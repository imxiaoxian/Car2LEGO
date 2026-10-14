"""Optional native geometry preview, using a configured local LDraw/Blender runtime."""
import importlib.metadata
import os
from pathlib import Path

from .common import digest, write_json
from .studio import assembly_sequence


def render_native(source, output, library, blender, addons=None, azimuths=(135, 315),
                  samples=32, resolution=900):
    source, output, library = Path(source), Path(output), Path(library)
    os.environ["LDRAW_LIBRARY_PATH"] = str(library.resolve())
    os.environ["LDRAW_MCP_BLENDER"] = str(Path(blender).resolve())
    if addons:
        os.environ["BLENDER_USER_SCRIPTS"] = str(Path(addons).resolve())
    from ldraw_mcp.render import render_ldraw
    sequence = assembly_sequence(source.read_text(encoding="utf-8"))
    parts = [row[-1] for row in sequence if row[0] == "1"]
    folders = [library / "parts", library / "UnOfficial/parts", library / "unofficial/parts"]
    missing = sorted({part for part in parts if not any((folder / part).is_file() for folder in folders)})
    if missing:
        raise ValueError(f"Missing native parts: {missing}")
    output.parent.mkdir(parents=True, exist_ok=True)
    render_ldraw(str(source.resolve()), str(output.resolve()), list(azimuths), samples=samples, resolution=resolution)
    report = {"status": "completed", "model_sha256": digest(source), "image_sha256": digest(output),
              "part_count": len(parts), "distinct_parts": len(set(parts)), "missing_parts": missing,
              "renderer": f"ldraw-mcp {importlib.metadata.version('ldraw-mcp')} / Blender / ImportLDraw",
              "azimuths": list(azimuths), "resolution_per_view": resolution, "samples": samples,
              "appearance_accepted": False, "collision_verified": False, "physical_verified": False}
    write_json(output.with_suffix(".json"), report)
    return output


def configured_preview(source, directory):
    library, blender = (os.environ.get(key) for key in ("LDRAW_LIBRARY_PATH", "LDRAW_MCP_BLENDER"))
    directory = Path(directory)
    report_path = directory / "native-render.json"
    if not library or not blender:
        write_json(report_path, {"status": "unavailable", "reason": "LDraw/Blender runtime is not configured.",
                                 "appearance_accepted": False})
        return None
    try:
        preview = render_native(source, directory / "native-ldraw.png", library, blender,
                                os.environ.get("BLENDER_USER_SCRIPTS"))
    except Exception as error:
        write_json(report_path, {"status": "failed", "error": str(error), "appearance_accepted": False})
        raise RuntimeError("Configured native preview failed; inspect native-render.json.") from error
    write_json(report_path, {"status": "completed", "preview": preview.name,
                             "model_sha256": digest(source),
                             "image_sha256": digest(preview), "appearance_accepted": False})
    return preview
