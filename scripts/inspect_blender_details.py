"""Inspect saved Blender geometry and save an annotated copy, without a model API call."""
import argparse
import json
from pathlib import Path

from car2lego3d.blender_mcp import BlenderSession
from car2lego3d.common import ROOT, digest, stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blend", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--port", type=int, default=9878)
    args = parser.parse_args()
    source, output = args.blend.resolve(strict=True), args.output.resolve()
    if output.exists():
        parser.error("Use a fresh output directory")
    template = ROOT / "scripts/blender_inspect_details.py"
    with stage(output, "detail-inspection-run", dict(source_blend=str(source), source_sha256=digest(source),
            script_sha256=digest(template), new_model_calls=0)) as record:
        with BlenderSession(output, port=args.port) as blender:
            blender.execute("import bpy\nbpy.ops.wm.open_mainfile(filepath=" + repr(str(source)) + ")", "load-scene")
            blender.execute("OUTPUT_DIRECTORY=" + repr(str(output)) + "\nSOURCE_BLEND=" + repr(str(source))
                            + "\nSOURCE_SHA256=" + repr(digest(source)) + "\n"
                            + template.read_text(encoding="utf-8"), "inspect-details")
        report = json.loads((output / "detail-inspection.json").read_text(encoding="utf-8"))
        if report["source_sha256"] != digest(source):
            raise ValueError("Inspection report does not match the source scene")
        record.update(sampled_objects=report["sampled_objects"], issues=len(report["issues"]),
            source_preserved=digest(source) == record["inputs"]["source_sha256"],
            outputs={name: digest(output / name) for name in ("detail-inspection.json", "inspected.blend")})
    print(json.dumps(dict(output=str(output), sampled_objects=report["sampled_objects"], issues=len(report["issues"]))))


if __name__ == "__main__":
    main()
