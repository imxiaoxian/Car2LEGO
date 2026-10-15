"""Compare prepared multiview reconstructions using the same LEGO conversion inputs."""
import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess

import numpy as np

from car2lego3d.blender_mcp import BlenderSession, render_code
from car2lego3d.carfit import convert_car
from car2lego3d.common import ROOT, digest, write_json
from car2lego3d.gpt_reference import configuration
from car2lego3d.lego import load_mesh
from car2lego3d.studio import export_studio, verify_archive


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--views", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--scale", default="1:24")
    parser.add_argument("--color", type=int, default=25)
    parser.add_argument("--render-only", action="store_true", help="Refresh common-rig renders without rebuilding LEGO")
    args = parser.parse_args()
    source, python = configuration()
    result = dict(inputs=dict(spec_sha256=digest(args.spec), views_sha256=digest(args.views),
        scale=args.scale, color=args.color), backends={}, appearance_accepted=False,
        physical_build_verified=False, merge_recommended=False)
    for label, root in (("gpt-blender", args.candidate.resolve()), ("hunyuan3d", args.baseline.resolve())):
        if root.is_relative_to(source.resolve()):
            raise ValueError("Source project is read-only")
        mesh_dir = root / "02-mesh"
        mesh_path = mesh_dir / "calibrated.glb"
        with BlenderSession(mesh_dir) as blender:
            if label == "gpt-blender":
                blender.execute("import bpy\nbpy.ops.wm.open_mainfile(filepath=" + repr(str(mesh_dir / "model.blend")) + ")", "comparison-load")
            else:
                blender.execute("import bpy\nbpy.ops.object.select_all(action='SELECT')\nbpy.ops.object.delete(use_global=False)\n"
                    "bpy.ops.import_scene.gltf(filepath=" + repr(str(mesh_path)) + ")\n"
                    "from mathutils import Matrix\n"
                    "axis_fix = Matrix.Rotation(-1.5707963267948966, 4, 'X')\n"
                    "for obj in list(bpy.context.scene.objects):\n"
                    "    if obj.parent is None: obj.matrix_world = axis_fix @ obj.matrix_world", "comparison-load")
            blender.execute(render_code(mesh_dir, export=False), "comparison-render")
        record_path = mesh_dir / "reconstruction.json"
        if record_path.is_file():
            record = read(record_path)
            output_hashes = {name: digest(mesh_dir / name) for name in record.get("outputs", {})}
            changed = {name: value for name, value in output_hashes.items() if value != record["outputs"][name]}
            if changed:
                record.setdefault("postprocessing", []).append(dict(at=datetime.now(timezone.utc).isoformat(),
                    operation="common-rig render and evaluated-vertex metrics refresh",
                    previous_outputs=record.get("outputs", {}), changed_outputs=changed,
                    note="Display refresh only; reconstruction and LEGO conversion were not rerun."))
            record["outputs"] = output_hashes
            write_json(record_path, record)
        if args.render_only:
            print(label, "renders refreshed", flush=True)
        lego, studio = root / "03-lego", root / "04-studio"
        studio_file = studio / "model.io"
        if not args.render_only:
            convert_car(mesh_path, lego, vehicle_spec=args.spec, scale=args.scale, reference_views=args.views, color=args.color)
            studio_file = export_studio(lego / "model.ldr", studio)
        verify_archive(studio_file, lego / "model.ldr")
        request = root / "request.json"
        spec = read(args.spec)
        if not args.render_only:
            write_json(request, dict(brand=spec.get("research_input", {}).get("brand", "Lotus"),
                model=spec.get("research_input", {}).get("model", spec["model"]), year=None,
                scale=args.scale, color=args.color, variant="", custom_request="", seed=42))
        commands = [
            [python, "-B", ROOT / "scripts/frontend_bridge_worker.py", "presentation", "--source", source,
             "--input", lego / "assembly.json", "--request", request, "--output", root / "05-presentation/presentation.json"],
            [python, "-B", ROOT / "scripts/native_audit_worker.py", "--source", source,
             "--assembly", lego / "assembly.json", "--output", lego / "native-audit.json"],
        ]
        for i, command in enumerate(commands if not args.render_only else []):
            completed = subprocess.run([str(x) for x in command], cwd=ROOT, capture_output=True, timeout=600,
                env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"})
            (root / f"comparison-service-{i}.log").write_bytes(completed.stdout + completed.stderr)
            if completed.returncode:
                raise RuntimeError(f"{label}: inspect comparison-service-{i}.log")
        mesh = load_mesh(mesh_path)
        audit = read(lego / "native-audit.json")
        bounds = np.array(audit["bounds_ldu"])
        result["backends"][label] = dict(mesh_sha256=digest(mesh_path),
            mesh_extents_mm=(mesh.extents * 1000).tolist(), mesh_triangles=len(mesh.faces),
            mesh_dimensions_note="World-space bounding box includes mirrors and trim; not body-only dimensions",
            assembly_sha256=digest(lego / "assembly.json"), studio_sha256=digest(studio_file),
            recipe=read(lego / "validation.json")["recipe"], part_count=audit["part_count"],
            native_dimensions_mm=((bounds[1] - bounds[0])[[0, 2, 1]] * .4).tolist(),
            native_dimensions_order=["length", "width", "height"],
            collisions=audit["collision_count"], connectivity=audit["connectivity"],
            requirements=read(lego / "requirements-report.json"),
            source_inference="GPT vision + Blender MCP" if label == "gpt-blender" else "reused raw multiview inference, recalibrated with same spec")
        print(label, "complete", flush=True)
    candidate = read(args.candidate / "03-lego/assembly.json")["parts"]
    baseline = read(args.baseline / "03-lego/assembly.json")["parts"]
    result["identical_lego_parts_and_transforms"] = candidate == baseline
    write_json(args.output, result)
    print(args.output)


if __name__ == "__main__":
    main()
