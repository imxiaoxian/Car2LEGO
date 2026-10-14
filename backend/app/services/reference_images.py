"""Generate synthetic vehicle references and attach them to multimodal prompts."""

import base64
import asyncio
import hashlib
import io
import json
import shutil
import uuid
from contextlib import ExitStack
from pathlib import Path
from typing import Literal

import httpx
from openai import AsyncOpenAI, APIConnectionError, APIStatusError
from PIL import Image
from pydantic import BaseModel, Field
from langchain_core.messages import HumanMessage, SystemMessage

from app.agents.models import create_text_llm, openai_base_url
from app.config import settings
from app.agents.security import mask_api_key
from .assembly_v3.requirements import requirements_for_scale


REFERENCE_VIEWS = {
    "overview": "A clean reference sheet: front three-quarter, rear three-quarter, exact side profile, front, rear and top views of the SAME complete car. Show all views fully, without cropping.",
    "chassis": "Underside and side profile reference sheet. Show wheelbase, axle positions, ground clearance and visible chassis silhouette. Do not invent hidden mechanical structures.",
    "front": "Front three-quarter and straight front detail views. Clearly show grille, headlights, hood contour, bumper, air intakes and front wheel arches.",
    "body": "Side profile, roof/top and cabin detail views. Clearly show window shape, windshield angle, roofline, doors, side panels and mirrors.",
    "rear": "Rear three-quarter and straight rear detail views. Clearly show taillights, rear bumper, diffuser, exhaust outlets, spoiler and rear body contour.",
    "wheels": "Full side profile with both axle positions plus sharp close-ups of rim, tire, wheel arch and visible brake details. Keep the wheel design consistent with the overview.",
}

DETAIL_VIEWS = {
    "engine_bay": "Engine bay with the engine cover fully open: overhead, rear three-quarter and close-up views. Show engine placement, intake plenums, hoses, exhaust routing and the surrounding frame. Preserve the exact engine for this year and variant.",
    "engine_details": "Macro reference sheet of the engine: intake plenum, cylinder banks, piping, exhaust outlets, visible belts and engine-bay trim. Show only plausible visible features; hidden construction is uncertain.",
    "cockpit": "Interior reference sheet photographed through the opened door and windshield: dashboard straight-on, driver footwell, center console and rear cabin. Show steering wheel, gauges, pedals, gear lever, trim and material colors.",
    "seats": "Seat reference sheet: front and rear three-quarter close-ups of both front seats, seatback side profile, headrest, harness openings, upholstery and seat-to-floor placement. Keep the upholstery consistent with the cockpit.",
    "doors": "Same door in three states: closed, half open and fully open, plus close-ups of door jamb, visible hinge, latch, sill and inner door panel. Preserve the real opening direction and hinge location for this vehicle. Show both sides; do not substitute scissor or butterfly doors for conventional doors.",
    "hood_opening": "Front hood and rear engine cover each shown closed, half open and fully open. Include side close-ups of visible hinges, frame attachment and clearance to adjacent panels. Keep the panels' size and opening direction identical across states. Do not invent concealed linkages.",
    "steering": "Reference sheet of visible front-wheel steering: wheels centered, turned left and turned right, with close-up views of steering wheel, front wheel arch clearance and visible hub/steering attachments. Hidden linkage is uncertain; no fabricated mechanical schematic.",
    "suspension": "Reference sheet of the visible suspension and front steering: neutral, steering turned and wheel at compressed and extended ride positions. Include wheel arch, hub, control-arm and spring close-ups where visible. Preserve the vehicle's actual suspension layout; inferred hidden structure must not look like measured engineering evidence.",
    "side_intakes": "Macro side and three-quarter views of side air intakes, NACA ducts, grille mesh, sill and rear-quarter vents. Match the same year, side profile and trim across all views.",
    "lights": "Close-up reference sheet of front and rear lamp clusters from straight and three-quarter angles, preserving lenses, housings, pop-up headlamp states where present and adjacent grille geometry.",
    "dashboard": "Straight-on and oblique close-ups of the dashboard, instrument cluster, steering wheel, center console, pedals and gear selector; preserve the exact interior trim and driving side.",
    "door_hinges": "Close-ups of each door jamb and visible hinge from outside, inside and along the sill. Show the SAME door at closed, half-open and fully-open positions, keeping the door panel and body in frame to establish its opening envelope.",
    "hood_hinges": "Side and oblique close-ups of the front bonnet and rear access panel or clamshell at closed, half-open and fully-open positions. Show which panels move together, the visible pivot region and clearance to wheels, cabin and surrounding bodywork.",
    "underbody": "Underside, low side and oblique close-ups of visible floor, front/rear subframes, exhaust routing and suspension attachment regions. Do not invent cutaway internals or present guessed dimensions as measurements.",
    "rear_seats": "Rear cabin viewed through open doors and from the front seats, plus close-ups of rear-seat shape, headrests, belts, trim and legroom. Only show rear seats if present on this exact vehicle.",
    "cargo_bay": "Front and rear storage or service compartments with their access panels open, including straight-on and oblique detail views. Preserve the exact vehicle's compartment layout and powertrain; do not substitute an invented combustion engine for an electric drivetrain.",
}
ALL_REFERENCE_VIEWS = {**REFERENCE_VIEWS, **DETAIL_VIEWS}
SECTION_DETAILS = {"front": {"hood_opening", "hood_hinges", "lights", "cargo_bay"}, "body": {"cockpit", "seats", "doors", "door_hinges", "dashboard", "rear_seats", "side_intakes"},
    "rear": {"engine_bay", "engine_details", "hood_opening", "hood_hinges", "lights"},
    "chassis": {"steering", "suspension", "hood_opening", "underbody"}, "wheels": {"steering", "suspension"},
    "engine": {"engine_bay", "engine_details"}, "cockpit": {"cockpit", "seats", "dashboard", "rear_seats", "doors"},
    "doors": {"body", "cockpit", "doors", "door_hinges"},
    "wheel_mounts": {"chassis", "wheels", "underbody", "steering", "suspension"},
    "body_frame": {"body", "chassis", "door_hinges", "hood_hinges", "underbody"},
    "details": {"front", "rear", "lights", "side_intakes", "engine_details"},
    "front_hood": {"front", "hood_opening", "hood_hinges", "cargo_bay"},
    "engine_cover": {"rear", "engine_bay", "hood_opening", "hood_hinges"}}


