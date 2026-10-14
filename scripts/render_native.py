"""Optional native-part preview using an installed ldraw-mcp / Blender runtime."""
import argparse
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
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
    from car2lego3d.native import render_native
    azimuths = [float(value) for value in args.azimuths.split(",")]
    print(render_native(args.ldraw, args.output, args.library, args.blender, args.addons,
                        azimuths, args.samples, args.resolution))


if __name__ == "__main__":
    main()
