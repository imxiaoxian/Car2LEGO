"""Supplementary checks using isolated LDraw MCP and legolization runtimes."""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import uuid

from app.config import settings
from .jobs import atomic_json
from .scene import AssemblyScene


def _tool_paths() -> dict[str, Path]:
    root = Path(settings.storage_path).resolve() / "tool_research"
    scripts = Path(__file__).resolve().parents[3] / "tasks"
    windows = os.name == "nt"
    scripts_dir = "Scripts" if windows else "bin"
    python_name = "python.exe" if windows else "python"
    executable_name = "ldraw-mcp.exe" if windows else "ldraw-mcp"
    return {
        "root": root,
        "ldraw_python": Path(settings.assembly_ldraw_mcp_python) if settings.assembly_ldraw_mcp_python else root / "ldraw-venv" / scripts_dir / python_name,
        "ldraw_command": Path(settings.assembly_ldraw_mcp_command) if settings.assembly_ldraw_mcp_command else root / "ldraw-venv" / scripts_dir / executable_name,
        "blender": Path(settings.assembly_ldraw_mcp_blender) if settings.assembly_ldraw_mcp_blender else root / "blender-4.5.14-windows-x64" / "blender.exe",
        "legolization_python": Path(settings.assembly_legolization_python) if settings.assembly_legolization_python else root / "legolization-venv" / scripts_dir / python_name,
        "ldraw_worker": scripts / "ldraw_mcp_quality.py",
        "legolization_worker": scripts / "analyze_f40_external.py",
    }


def _input_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _run_process(command: list[str], timeout: int, env: dict[str, str]) -> tuple[int | None, str, str, str | None]:
    try:
        result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                timeout=timeout, env=env, check=False)
        return result.returncode, result.stdout, result.stderr, None
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf-8", errors="replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf-8", errors="replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        return None, stdout, stderr, f"Timed out after {timeout} seconds"
    except OSError as exc:
        return None, "", "", str(exc)


def _load_worker_report(path: Path, return_code: int | None, stderr: str, error: str | None) -> dict:
    if path.is_file():
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
            pending = report.pop("_pending", False)
            if error:
                report["status"] = "indeterminate"
                report["error"] = error
            elif pending:
                report["status"] = "indeterminate"
                report["error"] = "Worker exited without publishing a final report"
            elif return_code not in (None, 0) and report.get("status") == "passed":
                report["status"] = "indeterminate"
                report["error"] = f"Worker exited with status {return_code}"
            return report
        except (OSError, json.JSONDecodeError) as exc:
            error = f"Invalid worker report: {exc}"
    return {"status": "indeterminate", "error": error or (stderr.strip()[-2000:] or "Worker did not produce a report")}


def _prepare_worker_report(path: Path, tool: str, scene_hash: str) -> None:
    """Archive an earlier run so a timeout cannot inherit its success report."""
    if path.is_file():
        archive = path.with_name(f"report.previous-{uuid.uuid4().hex}.json")
        path.replace(archive)
    atomic_json(path, {"status": "indeterminate", "tool": tool, "scene_hash": scene_hash,
                       "_pending": True, "reason": "Worker run has not completed"})


def run_external_checks(scene: AssemblyScene, directory: Path, progress=None) -> dict:
    """Run independent render/BOM and connectivity diagnostics after canonical export."""
    model_path = directory / "model.mpd"
    if not settings.assembly_external_checks_enabled:
        return {"schema": "assembly_v3.external_check.v1", "scene_hash": scene.digest(),
                "status": "indeterminate", "reason": "External checks are disabled", "checks": {}}
    if not model_path.is_file():
        return {"schema": "assembly_v3.external_check.v1", "scene_hash": scene.digest(),
                "status": "indeterminate", "reason": "Canonical MPD is missing", "checks": {}}

    paths = _tool_paths()
    external_root = directory / "external"
    external_root.mkdir(parents=True, exist_ok=True)
    timeout = max(1, settings.assembly_external_check_timeout_seconds)
    base = {"schema": "assembly_v3.external_check.v1", "scene_hash": scene.digest(),
            "input": "model.mpd", "input_sha256": _input_hash(model_path), "checks": {},
            "precision_verified_effect": "none"}

    ldraw_dir = external_root / "ldraw_mcp"
    if progress:
        progress("external_checks:ldraw_mcp", 97)
    if paths["ldraw_python"].is_file() and paths["ldraw_command"].is_file() and paths["ldraw_worker"].is_file():
        ldraw_dir.mkdir(parents=True, exist_ok=True)
        _prepare_worker_report(ldraw_dir / "report.json", "ldraw-mcp", scene.digest())
        env = os.environ.copy()
        env.update({"PYTHONUTF8": "1", "ASSEMBLY_LDRAW_MCP_COMMAND": str(paths["ldraw_command"]),
                    "ASSEMBLY_LDRAW_LIBRARY": str(Path(settings.studio_ldraw_path).resolve()),
                    "ASSEMBLY_LDRAW_MCP_BLENDER": str(paths["blender"]),
                    "ASSEMBLY_LDRAW_BLENDER_SCRIPTS": str(paths["root"] / "blender-scripts")})
        command = [str(paths["ldraw_python"]), str(paths["ldraw_worker"]), "--model", str(model_path),
                   "--scene", str(directory / "scene.json"), "--output", str(ldraw_dir)]
        code, _, stderr, error = _run_process(command, timeout, env)
        check = _load_worker_report(ldraw_dir / "report.json", code, stderr, error)
        check.update(tool="ldraw-mcp", version="0.3.1", artifacts_dir="external/ldraw_mcp")
        base["checks"]["ldraw_mcp"] = check
    else:
        missing = [str(paths[key]) for key in ("ldraw_python", "ldraw_command", "ldraw_worker") if not paths[key].is_file()]
        base["checks"]["ldraw_mcp"] = {"status": "indeterminate", "tool": "ldraw-mcp",
                                        "reason": "Runtime is not configured", "missing": missing}

    legolization_dir = external_root / "legolization"
    if progress:
        progress("external_checks:legolization", 98)
    if paths["legolization_python"].is_file() and paths["legolization_worker"].is_file():
        legolization_dir.mkdir(parents=True, exist_ok=True)
        _prepare_worker_report(legolization_dir / "report.json", "legolization", scene.digest())
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        command = [str(paths["legolization_python"]), str(paths["legolization_worker"]),
                   scene.design_id, "--design-directory", str(directory), "--ldraw-library",
                   str(Path(settings.studio_ldraw_path).resolve()), "--output-directory", str(legolization_dir)]
        code, _, stderr, error = _run_process(command, timeout, env)
        check = _load_worker_report(legolization_dir / "report.json", code, stderr, error)
        check.update(tool="legolization", version="0.6.0", license="GPL-3.0-or-later",
                     artifacts_dir="external/legolization")
        base["checks"]["legolization"] = check
    else:
        missing = [str(paths[key]) for key in ("legolization_python", "legolization_worker") if not paths[key].is_file()]
        base["checks"]["legolization"] = {"status": "indeterminate", "tool": "legolization",
                                           "reason": "Runtime is not configured", "missing": missing}

    states = [result.get("status", "indeterminate") for result in base["checks"].values()]
    base["status"] = "failed" if "failed" in states else "passed" if states and all(s == "passed" for s in states) else "indeterminate"
    base["limitations"] = [
        "External checks are advisory and do not override assembly_v3 gates.",
        "LDraw rendering and BOM coverage do not prove physical connections or appearance fidelity.",
        "legolization connection and load estimates do not prove Studio or physical-build acceptance.",
    ]
    atomic_json(external_root / "report.json", base)
    return base
