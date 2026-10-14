"""Publish a fresh API-free F40 surface draft without modifying historical designs.

The source design supplies already saved vehicle references. Its Studio and
physical acceptance are never inherited by the new scene.
"""
import argparse
import asyncio
import hashlib
import json
import shutil
import uuid
from pathlib import Path

from app.config import settings
from app.database import async_session
from app.models.car import Car
from app.models.design import Design
from app.services.assembly_v3.exports import export_scene
from app.services.assembly_v3.jobs import JobStore, atomic_json
from app.services.assembly_v3.official_guides import guide_records
from app.services.assembly_v3.recipes import build_f40
from app.services.assembly_v3.validation import validate_scene
from app.services.design_parts import replace_design_parts


async def main(reference_id: str, target_image: str | None = None):
    reference_id = str(uuid.UUID(reference_id))
    async with async_session() as db:
        original = await db.get(Design, uuid.UUID(reference_id))
        car = await db.get(Car, original.car_id) if original else None
        if not car or car.make.lower() != "ferrari" or car.model.lower().replace(" ", "") != "f40":
            raise ValueError("Reference design must identify a Ferrari F40")
        car_id = car.id
    storage = Path(settings.storage_path)
    source = storage / reference_id
    if not (source / "references" / "manifest.json").is_file():
        raise ValueError("Saved reference manifest is required")
    design_id = str(uuid.uuid4())
    directory = storage / design_id
    directory.mkdir(parents=True)
    shutil.copytree(source / "references", directory / "references")
    if (source / "visual_plan.json").is_file():
        shutil.copy2(source / "visual_plan.json", directory / "visual_plan.json")
    request = dict(design_id=design_id, make="Ferrari", model="F40", year=1990, scale="1:24", custom_request="")
    scene = build_f40(design_id, "1:24")
    scene.planning.update(reference_source=reference_id, reference_reused=True,
                          official_build_references=guide_records(storage, request))
    if target_image:
        target = directory / "appearance_target.png"
        shutil.copy2(Path(target_image), target)
        scene.planning["user_appearance_target"] = dict(path=target.name,
            sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
            role="User supplied appearance target, not dimensional or connection evidence")
    jobs = JobStore(storage)
    jobs.ensure(design_id, request)
    owner = jobs.claim(design_id)
    progress = lambda stage, percent, **data: jobs.checkpoint(design_id, owner, stage, percent, **data)
    async with async_session() as db:
        db.add(Design(id=uuid.UUID(design_id), car_id=car_id, match_level=4, scale="1:24", status="processing",
                      metadata_={"workflow_version": "assembly_v3", "quality_level": "experimental_draft"}))
        await db.commit()
    print(json.dumps(dict(id=design_id, directory=str(directory.resolve()), status="processing")), flush=True)
    try:
        progress("assembly:modules", 55, scene_hash=scene.digest(), module_hashes=scene.module_hashes(), reference_source=reference_id)
        report = await asyncio.to_thread(validate_scene, scene, progress=progress)
        report["reference_consistency"] = dict(status="unverified", reference_source=reference_id,
            reuse="Existing saved references; no model calls and no new cross-view acceptance")
        progress("exporting", 85)
        result = await asyncio.to_thread(export_scene, scene, directory, report, progress)
        progress("acceptance", 100, scene_hash=scene.digest(), module_hashes=scene.module_hashes(), exported=True)
        async with async_session() as db:
            design = await db.get(Design, uuid.UUID(design_id))
            design.status = "draft"
            design.parts_count, design.steps_count = len(scene.parts), len(scene.steps)
            design.difficulty = "Expert"
            design.file_io_path, design.file_ldr_path, design.file_pdf_path = (
                f"{design_id}/model.io", f"{design_id}/model.ldr", f"{design_id}/instructions.pdf")
            design.metadata_ = dict(workflow_version="assembly_v3", quality_level="experimental_draft",
                quality_report=report, reference_source=reference_id, recipe=scene.planning["recipe"])
            await replace_design_parts(db, design.id, result["parts_data"])
            await db.commit()
        jobs.finish(design_id, owner, "draft")
    except Exception as exc:
        from app.agents.security import mask_api_key
        message = mask_api_key(str(exc))[:1000]
        jobs.finish(design_id, owner, "failed", message)
        async with async_session() as db:
            design = await db.get(Design, uuid.UUID(design_id))
            design.status, design.error_message = "failed", message
            await db.commit()
        raise
    summary = dict(id=design_id, scale=scene.scale, status="draft", parts=len(scene.parts), steps=len(scene.steps),
        url=f"http://127.0.0.1:3000/designs/{design_id}", recipe=scene.planning["recipe"], gates=report["gates"],
        collisions=len(report["collisions"]), disconnected=len(report["connectivity"]["disconnected_parts"]),
        deviation=report["scale_deviation_percent"], calls={"text": 0, "image": 0})
    registry = storage / "f40_surface_samples.json"
    saved = json.loads(registry.read_text(encoding="utf-8")) if registry.is_file() else {"samples": []}
    saved["samples"].append(summary)
    atomic_json(registry, saved)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--references", required=True)
    parser.add_argument("--target-image")
    args = parser.parse_args()
    asyncio.run(main(args.references, args.target_image))
