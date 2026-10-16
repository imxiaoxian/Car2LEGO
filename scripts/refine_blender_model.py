"""Apply an audited Astra correction to an existing Blender scene."""
import argparse
import json
from pathlib import Path
import shutil

from car2lego3d.blender_mcp import BlenderSession, MODEL_TIMEOUT, modelling_model, render_code, validate_code
from car2lego3d.common import digest, stage
from car2lego3d.dialogue import ask_json, image_content
from car2lego3d.model_quality import assess_model, new_failures
from car2lego3d.multiview import load_views
from car2lego3d.vehicle import load_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="Audited scene directory")
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--views", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--focus", required=True)
    parser.add_argument("--details", type=Path, help="Direct geometry inspection JSON matching the source scene")
    parser.add_argument("--port", type=int, default=9878)
    args = parser.parse_args()
    source, output = args.source.resolve(strict=True), args.output.resolve()
    if output.exists():
        parser.error("Use a new output directory to preserve previous evidence")
    spec = load_spec(args.spec)
    manifest, references = load_views(args.views)
    body_style = (manifest.get("brief") or {}).get("body_style")
    model = modelling_model()
    detail_summary = None
    if args.details:
        details = json.loads(args.details.read_text(encoding="utf-8"))
        if details.get("source_sha256") != digest(source / "model.blend"):
            parser.error("Direct inspection belongs to a different source scene")
        detail_summary = {k: details[k] for k in ("source_sha256", "method", "issues", "limitations")}
    with stage(output, "model-refinement", dict(source_blend=str(source / "model.blend"),
            source_sha256=digest(source / "model.blend"), spec_sha256=digest(args.spec),
            manifest_sha256=digest(args.views), model=model, focus=args.focus,
            direct_inspection_sha256=digest(args.details) if args.details else None)) as record:
        for name in ("model.blend", "scene-metrics.json", "model-quality.json"):
            shutil.copyfile(source / name, output / name)
        if (args.views.parent / "reference.png").is_file():
            references["overview"] = args.views.parent / "reference.png"
        scripts = {p.name: p.read_text(encoding="utf-8") for p in source.glob("*.py")
                   if p.name.startswith(("model-", "visual-refine", "focused-refine"))}
        with BlenderSession(output, port=args.port) as blender:
            blender.execute("import bpy\nbpy.ops.wm.open_mainfile(filepath=" + repr(str(output / "model.blend")) + ")", "load-scene")
            baseline = output / "baseline"
            baseline.mkdir()
            blender.execute(render_code(baseline, export=False), "baseline-render")
            before = assess_model(baseline, spec, body_style=body_style)
            metrics = json.loads((baseline / "scene-metrics.json").read_text(encoding="utf-8"))
            current = {"CURRENT_" + v: baseline / f"render-{v}.png" for v in
                       ("left", "right", "front", "back", "three-quarter", "rear-quarter")}
            response = ask_json([dict(role="system", content="""Correct the existing automotive Blender scene.
Return JSON {analysis, code}, with a compact bpy corrective script; the scene is already built.
Use only bpy, math, mathutils, random. Do not clear the scene, load/save files, or access network/shell.
X=front 0 to rear length, left=-Y, up=Z, full-size metres. Preserve core dimensions, wheels and
integrated closed door/window assemblies. Fix the focused issues using actual geometry and all views.
Do not hide or delete required parts to silence diagnostics. Keep closed mesh normals outward,
and keep glazing fitted to the visible surface. Define any needed helper functions in the patch.
Use shared boundary coordinates for cabin/cowl/pillar roots, nose/fender/bumper and rear deck/buttress/tail.
Avoid whole-shell Boolean cuts: they previously erased the body. Fit new local surfaces to the actual
existing evaluated shell. Replace defective transition meshes with deliberate topology where needed.
Glass bottom edges must seat on body/cowl/engine_deck and top edges into roof/header within 12 mm
along the WHOLE edge. Preserve deliberate styling creases and intentional small panel gaps.
Tag support roles cowl, header, cabin_buttress, front_fender, rear_fender, front_fascia, rear_fascia,
engine_deck as appropriate. On separate transition MESHES add vertex groups join_<target car_role>
containing ALL vertices of each true contact edge. If both rails target the same role, use distinct
groups join_<role>__<edge_id> so internal cross-edges are not included. Groups contain seam vertices only.
Set car_connection_region='cabin', 'front', or 'rear'.
Provide these real seam groups in ALL three regions; host samples each mesh edge every <=10 mm and
requires max distance <=12 mm to evaluated target triangles. Do not use single-point fake groups.
Keep evaluated triangles below 250000; adapt sampling to curvature, not a fixed millimetre grid.
Use finite-thickness smoked transmissive glass (IOR 1.45-1.52, Transmission Weight .65-.9,
roughness .08-.16, alpha=1), not an opaque black surface. Keep the cabin and red seats visible.
Lamps need a fitted housing, reflector, translucent lens and reference-specific outline.
Use up to 220 lines for structural fixes, preserving existing good details. Do not print mesh data."""),
            dict(role="user", content=[dict(type="text", text=json.dumps(dict(focus=args.focus,
                vehicle=spec, diagnostics=before, direct_3d_inspection=detail_summary,
                scene_inventory=metrics, source_scripts=scripts), ensure_ascii=False)),
                *image_content(references), *image_content(current)])], output, "focused-review",
            model=model, max_tokens=16000, timeout=MODEL_TIMEOUT, total_timeout=900,
            stream=True, reasoning_effort="medium", transient_retries=1)
            code = validate_code(response["code"])
            (output / "focused-refine.py").write_text(code, encoding="utf-8")
            blender.execute(code, "focused-refine")
            blender.execute(render_code(output), "refined-export-render")
            after = assess_model(output, spec, body_style=body_style)
            regressions = new_failures(before, after)
            record.update(analysis=response["analysis"], failed_checks=after["failed_checks"],
                new_geometry_failures=regressions, candidate_selected=not regressions, appearance_accepted=False,
                outputs={p.name: digest(p) for p in output.iterdir() if p.suffix in {".glb", ".blend", ".png"}
                         or p.name in {"model-quality.json", "scene-metrics.json"}})
            if regressions:
                raise ValueError("Candidate rejected; source preserved. New failures: " + ", ".join(regressions))
    print(json.dumps(dict(output=str(output), failed_checks=after["failed_checks"])))


if __name__ == "__main__":
    main()
