"""Re-render and measure a saved scene without another image or modelling API call."""
import argparse
import json
from pathlib import Path

from car2lego3d.blender_mcp import BlenderSession, render_code
from car2lego3d.common import ROOT, digest, stage
from car2lego3d.model_quality import assess_model
from car2lego3d.vehicle import load_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--body-style", default=None)
    parser.add_argument("--port", type=int, default=9878)
    args = parser.parse_args()
    source, output = args.blend.resolve(strict=True), args.output.resolve()
    if output.exists():
        parser.error("Use a new output directory to preserve earlier modelling evidence")
    spec = load_spec(args.spec)
    with stage(output, "model-audit", dict(source_blend=str(source), source_sha256=digest(source),
            spec_sha256=digest(args.spec), new_model_calls=0,
            export_script_sha256=digest(ROOT / "scripts/blender_export_render.py"))) as record:
        with BlenderSession(output, port=args.port) as blender:
            blender.execute("import bpy\nbpy.ops.wm.open_mainfile(filepath=" + repr(str(source)) + ")", "load-scene")
            blender.execute(render_code(output), "audit-export-render")
            quality = assess_model(output, spec, body_style=args.body_style)
            record.update(quality_status=quality["status"], failed_checks=quality["failed_checks"],
                appearance_accepted=False, outputs={p.name: digest(p) for p in output.iterdir()
                    if p.suffix in {".glb", ".blend", ".png"} or p.name in {"model-quality.json", "scene-metrics.json"}})
    print(json.dumps(dict(output=str(output), failed_checks=quality["failed_checks"])))


if __name__ == "__main__":
    main()