class ReferenceShotRequest(BaseModel):
    view: str = Field(pattern="^(" + "|".join(ALL_REFERENCE_VIEWS) + ")$")
    focus: str = Field(min_length=1, max_length=700)
    angles: list[str] = Field(default_factory=list, max_length=5)
    reason: str = Field(default="", max_length=500)
    modules: list[str] = Field(default_factory=list, max_length=8)


def requested_shots(state: dict) -> dict[str, dict]:
    shots = {}
    for data in state.get("requested_reference_shots", []):
        shot = ReferenceShotRequest.model_validate(data).model_dump()
        shots[shot["view"]] = shot
    return shots


def reference_request_hash(state: dict, view: str) -> str | None:
    shot = requested_shots(state).get(view)
    correction = state.get("reference_corrections", {}).get(view, "")
    return hashlib.sha256(json.dumps({"shot": shot, "correction": correction}, sort_keys=True).encode()).hexdigest() if shot or correction else None


def vehicle_reference_constraints(state: dict, view: str) -> str:
    if state.get("make", "").lower() == "ferrari" and state.get("model", "").lower().replace(" ", "") == "f40":
        return ("F40 identity constraints: two bucket seats and a sparse cockpit; conventional front-hinged doors. "
                "The rear access is the complete rear body clamshell, including the rear window, rear fender bodywork "
                "and rear wing moving together; do not show only a small transparent window lifting independently. "
                "Show the complete front bonnet assembly where opened. Keep the fixed cockpit and chassis stationary. "
                "Visible hinge details remain synthetic and must be checked against real vehicle sources.")
    return "Preserve the exact vehicle's powertrain, seating layout and panel opening type; unknown hidden details remain uncertain."


def reference_plan(state: dict, brief: dict | None = None) -> dict[str, str]:
    if state.get("workflow_version") != "assembly_v3":
        return dict(REFERENCE_VIEWS)
    policy = state.get("scale_requirements") or requirements_for_scale(state.get("scale", "1:38"))
    plan = {name: ALL_REFERENCE_VIEWS[name] for name in policy["reference_views"]}
    for view in (brief or {}).get("detail_priorities", []):
        if view in DETAIL_VIEWS:
            plan[view] = DETAIL_VIEWS[view]
    for view, shot in requested_shots(state).items():
        plan[view] = ALL_REFERENCE_VIEWS[view] + "\nTargeted focus: " + shot["focus"] + "\nRequired angles: " + "; ".join(shot["angles"])
    return plan


