"""Resumable assembly_v3 orchestration, including best-draft preservation."""

import asyncio
import hashlib
import json
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from app.agents.models import create_text_llm
from app.agents.security import mask_api_key
from app.config import settings
from app.services.vehicle_physics import VehiclePhysicalProfile, load_profile, physical_prompt
from app.services.vehicle_research import collect_physical_profile
from app.services.reference_images import (ReferenceImageService, ReferenceShotRequest, reference_content,
    ALL_REFERENCE_VIEWS, SECTION_DETAILS, model_call, failure_details, design_directory, reference_request_hash)
from app.services.reference_images import controlled_call
from .exports import export_scene, parts_data
from .external_quality import run_external_checks
from .jobs import BudgetExceeded, JobStopped, JobStore, atomic_json
from .official_guides import guide_records, guide_content
from .recipes import build_f40
from .repair import repair_module
from .scene import AssemblyScene
from .specifications import F40_SPEC, SCALES, specifications_from_profile, physical_layout_constraints
from .validation import validate_scene
from .requirements import requirements_for_scale


class VehicleIntent(BaseModel):
    body_color_id: int = Field(default=4, ge=0)
    accent_color_id: int = Field(default=0, ge=0)
    feature_priorities: list[str] = Field(default_factory=list)
    notes: str = ""
    estimated_dimensions_mm: dict[str, float] = Field(default_factory=dict)
    reference_conflicts: list[str] = Field(default_factory=list, description="Only exact conflicting view names from: " + ", ".join(ALL_REFERENCE_VIEWS))
    reference_conflict_notes: list[str] = Field(default_factory=list)
    detail_reference_requests: list[ReferenceShotRequest] = Field(default_factory=list, max_length=4,
        description="Only genuinely missing or unreadable details needed by assembly modules. Specify view, exact focus, useful camera angles and module names. Do not request views already clear in the full manifest.")
    unsupported_modifications: list[str] = Field(default_factory=list)


async def review_references(state: dict, request: dict) -> dict:
    """Review detail sheets in bounded batches, including the overview anchor."""
    images = state.get("reference_images", [])
    overview = [r for r in images if r["view"] == "overview"]
    details = [r for r in images if r["view"] != "overview"]
    official = guide_content(state.get("storage_path") or settings.storage_path, request)
    outputs = []
    reviews = state.setdefault("reference_review_batches", {})
    for start in range(0, max(1, len(details)), 3):
        batch = state | {"reference_images": overview + details[start:start+3]}
        messages = [
            SystemMessage(content="Plan visual priorities for a physical LEGO assembly. Inspect exterior, engine, seats, interior and panel opening states. Code selects real connectors and all transforms. List conflicting exact view names in reference_conflicts, explain discrepancies in reference_conflict_notes. Suggest detail_reference_requests only for missing or unreadable visual information, specifying exact focus, camera angles and affected modules. Other images in the full manifest are reviewed in separate batches: do not call a view missing solely because it is absent from this batch. For F40, rear access must show the whole rear body clamshell and wing moving together, not only a transparent window. Generated pictures cannot establish measurements, LEGO connections or mechanical feasibility. Only requested modifications that cannot be implemented belong in unsupported_modifications. Do not include general missing validation there. For non-F40 vehicles estimate length,width,height,wheelbase in mm and label estimates in notes."),
            HumanMessage(content=reference_content(batch, json.dumps({"vehicle": request, "reference_brief": state.get("reference_brief", {}),
                "physical_specifications": physical_prompt(state.get("physical_specifications", {})),
                "scale_requirements": state.get("scale_requirements") or requirements_for_scale(state.get("scale", "1:38")),
                "available_views": [r["view"] for r in images], "reviewed_batch": [r["view"] for r in batch["reference_images"]]}), max_image_size=1024)
                + (official if start == 0 else [])),
        ]
        # Cache the exact multimodal payload. A corrected sheet, official page,
        # request, prompt or model invalidates only the batches using that input.
        signature = hashlib.sha256(json.dumps({"version": 1, "model": settings.openai_model,
            "messages": [m.content for m in messages]}, sort_keys=True).encode()).hexdigest()
        if signature in reviews:
            outputs.append(VehicleIntent.model_validate(reviews[signature]).model_dump())
            continue
        result = await model_call(lambda: create_text_llm(max_tokens=4096).with_structured_output(VehicleIntent).ainvoke(messages),
                                  state, "text", "reference_consistency", 37)
        outputs.append(result.model_dump())
        reviews[signature] = result.model_dump()
        if state.get("checkpoint_progress"):
            state["checkpoint_progress"]("reference_consistency", 37, reference_review_batches=reviews)
    merged = dict(outputs[0])
    for key in ("feature_priorities", "reference_conflicts", "reference_conflict_notes", "unsupported_modifications"):
        merged[key] = list(dict.fromkeys(item for output in outputs for item in output.get(key, [])))
    merged["reference_conflicts"] = [v for v in merged["reference_conflicts"] if v in ALL_REFERENCE_VIEWS]
    merged["notes"] = "\n".join(dict.fromkeys(o["notes"] for o in outputs if o["notes"]))
    shots = {}
    for output in outputs:
        for shot in output.get("detail_reference_requests", []):
            if shot["view"] not in shots:
                shots[shot["view"]] = shot
            else:
                old = shots[shot["view"]]
                old["focus"] = (old["focus"] + "; " + shot["focus"])[:700]
                old["angles"] = list(dict.fromkeys(old["angles"] + shot["angles"]))[:5]
                old["modules"] = list(dict.fromkeys(old["modules"] + shot["modules"]))[:8]
    merged["detail_reference_requests"] = list(shots.values())[:4]
    return merged


