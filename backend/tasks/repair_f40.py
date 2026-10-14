"""Rebuild a design using its existing references; preserve the original artifact."""
import asyncio
import json
import os
import shutil
import sys
import uuid
from pathlib import Path

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./image_guided_dev.db"
os.environ["DATABASE_URL_SYNC"] = "sqlite:///./image_guided_dev.db"
os.environ["DEBUG"] = "false"
os.environ["REDIS_URL"] = ""

from langchain_core.messages import HumanMessage, SystemMessage
from app.agents.design_graph import build_design_graph
from app.agents import design_graph
from app.agents.models import create_text_llm
from app.agents.security import mask_api_key
from app.config import settings
from app.database import async_session
from app.models.design import Design
import app.models  # register relationships
from app.services.reference_images import ReferenceImageService, VehicleReferenceBrief, reference_content, write_progress
from app.services.constrained_assembly import build_assembly
from app.services.section_planner import compute_section_bounds, SECTIONS_ORDER
from tasks.generation import _update_design

SOURCE_ID = "47d81760-d7f9-4844-9f0d-074529212c04"


async def main():
    identifier = sys.argv[1] if len(sys.argv) > 1 else str(uuid.uuid4())
    uuid.UUID(identifier)
    root = Path(settings.storage_path)
    directory = root / identifier
    directory.mkdir(exist_ok=True)
    if not (directory / "references").exists():
        shutil.copytree(root / SOURCE_ID / "references", directory / "references")
    manifest_path = directory / "references" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    saved_path = directory / "repair_state.json"
    saved = json.loads(saved_path.read_text(encoding="utf-8")) if saved_path.exists() else {}
    state = dict(design_id=identifier, make="Ferrari", model="F40", year=1990, scale="1:38",
                 storage_path=str(root), reference_images=manifest["images"], vehicle_features={},
                 custom_request="", mod_ids=[], status="processing", messages=[])
    print(f"NEW_DESIGN={identifier}", flush=True)
    if manifest.get("repair_source") == SOURCE_ID:
        brief_data = dict(manifest["brief"])
        if brief_data["body_style"] not in ("sports_car", "sedan", "suv", "pickup", "hatchback", "f1_race", "other"):
            brief_data["body_style"] = "sports_car"
        brief = VehicleReferenceBrief(**brief_data)
    else:
        brief = await create_text_llm().with_structured_output(VehicleReferenceBrief, method="function_calling").ainvoke([
            SystemMessage(content="Describe the exact car from these references, preserving its model identity and distinctive visual features."),
            HumanMessage(content=reference_content(state, "Target vehicle: 1990 Ferrari F40. Describe its appearance.")),
        ])
    manifest["brief"] = brief.model_dump()
    manifest["repair_source"] = SOURCE_ID
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    state["reference_brief"] = brief.model_dump()
    async def cached_references(self, input_state):
        return dict(reference_images=manifest["images"], reference_brief=brief.model_dump())
    ReferenceImageService.generate = cached_references
    if saved.get("plan"):
        plan = dict(saved["plan"])
        plan["section_bounds"] = [b.model_dump() for b in compute_section_bounds("1:38", brief.body_style)]
        plan["overall_dimensions"]["length"] = 384
        plan["overall_dimensions"]["width"] = 176
        plan["section_highlights"]["wheels"] = "Four black 6015 tyres with light-gray 6014 rims; axles at X=74,Y=35,Z=60/260, total native mesh width 176 LDU."
        plan["plan_notes"] = "Image-guided stylized prototype. Native collision geometry checked; physical clutch still requires Studio inspection."
        completed = saved.get("completed_sections", [])
        recipe = build_assembly(plan)
        expected = [{**p, "step": i + 1} for i, name in enumerate(completed) for p in recipe[name]]
        retained = saved.get("committed_parts", [])
        if expected != retained:
            completed, retained = [], []
        async def resume_plan(input_state):
            index = len(completed)
            return dict(plan=plan, committed_parts=retained, pending_parts=[], completed_sections=completed,
                        section_index=index, current_section=SECTIONS_ORDER[index] if index < 5 else "done",
                        section_failure="", section_feedback=[], section_retry_count=0, status="processing",
                        progress=f"{index}/5", evaluation_result=None, inspection_snapshot=None)
        if len(completed) < 5:
            design_graph.plan_design_node = resume_plan
            print(f"REUSE_PLAN VERIFIED_SECTIONS={len(completed)}", flush=True)
    async with async_session() as db:
        source = await db.get(Design, uuid.UUID(SOURCE_ID))
        existing = await db.get(Design, uuid.UUID(identifier))
        if existing:
            existing.status = "processing"
            existing.error_message = None
        else:
            db.add(Design(id=uuid.UUID(identifier), car_id=source.car_id, match_level=4, scale="1:38",
                          status="processing", parent_design_id=source.id,
                          metadata_={"repair_source": SOURCE_ID, "references_reused": True}))
        await db.commit()
    try:
        async for update in build_design_graph().astream(state, config={"recursion_limit": 256}, stream_mode="updates"):
            for node, values in update.items():
                if not values:
                    continue
                state.update(values)
                snapshot = {k: v for k, v in state.items() if k != "messages"}
                saved_path.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2), encoding="utf-8")
                print(f"STAGE={node} STATUS={state.get('status')} PROGRESS={state.get('progress', '')}", flush=True)
                if values.get("section_failure"):
                    print(values["section_failure"], flush=True)
    except Exception as exc:
        state.update(status="failed", error_message=mask_api_key(str(exc))[:1000])
    result = dict(status=state["status"], parts_count=state.get("parts_count", 0),
                  parts_data=state.get("parts_data", []), difficulty=state.get("difficulty", "Medium"),
                  file_io_path=state.get("io_path"), file_ldr_path=state.get("ldr_path"),
                  metadata=state.get("metadata", {}), error_message=state.get("error_message"))
    await _update_design(identifier, result)
    write_progress(state, state["status"], 100 if state["status"] == "completed" else 0)
    (directory / "repair_result.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(dict(id=identifier, status=state["status"], parts_count=state.get("parts_count"), error=state.get("error_message")), ensure_ascii=False), flush=True)


if __name__ == "__main__":
    asyncio.run(main())
