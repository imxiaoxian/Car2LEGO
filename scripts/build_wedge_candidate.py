"""Rebuild a saved reconstruction, retaining a reproducible legacy comparator."""
import argparse
from collections import Counter
import json
from pathlib import Path
import subprocess

import numpy as np

from car2lego3d.carfit import convert_car, design, export, fit_mesh, split_steps
from car2lego3d.common import ROOT, digest, write_json
from car2lego3d.lego import load_mesh
from car2lego3d.vehicle import load_spec


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-run", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--mesh", type=Path, help="Explicit audited reconstruction GLB")
    parser.add_argument("--scale", default="1:24")
    parser.add_argument("--scale-mode", choices=["appearance", "exact"], default="appearance")
    parser.add_argument("--legacy-sports", action="store_true")
    args = parser.parse_args()
    source, output = args.source_run.resolve(), args.output.resolve()
    if output.exists():
        raise ValueError("Use a new candidate directory to preserve earlier comparisons")
    lego = output / "03-lego"
    mesh = args.mesh.resolve(strict=True) if args.mesh else source / "02-mesh/calibrated.glb"
    spec = source / "spec/spec.json"
    views = source / "01-image/views.json"
    if args.legacy_sports:
        fit = fit_mesh(load_mesh(mesh), specifications=load_spec(spec), scale=args.scale, color=15,
                       scale_mode=args.scale_mode)
        roof = np.flatnonzero(np.asarray(fit["height_profile_studs"]) > max(fit["height_profile_studs"])*.94)
        end = int(np.clip(round(float(roof.mean())+1), 12, fit["length_studs"]-9))
        fit.update(roof_start_stud=end-1, roof_end_stud=end, recipe="sports-v1")
        fit.pop("family_builder", None)
        car = design(fit)
        split_steps(car, 12)
        lego.mkdir(parents=True)
        export(car, lego)
        write_json(lego / "fit.json", fit)
        write_json(lego / "validation.json", dict(part_count=len(car.parts), appearance_accepted=False,
            comparison_only=True, note="Legacy sports builder at the same scale, mesh and colour"))
    else:
        convert_car(mesh, lego, vehicle_spec=spec, reference_views=views, scale=args.scale, color=15,
                    scale_mode=args.scale_mode)
    write_json(output / "request.json", dict(brand="Lamborghini", model="Countach", year=1988,
        variant="5000 Quattrovalvole", scale=args.scale, scale_mode=args.scale_mode, color=15,
        custom_request="White, red cabin, door glass integrated with each door assembly",
        seed=42, reconstruction_backend="gpt-blender", parent_design_id=None))
    write_json(output / "provenance.json", dict(mesh_sha256=digest(mesh), spec_sha256=digest(spec),
        views_sha256=digest(views), legacy_sports=args.legacy_sports,
        builder_sha256=digest(ROOT / "src/car2lego3d/wedge.py"), appearance_accepted=False))
    bridge = ["D:/python/anaconda/python.exe", "-B"]
    subprocess.run([*bridge, str(ROOT / "scripts/native_audit_worker.py"), "--source", "D:/lego",
        "--assembly", str(lego / "assembly.json"), "--output", str(lego / "native-audit.json")], check=True)
    subprocess.run([*bridge, str(ROOT / "scripts/frontend_bridge_worker.py"), "render", "--source", "D:/lego",
        "--input", str(lego / "assembly.json"), "--request", str(output / "request.json"),
        "--output", str(output / "05-presentation/presentation.json")], check=True)
    from car2lego3d.studio import export_studio
    export_studio(lego / "model.ldr", output / "04-studio")
    rows = json.loads((lego / "assembly.json").read_text())["parts"]
    print(json.dumps(dict(output=str(output), parts=len(rows),
        modules=Counter(p["module"] for p in rows)), ensure_ascii=True))


if __name__ == "__main__":
    main()
