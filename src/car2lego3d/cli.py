import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from .common import model_lock, stage


def main():
    parser = argparse.ArgumentParser(description="Car2LEGO_3D: text -> image -> mesh -> LEGO plate sculpture")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Clone and pin upstream TripoSR source")
    commands.add_parser("doctor", help="Show environment and CUDA availability")
    for name in ("image", "reconstruct", "lego", "run"):
        child = commands.add_parser(name)
        child.add_argument("--output", type=Path, required=True)
        if name in ("image", "run"):
            child.add_argument("--prompt", required=name == "image")
            child.add_argument("--seed", type=int, default=42)
            child.add_argument("--steps", type=int, choices=range(1, 5), default=4)
        if name in ("reconstruct", "run"):
            child.add_argument("--image", type=Path, required=name == "reconstruct")
            child.add_argument("--resolution", type=int, choices=[64, 128, 192, 256], default=128)
            child.add_argument("--chunk-size", type=int, default=4096)
            child.add_argument("--no-remove-bg", action="store_true")
        if name != "lego":
            child.add_argument("--device", default="auto")
        if name in ("lego", "run"):
            if name == "lego":
                child.add_argument("--mesh", type=Path, required=True)
            child.add_argument("--length-studs", type=int, default=32)
            child.add_argument("--up-axis", choices=["x", "y", "z"], default="z")
            child.add_argument("--yaw", type=float, default=0)
            child.add_argument("--color", type=int, help="Force one LDraw color; otherwise nearest vertex color")
    args = parser.parse_args()
    if args.command == "setup":
        from .reconstruction import setup_source
        print(setup_source())
    elif args.command == "doctor":
        import torch
        info = {"python": sys.version, "platform": platform.platform(), "torch": torch.__version__,
                "cuda_available": torch.cuda.is_available(), "torch_cuda": torch.version.cuda, "models": model_lock()}
        if torch.cuda.is_available():
            properties = torch.cuda.get_device_properties(0)
            info.update(gpu=properties.name, gpu_total_mb=round(properties.total_memory / 2**20))
        print(json.dumps(info, indent=2))
    elif args.command == "run":
        if bool(args.prompt) == bool(args.image):
            parser.error("run requires exactly one of --prompt or --image")
        if args.output.exists() and any(args.output.iterdir()):
            parser.error("run --output must be empty to preserve prior artifacts")
        args.output.mkdir(parents=True, exist_ok=True)
        with stage(args.output, "pipeline", {"mode": "prompt" if args.prompt else "image", "seed": args.seed,
                                             "resolution": args.resolution, "length_studs": args.length_studs}) as record:
            if args.prompt:
                invoke("image", "--prompt", args.prompt, "--output", args.output / "01-image",
                       "--seed", args.seed, "--steps", args.steps, "--device", args.device)
                source = args.output / "01-image" / "reference.png"
            else:
                source = args.image.resolve()
            extra = ["--no-remove-bg"] if args.no_remove_bg else []
            invoke("reconstruct", "--image", source, "--output", args.output / "02-mesh", "--resolution", args.resolution,
                   "--chunk-size", args.chunk_size, "--device", args.device, *extra)
            color_args = ["--color", args.color] if args.color is not None else []
            invoke("lego", "--mesh", args.output / "02-mesh" / "mesh.glb", "--output", args.output / "03-lego",
                   "--length-studs", args.length_studs, "--up-axis", args.up_axis, "--yaw", args.yaw, *color_args)
            record["buildability"] = "unverified"
    elif args.command == "image":
        from .image import generate
        print(generate(args.prompt, args.output, args.seed, args.steps, args.device))
    elif args.command == "reconstruct":
        from .reconstruction import reconstruct
        print(reconstruct(args.image, args.output, args.resolution, args.chunk_size, args.device, not args.no_remove_bg))
    elif args.command == "lego":
        from .lego import convert
        print(convert(args.mesh, args.output, args.length_studs, args.up_axis, args.yaw, args.color))


def invoke(*arguments):
    # A process per model stage guarantees GPU memory is released before the next stage.
    subprocess.run([sys.executable, "-m", "car2lego3d", *map(str, arguments)], check=True)