class VehicleReferenceBrief(BaseModel):
    body_style: Literal["sports_car", "sedan", "suv", "pickup", "hatchback", "f1_race", "other"]
    paint: str
    visual_description: str
    distinctive_features: list[str] = Field(default_factory=list)
    detail_priorities: list[str] = Field(default_factory=list, description="Optional priority view names: engine_details, side_intakes, lights. Choose based on the exact vehicle's visible features.")


def design_directory(state: dict) -> Path:
    storage = Path(state.get("storage_path") or settings.storage_path).resolve()
    directory = (storage / str(state["design_id"])).resolve()
    if directory.parent != storage:
        raise ValueError("Invalid design directory")
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def write_progress(state: dict, stage: str, progress: int) -> None:
    directory = design_directory(state)
    temp = directory / "generation_status.tmp"
    temp.write_text(json.dumps({"stage": stage, "progress": progress}), encoding="utf-8")
    temp.replace(directory / "generation_status.json")


def reference_identity(state: dict) -> dict:
    identity = {key: state.get(key) for key in ("make", "model", "year", "vehicle_features", "custom_request", "mod_ids")}
    if state.get("source_image_path"):
        identity["source_digest"] = hashlib.sha256(Path(state["source_image_path"]).read_bytes()).hexdigest()
    identity.update(image_model=settings.openai_image_model, size=settings.image_size, quality=settings.image_quality,
                    reference_version=2)
    if state.get("physical_specifications", {}).get("measurements"):
        identity["physical_specifications"] = state["physical_specifications"]
    return identity


def reference_fingerprint(state: dict) -> str:
    return hashlib.sha256(json.dumps(reference_identity(state), sort_keys=True).encode()).hexdigest()


async def controlled_call(call, state: dict, stage: str, percent: int):
    """Poll task controls while the provider works, without issuing another call."""
    task = asyncio.create_task(call)
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=10)
            if state.get("checkpoint_progress"):
                state["checkpoint_progress"](stage, percent)
        return await task
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


def transient_model_error(exc: Exception) -> bool:
    return isinstance(exc, (APIConnectionError, httpx.TransportError)) or (
        isinstance(exc, APIStatusError) and (exc.status_code in (408, 429) or exc.status_code >= 500))


def failure_details(exc: Exception, stage: str, kind: str | None = None, attempt: int = 1) -> dict:
    def clean(value):
        text = str(value)
        if settings.openai_api_key:
            text = text.replace(settings.openai_api_key, "[redacted]")
        return mask_api_key(text)[:400]
    causes = []
    cause = exc.__cause__
    while cause and len(causes) < 3:
        causes.append({"type": type(cause).__name__, "message": clean(cause)})
        cause = cause.__cause__
    return {"stage": stage, "call_kind": kind, "exception_type": type(exc).__name__,
            "message": clean(exc), "causes": causes, "attempts": attempt,
            "retryable": transient_model_error(exc)}


async def model_call(factory, state: dict, kind: str, stage: str, percent: int):
    """Count every provider attempt and retry transient text failures only."""
    attempts = max(1, min(5, settings.assembly_text_retry_attempts)) if kind == "text" else 1
    for attempt in range(1, attempts + 1):
        if state.get("checkpoint_progress"):
            state["checkpoint_progress"](stage, percent)
        if state.get("consume_call"):
            state["consume_call"](kind)
        try:
            return await controlled_call(factory(), state, stage, percent)
        except Exception as exc:
            from .assembly_v3.jobs import JobStopped, BudgetExceeded
            if isinstance(exc, (JobStopped, BudgetExceeded)):
                raise
            if attempt == attempts or not transient_model_error(exc):
                state["call_failure"] = failure_details(exc, stage, kind, attempt)
                raise
            await controlled_call(asyncio.sleep(min(2 ** (attempt - 1), 4)), state, stage, percent)


