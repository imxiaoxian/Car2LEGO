"""Run the optional community analyzer with an isolated, scoped part library.

Use the legolization-venv Python. This leaves backend and global pyldraw
configuration unchanged. Results are supplementary, never quality gate passes.
"""
import argparse
from contextlib import redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import shutil
import sys

from ldraw.config import Config
from ldraw.generate import FORMAT_STRING, get_parts_lst
from legolization.main import main


def run() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("design", default="e08894ce-7909-48f2-a3cf-16292d0a4e3e", nargs="?")
    parser.add_argument("--design-directory", type=Path)
    parser.add_argument("--ldraw-library", type=Path)
    parser.add_argument("--output-directory", type=Path)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    design = (args.design_directory or project / "backend/storage" / args.design).resolve()
    scene = json.loads((design / "scene.json").read_text(encoding="utf-8"))
    source = (args.ldraw_library or project / "Studio 2.0/ldraw").resolve()
    root = (args.output_directory or project / "backend/storage/tool_research/scoped-analysis-library" / args.design).resolve()
    library = root / "ldraw"
    root.mkdir(parents=True, exist_ok=True)
    requested = {part["part_num"].replace("\\", "/") for part in scene["parts"]}
    queue = sorted(requested)
    copied = {}
    while queue:
        reference = queue.pop()
        if reference.lower() in copied:
            continue
        relative = Path(reference)
        if relative.is_absolute() or ".." in relative.parts:
            raise ValueError(f"invalid reference {reference}")
        candidates = [source / folder / relative for folder in ("parts", "p", "UnOfficial/parts", "UnOfficial/p")]
        path = next((p for p in candidates if p.is_file()), None)
        if path is None:
            raise FileNotFoundError(reference)
        folder = "p" if path.is_relative_to(source / "p") or path.is_relative_to(source / "UnOfficial/p") else "parts"
        target = library / folder / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)
        data = path.read_bytes()
        copied[reference.lower()] = {"source": str(path), "sha256": hashlib.sha256(data).hexdigest()}
        for line in data.decode("utf-8", errors="replace").splitlines():
            fields = line.split()
            if fields and fields[0] == "1" and len(fields) >= 15:
                queue.append(" ".join(fields[14:]).replace("\\", "/"))
    shutil.copy2(source / "LDConfig.ldr", library / "LDConfig.ldr")
    rows = get_parts_lst(library / "parts", "description")
    (library / "parts.lst").write_text("\n".join(FORMAT_STRING.format(**row) for row in rows), encoding="utf-8")
    (root / "source-manifest.json").write_text(json.dumps({"design": args.design,
        "scope": "model parts and recursive geometry dependencies only", "files": copied}, indent=2), encoding="utf-8")
    config = Config(ldraw_library_path=str(root), generated_path=str(root / "generated"))
    # Scope configuration to this process; do not rewrite the user's config.yml.
    Config.load = classmethod(lambda cls, config_file=None: config)
    artifact_dir = root / "analysis"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    sys.argv = ["legolization", "analyze", str(design / "model.mpd"), "--no-repair",
                "--json", "--no-step-check", "--no-manifest", "--artifact-dir", str(artifact_dir)]
    print(f"Scoped {len(requested)} model parts, {len(copied)} geometry files", file=sys.stderr, flush=True)
    captured = StringIO()
    exit_code = 0
    with redirect_stdout(captured):
        try:
            result = main()
            if isinstance(result, int):
                exit_code = result
        except SystemExit as exc:
            exit_code = exc.code if isinstance(exc.code, int) else 1
    # The dependency prints generation progress on stdout before the CLI JSON.
    # Preserve it on stderr and keep one machine-readable result on stdout.
    output = captured.getvalue()
    start = output.find('{\n  "artifacts"')
    if start < 0:
        print(output, file=sys.stderr)
        raise RuntimeError("analyzer did not emit its JSON envelope")
    print(output[:start], file=sys.stderr, end="")
    payload = json.loads(output[start:])
    status = "passed" if payload.get("status") in ("buildable", "passed", "ok") else "failed" if payload.get("status") in ("unbuildable", "failed") else "indeterminate"
    result_path = root / "analysis-result.json"
    result_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (root / "report.json").write_text(json.dumps({"status": status, "analyzer_status": payload.get("status"),
        "result_code": exit_code, "scene_design_id": args.design, "artifact_directory": str(artifact_dir),
        "part_count": len(scene["parts"]), "library_scope": "model parts and recursive geometry dependencies only",
        "analysis_result": result_path.name, "artifact_count": len(payload.get("artifacts", []))},
        ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": status, "analyzer_status": payload.get("status"), "parts": len(scene["parts"])}))
    raise SystemExit(exit_code)


if __name__ == "__main__":
    run()
