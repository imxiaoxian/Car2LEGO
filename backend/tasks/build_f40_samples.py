"""Build honest F40 draft artifacts using existing generated references and a fresh visual plan.

Run from backend: python -m tasks.build_f40_samples --references <existing-design-id>
Does not alter the source design or claim Studio/physical acceptance.
"""

import argparse
import asyncio
import json
import shutil
import uuid
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from sqlalchemy import select

from app.agents.models import create_text_llm
from app.config import settings
from app.database import async_session
from app.models.car import Car
from app.models.design import Design
from app.services.assembly_v3.pipeline import review_references, refine_references, module_reference_views
from app.services.assembly_v3.official_guides import guide_records
from app.services.assembly_v3.recipes import build_f40
from app.services.assembly_v3.validation import validate_scene
from app.services.assembly_v3.exports import export_scene
from app.services.assembly_v3.jobs import JobStore, atomic_json
from app.services.design_parts import replace_design_parts
from app.services.reference_images import ReferenceImageService, reference_fingerprint


async def main(reference_id: str, resume: bool = False):
    storage=Path(settings.storage_path)
    source=storage/str(uuid.UUID(reference_id))
    manifest=json.loads((source/"references"/"manifest.json").read_text(encoding="utf-8"))
    async with async_session() as db:
        original=await db.get(Design,uuid.UUID(reference_id))
        car=await db.get(Car,original.car_id) if original else None
        if not car or car.make.lower()!="ferrari" or car.model.lower().replace(" ","")!="f40":
            raise ValueError("Reference source must be an existing Ferrari F40 design")
        car_id=car.id
    summary=[]
    previous=json.loads((storage/"f40_samples.json").read_text(encoding="utf-8"))["samples"] if resume and (storage/"f40_samples.json").is_file() else []
    for scale in ("1:24","1:16","1:12"):
        saved=next((s for s in previous if s["scale"]==scale),None)
        if saved and saved.get("status")=="draft":
            summary.append(saved);source=storage/saved["id"];manifest=json.loads((source/"references"/"manifest.json").read_text(encoding="utf-8"));continue
        id=saved["id"] if saved else str(uuid.uuid4()); directory=storage/id;directory.mkdir(parents=True,exist_ok=True)
        if not (directory/"references").exists():shutil.copytree(source/"references",directory/"references")
        request=dict(design_id=id,make="Ferrari",model="F40",year=1990,scale=scale,vehicle_features={},custom_request="",mod_ids=[])
        state=request | dict(storage_path=str(storage),workflow_version="assembly_v3")
        imported=dict(manifest)
        imported.update(fingerprint=reference_fingerprint(state),imported_from=reference_id,
                        import_evidence="Source vehicle identity checked against the design database")
        if not saved:atomic_json(directory/"references"/"manifest.json",imported)
        jobs=JobStore(storage);jobs.ensure(id,request)
        if saved and jobs.get(id)["state"] in ("failed","paused"):
            jobs.control(id,"resume")
        owner=jobs.claim(id)
        if not owner:raise RuntimeError("Another worker owns the saved sample")
        progress=lambda stage,p,**kw:jobs.checkpoint(id,owner,stage,p,**kw)
        state.update(consume_call=lambda kind:jobs.consume(id,owner,kind),checkpoint_progress=progress)
        async with async_session() as db:
            design=await db.get(Design,uuid.UUID(id))
            if not design:
                design=Design(id=uuid.UUID(id),car_id=car_id,match_level=4,scale=scale,status="processing",
                    metadata_={"workflow_version":"assembly_v3","quality_level":"experimental_draft","reference_source":reference_id});db.add(design)
            else:design.status="processing"
            await db.commit()
        item={"id":id,"scale":scale,"status":"processing","url":f"http://127.0.0.1:3000/designs/{id}"}
        summary.append(item);atomic_json(storage/"f40_samples.json",{"samples":summary,"reference_source":reference_id})
        print(json.dumps(item),flush=True)
        progress("reference_images",5)
        try:
            state.update(await ReferenceImageService().generate(state))
            progress("reference_consistency",36,references=True)
            checkpoint=jobs.get(id)["data"]["checkpoint"]
            intent=checkpoint.get("intent") or await review_references(state,request)
            if not checkpoint.get("references_refined"):
                intent=await refine_references(state,request,intent)
                progress("planning",44,intent=intent,references_refined=True)
            atomic_json(directory/"visual_plan.json",intent)
            progress("assembly:modules",50,intent=intent,reference_source=reference_id)
        except Exception as exc:
            from app.agents.security import mask_api_key
            jobs.finish(id,owner,"failed",mask_api_key(str(exc))[:1000])
            async with async_session() as db:
                design=await db.get(Design,uuid.UUID(id));design.status="failed";design.error_message=mask_api_key(str(exc))[:1000];await db.commit()
            item.update(status="failed",error=mask_api_key(str(exc))[:1000])
            atomic_json(storage/"f40_samples.json",{"samples":summary,"reference_source":reference_id})
            raise
        try:
            scene=await asyncio.to_thread(build_f40,id,scale,intent)
            scene.planning["module_reference_views"]=module_reference_views(scene,state)
            scene.planning["official_build_references"]=guide_records(storage,request)
            atomic_json(directory/"scene.json",scene.model_dump())
            progress("assembly:modules",55,scene_hash=scene.digest(),module_hashes=scene.module_hashes())
            report=await asyncio.to_thread(validate_scene,scene,progress=progress)
            report["reference_consistency"]={"status":"unverified","model_findings":intent["reference_conflicts"],
                "reference_source":reference_id,"supplemented_views":intent.get("supplemented_views",[]),
                "unresolved_views":intent.get("unresolved_reference_views",[]),"budget_issue":intent.get("reference_budget_issue")}
            atomic_json(directory/"scene.json",scene.model_dump())
            atomic_json(directory/"quality_report.json",report)
            progress("exporting",85)
            result=await asyncio.to_thread(export_scene,scene,directory,report,progress)
            progress("acceptance",100,scene_hash=scene.digest(),module_hashes=scene.module_hashes(),exported=True)
            async with async_session() as db:
                design=await db.get(Design,uuid.UUID(id))
                design.status="draft";design.error_message=None;design.parts_count=len(scene.parts);design.steps_count=len(scene.steps);design.difficulty="Expert"
                design.file_io_path=f"{id}/model.io";design.file_ldr_path=f"{id}/model.ldr";design.file_pdf_path=f"{id}/instructions.pdf"
                design.metadata_={"workflow_version":"assembly_v3","quality_level":"experimental_draft","quality_report":report,"reference_source":reference_id}
                await replace_design_parts(db,design.id,result["parts_data"]);await db.commit()
            jobs.finish(id,owner,"draft")
        except Exception as exc:
            from app.agents.security import mask_api_key
            error=mask_api_key(str(exc))[:1000]
            jobs.finish(id,owner,"failed",error)
            async with async_session() as db:
                design=await db.get(Design,uuid.UUID(id));design.status="failed";design.error_message=error;await db.commit()
            item.update(status="failed",error=error)
            atomic_json(storage/"f40_samples.json",{"samples":summary,"reference_source":reference_id})
            raise
        item.update(status="draft",parts=len(scene.parts),steps=len(scene.steps),gates=report["gates"],
                    collisions=len(report["collisions"]),disconnected=len(report["connectivity"]["disconnected_parts"]))
        atomic_json(storage/"f40_samples.json",{"samples":summary,"reference_source":reference_id})
        # Reuse the newly generated common detail sheets for the next scale.
        source=directory;manifest=json.loads((source/"references"/"manifest.json").read_text(encoding="utf-8"))
        print(json.dumps(item,ensure_ascii=False),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser();parser.add_argument("--references",required=True);parser.add_argument("--resume",action="store_true")
    args=parser.parse_args();asyncio.run(main(args.references,args.resume))
