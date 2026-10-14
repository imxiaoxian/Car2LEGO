import argparse
import json
import platform
import subprocess
import sys
from pathlib import Path

from .common import model_lock, stage, write_json


def main():
    parser = argparse.ArgumentParser(description="Car2LEGO_3D: text -> image -> mesh -> LEGO -> Studio .io")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("setup", help="Clone and pin upstream TripoSR source")
    commands.add_parser("doctor", help="Show environment and CUDA availability")
    studio = commands.add_parser("studio", help="Package a flat LDraw assembly as Studio .io")
    studio.add_argument("--ldraw", type=Path, required=True)
    studio.add_argument("--output", type=Path, required=True)
    studio.add_argument("--thumbnail", type=Path)
    measure = commands.add_parser("measure", help="Convert orthographic side-view annotations to physical priors")
    measure.add_argument("--vehicle-specs", type=Path, required=True)
    measure.add_argument("--annotations", type=Path, required=True)
    measure.add_argument("--reference-image", type=Path, required=True)
    measure.add_argument("--output", type=Path, required=True)
    for name in ("image", "reconstruct", "lego", "run"):
        child = commands.add_parser(name)
        child.add_argument("--output", type=Path, required=True)
        child.add_argument("--vehicle-specs", type=Path, help="Sourced physical vehicle dimensions JSON")
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
            child.add_argument("--length-studs", type=int, default=24)
            child.add_argument("--strategy", choices=["plates", "car"], default="car")
            child.add_argument("--width-studs", type=int, choices=[8, 10, 12],
                               help="Body core width; spec mode selects the nearest family if omitted")
            child.add_argument("--no-rear-wing", action="store_true")
            child.add_argument("--up-axis", choices=["x", "y", "z"], default="z")
            child.add_argument("--yaw", type=float, default=0)
            child.add_argument("--color", type=int, help="Body color for car strategy; uniform color for plates")
    args = parser.parse_args()
    vehicle_spec = getattr(args, "vehicle_specs", None)
    if vehicle_spec is not None:
        from .vehicle import load_spec
        vehicle_spec = vehicle_spec.resolve()
        try:
            load_spec(vehicle_spec)
        except (ValueError, OSError) as error:
            parser.error(str(error))
    if getattr(args, "strategy", None) == "plates" and (vehicle_spec is not None or args.width_studs is not None):
        parser.error("--vehicle-specs and --width-studs currently require --strategy car")
    if args.command == "run" and vehicle_spec is not None and (args.up_axis != "z" or args.yaw != 0):
        parser.error("Spec-based run uses the calibrated TripoSR X-long/Z-up frame; omit --up-axis and --yaw")
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
        if vehicle_spec is not None:
            snapshot = args.output / "00-vehicle" / "spec.json"
            write_json(snapshot, load_spec(vehicle_spec))
            vehicle_spec = snapshot.resolve()
        spec_args = ["--vehicle-specs", vehicle_spec] if vehicle_spec is not None else []
        with stage(args.output, "pipeline", {"mode": "prompt" if args.prompt else "image", "seed": args.seed,
                                             "resolution": args.resolution, "length_studs": args.length_studs,
                                             "strategy": args.strategy}) as record:
            if vehicle_spec is not None:
                from .vehicle import spec_record
                record["vehicle_spec"] = spec_record(vehicle_spec)
            if args.prompt:
                invoke("image", "--prompt", args.prompt, "--output", args.output / "01-image",
                       "--seed", args.seed, "--steps", args.steps, "--device", args.device, *spec_args)
                source = args.output / "01-image" / "reference.png"
            else:
                source = args.image.resolve()
            extra = ["--no-remove-bg"] if args.no_remove_bg else []
            invoke("reconstruct", "--image", source, "--output", args.output / "02-mesh", "--resolution", args.resolution,
                   "--chunk-size", args.chunk_size, "--device", args.device, *extra, *spec_args)
            mesh = args.output / "02-mesh" / ("calibrated.glb" if vehicle_spec is not None else "mesh.glb")
            color_args = ["--color", args.color] if args.color is not None else []
            invoke("lego", "--mesh", mesh, "--output", args.output / "03-lego",
                   "--length-studs", args.length_studs, "--up-axis", args.up_axis, "--yaw", args.yaw,
                   "--strategy", args.strategy, *(["--no-rear-wing"] if args.no_rear_wing else []), *color_args,
                   *(["--width-studs", args.width_studs] if args.width_studs is not None else []), *spec_args)
            thumbnail = args.output / "03-lego" / "lego-preview.png"
            thumbnail_args = ["--thumbnail", thumbnail] if thumbnail.exists() else []
            invoke("studio", "--ldraw", args.output / "03-lego" / "model.ldr",
                   "--output", args.output / "04-studio", *thumbnail_args)
            record["studio_file"] = "04-studio/model.io"
            record["buildability"] = "unverified"
            record["appearance_accepted"] = False
    elif args.command == "image":
        from .image import generate
        print(generate(args.prompt, args.output, args.seed, args.steps, args.device, vehicle_spec))
    elif args.command == "reconstruct":
        from .reconstruction import reconstruct
        print(reconstruct(args.image, args.output, args.resolution, args.chunk_size, args.device,
                          not args.no_remove_bg, vehicle_spec))
    elif args.command == "lego":
        if args.strategy == "car":
            from .carfit import convert_car
            print(convert_car(args.mesh, args.output, args.length_studs, args.up_axis, args.yaw,
                              args.color, not args.no_rear_wing, vehicle_spec, args.width_studs))
        else:
            from .lego import convert
            print(convert(args.mesh, args.output, args.length_studs, args.up_axis, args.yaw, args.color))
    elif args.command == "studio":
        from .studio import export_studio
        print(export_studio(args.ldraw, args.output, args.thumbnail))
    elif args.command == "measure":
        from .measurement import measure_side_view
        from .common import digest
        with stage(args.output, "measurement", {"image_sha256": digest(args.reference_image),
                    "annotation_sha256": digest(args.annotations), "vehicle_spec_sha256": digest(vehicle_spec)}) as record:
            spec = measure_side_view(load_spec(vehicle_spec),
                                     json.loads(args.annotations.read_text(encoding="utf-8")), args.reference_image)
            output = args.output / "spec.json"
            write_json(output, spec)
            record.update(physical_measurement_verified=False, outputs={output.name: digest(output)})
        print(output)


def invoke(*arguments):
    # A process per model stage guarantees GPU memory is released before the next stage.
    subprocess.run([sys.executable, "-m", "car2lego3d", *map(str, arguments)], check=True)