async def refine_references(state: dict, request: dict, intent: dict) -> dict:
    """One bounded, resumable round of targeted corrections and extra detail views."""
    shots = intent.get("detail_reference_requests", [])
    conflicts = [v for v in intent.get("reference_conflicts", []) if v in {r["view"] for r in state["reference_images"]}]
    wanted = set(conflicts) | {shot["view"] for shot in shots}
    if not wanted:
        return intent
    targeted = state | {"requested_reference_shots": shots, "reference_corrections": {
        view: "Reconcile this view with the overview and the exact vehicle. " + "; ".join(intent.get("reference_conflict_notes", []))[:1600]
        for view in conflicts}}
    budget_issue = None
    try:
        state.update(await ReferenceImageService().generate(targeted, only=wanted))
    except BudgetExceeded as exc:
        budget_issue = str(exc)
        manifest = json.loads((design_directory(state) / "references" / "manifest.json").read_text(encoding="utf-8"))
        state.update(reference_images=manifest["images"])
    except Exception:
        state["call_failure"] = targeted.get("call_failure")
        raise
    completed = [r["view"] for r in state["reference_images"] if r["view"] in wanted and
                 r.get("shot_request_hash") == reference_request_hash(targeted, r["view"])]
    result = dict(intent)
    if completed:
        try:
            result = await review_references(state, request)
        except BudgetExceeded as exc:
            budget_issue = str(exc)
    result.update(reference_refinement_requests=shots, regenerated_views=[v for v in completed if v in conflicts],
        supplemented_views=[v for v in completed if v not in conflicts],
        unresolved_reference_views=sorted(wanted - set(completed)), reference_budget_issue=budget_issue)
    return result


def module_reference_views(scene: AssemblyScene, state: dict) -> dict[str, list[str]]:
    available = {r["view"] for r in state.get("reference_images", [])}
    return {m.id: sorted(available & {"overview", m.id, *SECTION_DETAILS.get(
        "wheels" if m.id.startswith("wheel_") and m.id != "wheel_mounts" else m.id, set())}) for m in scene.modules}


