"""Optional native-part preview using an installed ldraw-mcp / Blender runtime."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ldraw", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--library", type=Path, required=True)
    parser.add_argument("--blender", type=Path, required=True)
    parser.add_argument("--addons", type=Path, help="Blender user scripts folder containing ImportLDraw")
    parser.add_argument("--azimuths", default="135,315")
    parser.add_argument("--resolution", type=int, default=900)
    parser.add_argument("--samples", type=int, default=32)
    args = parser.parse_args()
    os.environ["LDRAW_LIBRARY_PATH"] = str(args.library.resolve())
    os.environ["LDRAW_MCP_BLENDER"] = str(args.blender.resolve())
    if args.addons:
        os.environ["BLENDER_USER_SCRIPTS"] = str(args.addons.resolve())
    from ldraw_mcp.render import render_ldraw
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from car2lego3d.studio import assembly_sequence
    sequence = assembly_sequence(args.ldraw.read_text(encoding="utf-8"))
    parts = [row[-1] for row in sequence if row[0] == "1"]
    folders = [args.library / "parts", args.library / "UnOfficial" / "parts",
               args.library / "unofficial" / "parts"]
    missing = sorted({part for part in parts if not any((folder / part).is_file() for folder in folders)})
    if missing:
        raise ValueError(f"Missing native parts: {missing}")
    azimuths = [float(value) for value in args.azimuths.split(",")]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    render_ldraw(str(args.ldraw.resolve()), str(args.output.resolve()), azimuths,
                 samples=args.samples, resolution=args.resolution)
    digest = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
    report = {"model_sha256": digest(args.ldraw), "image_sha256": digest(args.output),
              "part_count": len(parts), "distinct_parts": len(set(parts)), "missing_parts": missing,
              "renderer": f"ldraw-mcp {importlib.metadata.version('ldraw-mcp')} / Blender / ImportLDraw",
              "azimuths": azimuths, "resolution_per_view": args.resolution, "samples": args.samples,
              "appearance_accepted": False, "collision_verified": False, "physical_verified": False}
    args.output.with_suffix(".json").write_text(json.dumps(report, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