def reference_content(state: dict, text: str, section: str | None = None, max_image_size: int = 1536) -> list[dict]:
    """Use local image bytes, never send private filesystem paths to the model."""
    content = [{"type": "text", "text": text}]
    if not state.get("reference_images"):
        return content
    directory = design_directory(state)
    for ref in state.get("reference_images", []):
        scope = "wheels" if section and section.startswith("wheel_") and section != "wheel_mounts" else section
        if section and ref["view"] not in {"overview", section, *SECTION_DETAILS.get(scope, set())}:
            continue
        path = (directory / ref["path"]).resolve()
        if not path.is_relative_to(directory):
            raise ValueError("Invalid reference image path")
        # Keep full-resolution files for the user. Bound the vision request payload
        # so six reference sheets do not exceed an upstream gateway's body limit.
        with Image.open(path) as source:
            thumbnail = source.convert("RGB")
            thumbnail.thumbnail((max_image_size, max_image_size), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            thumbnail.save(buffer, format="JPEG", quality=90)
        encoded = base64.b64encode(buffer.getvalue()).decode("ascii")
        content.extend([
            {"type": "text", "text": f"Synthetic {ref['view']} reference; use for appearance, not proof of physical LEGO connections."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{encoded}", "detail": "high"}},
        ])
    return content


class ReferenceImageService:
    async def generate(self, state: dict, regenerate: set[str] | None = None, only: set[str] | None = None) -> dict:
        directory = design_directory(state)
        refs_dir = directory / "references"
        refs_dir.mkdir(exist_ok=True)
        identity = reference_identity(state)
        source = state.get("source_image_path")
        # Exterior appearance cache stays compatible. The expanded shot plan is
        # stored separately, so adding details reuses already generated exterior views.
        fingerprint = reference_fingerprint(state)
        manifest_path = refs_dir / "manifest.json"
        manifest = {}
        if manifest_path.exists():
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest.get("fingerprint") != fingerprint:
            manifest = {"fingerprint": fingerprint, "images": []}

        brief = manifest.get("brief")
        if not brief:
            result = await model_call(lambda: create_text_llm(max_tokens=4096).with_structured_output(VehicleReferenceBrief).ainvoke([
                SystemMessage(content="Describe the exact target vehicle's visible appearance for image generation. Preserve year, variant and input photo features. Do not present inferred dimensions as measured facts."),
                HumanMessage(content=json.dumps({key: identity[key] for key in
                    ("make", "model", "year", "vehicle_features", "custom_request", "mod_ids")} | {
                        "physical_specifications": state.get("physical_specifications", {})})),
            ]), state, "text", "reference_brief", 4)
            brief = result.model_dump()
            manifest["brief"] = brief

        plan = reference_plan(state, brief)
        if only is not None:
            if not only <= set(ALL_REFERENCE_VIEWS):
                raise ValueError("Unknown reference view")
            # A scale may inherit optional views from an earlier scale. Those
            # cached views remain eligible for a targeted consistency correction.
            for view in sorted(only):
                plan.setdefault(view, ALL_REFERENCE_VIEWS[view])
        manifest["shot_plan"] = list(plan)
        manifest["detail_plan_version"] = 3 if state.get("workflow_version") == "assembly_v3" else 0
        if state.get("workflow_version") == "assembly_v3":
            policy = state.get("scale_requirements") or requirements_for_scale(state.get("scale", "1:38"))
            manifest["scale_requirements"] = {"version": policy["version"], "scale": policy["scale"]}
        shots = requested_shots(state)
        if only is not None and not only <= set(plan):
            raise ValueError("Requested reference view is not in the shot plan")
        manifest.setdefault("shot_requests", {}).update(shots)
        from .assembly_v3.jobs import atomic_json, replace_file
        atomic_json(manifest_path, manifest)

        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        async with AsyncOpenAI(
            api_key=settings.openai_api_key, base_url=openai_base_url(),
            timeout=settings.image_timeout, max_retries=0,
        ) as client:
            for index, (view, instructions) in enumerate(plan.items()):
                if only is not None and view not in only:
                    continue
                cached = next((r for r in manifest["images"] if r["view"] == view), None)
                correction = state.get("reference_corrections", {}).get(view, "")
                shot_hash = reference_request_hash(state, view)
                if cached and view not in (regenerate or set()) and (directory / cached["path"]).is_file():
                    digest = hashlib.sha256((directory / cached["path"]).read_bytes()).hexdigest()
                    if (not cached.get("sha256") or cached["sha256"] == digest) and (not shot_hash or cached.get("shot_request_hash") == shot_hash):
                        continue
                percent = 5 + round(index / len(plan) * 30)
                write_progress(state, f"reference_images:{view}", percent)
                if state.get("checkpoint_progress"):
                    state["checkpoint_progress"](f"reference_images:{view}", percent)
                prompt = (
                    f"Create a high-quality photorealistic engineering visual reference of the exact "
                    f"{state['year']} {state['make']} {state['model']}. {instructions}\n"
                    f"Locked appearance: {json.dumps(brief)}\n"
                    f"Vehicle detail constraints: {vehicle_reference_constraints(state, view)}\n"
                    f"Sourced physical geometry (mm/deg; missing data is unknown): {json.dumps(state.get('physical_specifications', {}))}\n"
                    "Use only grounded measurements to lock wheel diameters, track, door extents and glass inclination. "
                    "Do not draw measurement labels or invent hidden measurements.\n"
                    f"Correction of an observed discrepancy: {correction}\n"
                    f"Requested modifications: {state.get('custom_request', '')}; {state.get('mod_ids', [])}.\n"
                    "Neutral light background, sharp focus, realistic materials, even studio lighting. "
                    "Keep paint, trim, proportions and details identical across views. No people, scenery, "
                    "watermarks, captions or decorative effects. This is the real vehicle reference, "
                    "not a toy. The downstream builder selects real LEGO parts separately."
                )
                kwargs = dict(model=settings.openai_image_model, prompt=prompt, n=1,
                              quality=settings.image_quality, size=settings.image_size)
                anchors = []
                if source:
                    anchors.append(Path(source))
                overview = refs_dir / "overview.png"
                if view != "overview":
                    anchors.append(overview)
                # The overview locks exterior identity; related detail sheets also
                # lock upholstery, engine trim and panel states when available.
                related = {"seats": "cockpit", "doors": "cockpit", "hood_opening": "engine_bay",
                           "dashboard": "cockpit", "rear_seats": "cockpit", "door_hinges": "doors",
                           "hood_hinges": "hood_opening", "underbody": "chassis", "cargo_bay": "hood_opening",
                           "engine_details": "engine_bay", "steering": "wheels", "suspension": "chassis"}.get(view)
                if related and (refs_dir / f"{related}.png").is_file():
                    anchors.append(refs_dir / f"{related}.png")
                if view != "overview" and not any(r["view"] == "overview" for r in manifest["images"]):
                    raise ValueError("Overview reference missing")
                if anchors:
                    with ExitStack() as stack:
                        files = [stack.enter_context(path.open("rb")) for path in anchors]
                        response = await model_call(lambda: client.images.edit(image=files, **kwargs), state, "image", f"reference_images:{view}", percent)
                else:
                    response = await model_call(lambda: client.images.generate(**kwargs), state, "image", f"reference_images:{view}", percent)
                if not response.data:
                    raise ValueError(f"Image API returned no image for {view}")
                image = response.data[0]
                if image.b64_json:
                    data = base64.b64decode(image.b64_json, validate=True)
                elif image.url:
                    async with httpx.AsyncClient(timeout=60) as download:
                        result = await download.get(image.url)
                        result.raise_for_status()
                        data = result.content
                else:
                    raise ValueError(f"Image API returned an empty image for {view}")
                path = refs_dir / f"{view}.png"
                if path.is_file():
                    history = refs_dir / "history"
                    history.mkdir(exist_ok=True)
                    old_hash = hashlib.sha256(path.read_bytes()).hexdigest()
                    shutil.copy2(path, history / f"{view}-{old_hash}.png")
                temporary = refs_dir / f"{view}.{uuid.uuid4().hex}.tmp"
                with Image.open(io.BytesIO(data)) as generated:
                    generated.convert("RGB").save(temporary, format="PNG")
                replace_file(temporary, path)
                ref = {"view": view, "path": f"references/{view}.png",
                       "model": settings.openai_image_model, "synthetic": True,
                       "category": "detail" if view in DETAIL_VIEWS else "exterior", "purpose": instructions,
                       "shot_request": shots.get(view), "shot_request_hash": shot_hash,
                       "correction": correction,
                       "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                manifest["images"] = [r for r in manifest["images"] if r["view"] != view] + [ref]
                atomic_json(manifest_path,manifest)

        return {"reference_brief": brief, "reference_images": manifest["images"]}