class AssemblyPipeline:
    def __init__(self, storage: str | Path | None = None):
        self.storage = Path(storage or settings.storage_path)
        self.jobs = JobStore(self.storage)

    async def generate(self, design_id: str, make: str, model: str, year: int, scale: str = "1:38", **kwargs) -> dict:
        if scale not in SCALES:
            raise ValueError("1:8 and 1:10 precision generation is not yet validated")
        request = dict(design_id=design_id, make=make, model=model, year=year, scale=scale,
                       custom_request=kwargs.get("custom_request", ""), vehicle_features=kwargs.get("vehicle_features") or {},
                       source_image_path=kwargs.get("source_image_path", ""), mod_ids=kwargs.get("mod_ids") or [])
        self.jobs.ensure(design_id, request)
        owner = self.jobs.claim(design_id)
        if not owner:
            job = self.jobs.get(design_id)
            return self.result(design_id, job["state"])
        directory = self.storage / design_id
        checkpoint = self.jobs.get(design_id)["data"]["checkpoint"]
        def progress(stage, percent, **updates):
            self.jobs.checkpoint(design_id, owner, stage, percent, **updates)
            checkpoint.update(updates)
            state["active_stage"] = stage
        state = request | {"storage_path": str(self.storage), "workflow_version": "assembly_v3", "consume_call": lambda kind: self.jobs.consume(design_id, owner, kind),
                           "scale_requirements": checkpoint.get("scale_requirements") or requirements_for_scale(scale),
                           "checkpoint_progress": progress,
                           "reference_review_batches": checkpoint.get("reference_review_batches", {})}
        try:
            progress("starting", 1)
            if not checkpoint.get("scale_requirements") and not checkpoint.get("references") and not checkpoint.get("scene_hash"):
                progress("starting", 1, scale_requirements=state["scale_requirements"])
            # Snapshot source data so resume cannot silently alter proportions or
            # invalidate existing references after a shared cache is updated.
            physical = checkpoint.get("physical_specifications")
            if physical is None and not checkpoint.get("references"):
                progress("vehicle_research", 2)
                profile = load_profile(make, model, year, self.storage)
                if not profile.sources:
                    profile = await controlled_call(collect_physical_profile(make, model, year, storage=self.storage),
                                                    state, "vehicle_research", 2)
                physical = profile.resolved(scale)
                atomic_json(directory / "physical_specifications.json", physical)
                progress("vehicle_research", 3, physical_specifications=physical)
            elif physical is None:
                # Existing paid references keep their inputs until explicitly rebuilt.
                physical = VehiclePhysicalProfile(make=make, model=model, year=year).resolved(scale)
            state["physical_specifications"] = physical
            if not checkpoint.get("references"):
                state.update(await ReferenceImageService().generate(state))
                progress("reference_consistency", 36, references=True)
            else:
                manifest = json.loads((directory / "references" / "manifest.json").read_text(encoding="utf-8"))
                state.update(reference_images=manifest["images"], reference_brief=manifest["brief"])
            intent = checkpoint.get("intent")
            if not intent:
                intent = await review_references(state, request)
                progress("planning", 42, intent=intent)
            if not checkpoint.get("references_refined"):
                intent = await refine_references(state, request, intent)
                progress("planning", 44, intent=intent, references_refined=True)
            atomic_json(directory / "visual_plan.json", intent)
            scene_path = directory / "scene.json"
            if checkpoint.get("scene_hash") and scene_path.is_file():
                scene = AssemblyScene.model_validate_json(scene_path.read_text(encoding="utf-8"))
                if scene.digest() != checkpoint["scene_hash"]:
                    raise ValueError("Scene checkpoint hash mismatch; preserved files require explicit recovery")
            else:
                f40 = make.lower() == "ferrari" and model.lower().replace(" ", "") == "f40"
                spec = specifications_from_profile(physical, dict(F40_SPEC) if f40 else None,
                                                   intent.get("estimated_dimensions_mm"))
                scene = await asyncio.to_thread(build_f40, design_id, scale, intent, dict(make=make, model=model, year=year), spec,
                                                requirements=state["scale_requirements"])
                scene.planning["physical_constraints"] = physical_layout_constraints(physical)
                if not f40:
                    scene.planning["recipe"] = "experimental-coupe-scaffold"
                atomic_json(scene_path, scene.model_dump())
                progress("assembly:modules", 55, scene_hash=scene.digest(), module_hashes=scene.module_hashes())
            report = await asyncio.to_thread(validate_scene, scene, progress=progress)
            atomic_json(scene_path, scene.model_dump())
            progress("validation", 70, scene_hash=scene.digest(), module_hashes=scene.module_hashes())
            repair_history = checkpoint.get("repair_history", [])
            retry_module = checkpoint.get("retry_module")
            candidates = [retry_module] if retry_module else sorted({m for issue in report["issues"] for m in issue["modules"]})
            module_ids={m.id for m in scene.modules}
            for module in candidates:
                if module not in module_ids:
                    raise ValueError("Unknown repair module")
                for _ in range(settings.assembly_module_repair_limit):
                    if not self.jobs.reserve_repair(design_id, owner, module):
                        break
                    progress("repair:" + module, 76)
                    scene, result = await asyncio.to_thread(repair_module, scene, module)
                    repair_history.append(result)
                    atomic_json(scene_path, scene.model_dump())
                    progress("repair:" + module, 80, scene_hash=scene.digest(), module_hashes=scene.module_hashes(), repair_history=repair_history)
                    if result["status"] != "improved":
                        break
            scene.planning["reference_findings"] = intent.get("reference_conflicts", [])
            scene.planning["module_reference_views"] = module_reference_views(scene, state)
            scene.planning["official_build_references"] = guide_records(self.storage, request)
            report = await asyncio.to_thread(validate_scene, scene, progress=progress)
            report["repair_history"] = repair_history
            report["reference_consistency"] = {"status": "unverified", "model_findings": intent.get("reference_conflicts", []),
                "notes": intent.get("reference_conflict_notes", []), "regenerated_views": intent.get("regenerated_views", []),
                "budget_issue": intent.get("reference_budget_issue"), "reviewed_views": [r["view"] for r in state["reference_images"]]}
            report["reference_consistency"].update(requested_details=intent.get("reference_refinement_requests", []),
                supplemented_views=intent.get("supplemented_views", []), unresolved_views=intent.get("unresolved_reference_views", []))
            if request["custom_request"] and intent.get("unsupported_modifications"):
                report["unsupported_modifications"] = intent["unsupported_modifications"]
                report["gates"]["customization"] = "failed"
            atomic_json(scene_path, scene.model_dump())
            atomic_json(directory / "quality_report.json", report)
            progress("exporting", 86, scene_hash=scene.digest(), repair_history=repair_history, retry_module=None)
            await asyncio.to_thread(export_scene, scene, directory, report, progress)
            progress("external_checks", 97, scene_hash=scene.digest())
            report["external_checks"] = await asyncio.to_thread(run_external_checks, scene, directory, progress)
            atomic_json(directory / "quality_report.json", report)
            progress("acceptance", 100, scene_hash=scene.digest(), module_hashes=scene.module_hashes(), exported=True)
            # Publication requires independent acceptance; a draft remains useful and downloadable.
            terminal = "completed" if report["precision_verified"] else "draft"
            self.jobs.finish(design_id, owner, terminal)
            return self.result(design_id, terminal)
        except JobStopped:
            status = self.jobs.get(design_id)["state"]
            if status in ("paused","cancelled"):
                self.jobs.finish(design_id, owner, status)
            return self.result(design_id, status)
        except Exception as exc:
            failure = state.get("call_failure") or failure_details(exc, state.get("active_stage", "starting"))
            error = failure["message"]
            status = "draft" if scene_path_exists(directory) else "failed"
            self.jobs.finish(design_id, owner, status, error, failure)
            return self.result(design_id, status, error)

    def result(self, id: str, status: str, error: str = "") -> dict:
        directory = self.storage / id
        scene = AssemblyScene.model_validate_json((directory / "scene.json").read_text(encoding="utf-8")) if (directory / "scene.json").is_file() else None
        report = json.loads((directory / "quality_report.json").read_text(encoding="utf-8")) if (directory / "quality_report.json").is_file() else None
        job=self.jobs.get(id)
        return {"status": status, "error_message": error or (job or {}).get("data",{}).get("error",""), "parts_count": len(scene.parts) if scene else 0,
                "parts_data": parts_data(scene) if scene else [], "difficulty": "Expert", "steps_count": len(scene.steps) if scene else 0,
                **{key: f"{id}/{name}" if (directory / name).is_file() else "" for key, name in
                   (("file_io_path", "model.io"), ("file_ldr_path", "model.ldr"), ("file_pdf_path", "instructions.pdf"))},
                "metadata": {"workflow_version": "assembly_v3", "quality_level": "precision_verified" if report and report["precision_verified"] else "experimental_draft",
                             "quality_report": report, "requested_scale": scene.scale if scene else None}}


def scene_path_exists(directory: Path) -> bool:
    return (directory / "scene.json").is_file()
