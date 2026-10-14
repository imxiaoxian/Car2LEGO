# backend/app/agents/design_graph.py
"""LangGraph v2 — section-by-section design workflow.

Replaces the legacy template-first single-shot approach with:
    START → plan_design → section_loop → final_validate → create_io → END

Section loop (in section_graph.py) runs 5 sections sequentially with
deterministic_check + inspect_ldr + llm_evaluate + retry per section.

Env var DESIGN_WORKFLOW=legacy falls back to design_graph_legacy.py.
"""
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.agents.models import create_text_llm
from app.agents.security import mask_api_key
from app.agents.section_graph import build_section_loop_graph
from app.agents.section_schemas import DesignPlan
from app.agents.state import DesignState
from app.config import settings
from app.services.reference_images import (
    ReferenceImageService, reference_content, design_directory, write_progress,
)
from app.services.io_validator import (
    SLOPE_PART_NUMBERS, TRANSPARENT_COLORS, WHEEL_PART_NUMBERS,
)
from app.services.section_planner import compute_section_bounds
from app.services.studio_design_generator import StudioDesignGenerator
from app.services.studio_service import StudioService
from app.services.studio_templates import classify_car_to_template, validate_scale


PLAN_SYSTEM_PROMPT = """You are a master LEGO car designer.

Given a target car, produce a DesignPlan that locks:
1. body_color_id + accent_color_id (brand colors)
2. overall_dimensions (LDU)
3. section_bounds — physical Z/Y boundary for each of 5 sections
4. section_highlights — one-sentence design focus per section
5. brand_features_to_render — feature IDs to replicate

The 5 sections are processed sequentially: chassis → front → body → rear → wheels.
Your plan is the HARD CONSTRAINT for all 5 subsequent LLM calls.
"""


class PlanInput(BaseModel):
    """Lightweight wrapper for plan_design prompt inputs."""
    make: str
    model: str
    year: int
    scale: str
    flagship_metadata: dict | None = None


async def prepare_references_node(state: DesignState) -> dict:
    write_progress(state, "reference_images", 5)
    return await ReferenceImageService().generate(state)


async def plan_design_node(state: DesignState) -> dict:
    """LLM produces DesignPlan — global plan, hard constraint for 5 sections."""
    llm = create_text_llm()
    structured_llm = llm.with_structured_output(DesignPlan, method="function_calling")

    make, model, year = state["make"], state["model"], state["year"]
    scale = validate_scale(state.get("scale"))

    # Pre-compute section bounds based on body_style classification
    body_style = state.get("reference_brief", {}).get("body_style") or classify_car_to_template(make)
    section_bounds = compute_section_bounds(scale=scale, body_style=body_style)

    flagship = state.get("flagship_metadata") or {}

    prompt = f"""## Target Car
{year} {make} {model}
Scale: {scale}
Body style: {body_style}

## Pre-computed Section Bounds (use these — they're physical constraints)
{[b.model_dump() for b in section_bounds]}

## Brand Context
- Body style template: {body_style}
- Flagship specs: {flagship}
- Reference appearance: {state.get('reference_brief', {})}
- Input photo features: {state.get('vehicle_features', {})}
- Requested modifications: {state.get('custom_request', '')} {state.get('mod_ids', [])}

## Your Task
Produce an appearance plan for a stylized eight-wide assembly. Code supplies
a 320-LDU chassis with axles at Z=60/260, 384-LDU total body length
(rear light faces at Z=-24, front lip ends at Z=360) and
176-LDU width including tyres. Available components: wedge hood, rectangular
headlights, side sills, six-wide glazing, tiled roof, rear grille/louvers,
round tail lamps and optional fixed rear wing. Select highlights achievable
with these components; exact logos, pop-up mechanisms and measured vehicle
dimensions are not supported by this prototype. The plan locks:
- body_color_id (primary brand color)
- accent_color_id (trim/secondary)
- overall_dimensions (LDU)
- section_bounds (use the pre-computed ones above)
- section_highlights (one sentence per section: chassis/front/body/rear/wheels)
- brand_features_to_render (e.g., ['rear_wing', 'pop_up_headlight'])
- assembly_profile: low_coupe for sports cars, boxy for tall cabins
- rear_wing: true only when the vehicle has a prominent rear wing

The plan is the HARD CONSTRAINT for the 5 subsequent section generators.
"""
    plan = await structured_llm.ainvoke([
        SystemMessage(content=PLAN_SYSTEM_PROMPT),
        HumanMessage(content=reference_content(state, prompt)),
    ])

    # Boundaries are code-owned constraints, never replaced by inferred image dimensions.
    plan.section_bounds = section_bounds
    plan.overall_dimensions = {"length": 384, "width": 176,
                               "height": 144 if plan.assembly_profile == "boxy" else 120 if plan.rear_wing else 104}
    plan.section_highlights["wheels"] = "Four black 6015 tyres with light-gray 6014 rims; axles at X=74,Y=35,Z=60/260, total native mesh width 176 LDU."
    write_progress(state, "planning", 35)

    return {
        "plan": {**plan.model_dump(), "placement_engine": "constrained"},
        "current_section": "chassis",
        "section_index": 0,
        "committed_parts": [],
        "pending_parts": [],
        "section_feedback": [],
        "section_retry_count": 0,
        "completed_sections": [],
        "section_failure": "",
        "status": "processing",
        "progress": "0/5",
    }


async def run_section_loop_node(state: DesignState) -> dict:
    """Invoke the section loop subgraph and merge results into state."""
    section_graph = build_section_loop_graph()
    result = await section_graph.ainvoke(state, config={"recursion_limit": 256})
    # Merge returned state keys
    return {
        "committed_parts": result.get("committed_parts", []),
        "section_index": result.get("section_index", 5),
        "current_section": result.get("current_section", "done"),
        "progress": result.get("progress", "5/5"),
        "completed_sections": result.get("completed_sections", []),
        "section_failure": result.get("section_failure", ""),
    }


async def final_validate_node(state: DesignState) -> dict:
    """Validate the full design. On failure, locate section + retry or fallback."""
    committed = state.get("committed_parts", [])

    wheel_positions = set()
    for p in committed:
        if p["part_num"] in WHEEL_PART_NUMBERS:
            wheel_positions.add((p["x"], p["z"]))
            if p["x"] > 0.1:
                wheel_positions.add((-p["x"], p["z"]))
    slopes = [p for p in committed if p["part_num"] in SLOPE_PART_NUMBERS]
    windshield = [p for p in committed if p["color_id"] in TRANSPARENT_COLORS and p["y"] >= 64]

    issues = []
    if state.get("section_failure"):
        issues.append(state["section_failure"])
    if state.get("completed_sections") != ["chassis", "front", "body", "rear", "wheels"]:
        issues.append("section workflow did not complete all five sections")
    if len(wheel_positions) < 4:
        issues.append(f"wheels_section: only {len(wheel_positions)} wheel positions (need >=4)")
    slope_count = sum(2 if p["x"] > .1 else 1 for p in slopes)
    if slope_count < 2:
        issues.append(f"front_or_rear: only {slope_count} slopes (need >=2)")
    if len(windshield) == 0 and state.get("reference_brief", {}).get("body_style") != "f1_race":
        issues.append("body: no transparent windshield at Y>=64")

    if state.get("plan", {}).get("placement_engine") == "constrained":
        from app.services.assembly_geometry import collision_issues
        try:
            issues.extend(collision_issues(committed))
        except ValueError as exc:
            issues.append(str(exc))

    if not issues:
        return {"final_validation_issues": [], "status": "completed"}

    return {"status": "failed", "final_validation_issues": issues, "fallback_used": False,
            "error_message": "装配质量检查未通过：" + "; ".join(issues[:8])}


async def create_io_node(state: DesignState) -> dict:
    """Build LDraw + Studio .io and persist."""
    if state.get("status") == "failed":
        return {}

    parts = state.get("committed_parts", [])
    design_notes = state.get("plan", {}).get("plan_notes", "")
    data = {
        "parts": parts,
        "design_notes": design_notes,
        "body_color_id": state.get("plan", {}).get("body_color_id", 4),
        "total_parts": len(parts),
        "positive_y_is_height": True,
    }

    generator = StudioDesignGenerator()
    ldr_content = generator._build_ldraw(data, state["make"], state["model"], state["year"])

    design_dir = design_directory(state)
    storage = design_dir.parent

    studio_file = StudioService.create_studio_file(
        ldr_content=ldr_content,
        name=f"{state['make']} {state['model']} {state['year']}",
        description=design_notes,
    )
    io_path = design_dir / "model.io"
    studio_file.save(io_path)

    from app.services.io_validator import validate_io_file

    report = validate_io_file(io_path)
    if report.has_errors:
        return {"status": "failed", "error_message": "; ".join(i.message for i in report.errors[:10])}

    ldr_path = design_dir / "model.ldr"
    ldr_path.write_text(ldr_content, encoding="utf-8")
    if state.get("plan", {}).get("placement_engine") == "constrained":
        from app.services.assembly_preview import render_preview
        render_preview(parts, design_dir / "assembly_preview.png")
        render_preview(parts, design_dir / "assembly_preview_rear.png", view="rear")

    return {
        "io_path": str(io_path.relative_to(storage)),
        "ldr_path": str(ldr_path.relative_to(storage)),
        "ldr_content": ldr_content,
        "body_color_id": data["body_color_id"],
    }


async def build_parts_data_node(state: DesignState) -> dict:
    """Deduplicate parts + assemble final return dict."""
    if state.get("status") == "failed":
        return _failed_return(state)

    generator = StudioDesignGenerator()
    data = {
        "parts": state.get("committed_parts", []),
        "design_notes": state.get("plan", {}).get("plan_notes", ""),
    }
    parts_data = generator._build_parts_data(data)
    total_parts = sum(p["quantity"] for p in parts_data)

    metadata = {**(state.get("metadata") or {}),
        "generator": "langgraph_v2_section",
        "studio_version": "2.26.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": "fallback_legacy" if state.get("fallback_used") else "v2_section",
        "progress": state.get("progress", "5/5"),
        "reference_images": state.get("reference_images", []),
        "reference_brief": state.get("reference_brief", {}),
        "text_model": settings.openai_model,
        "image_model": settings.openai_image_model,
        "placement_engine": state.get("plan", {}).get("placement_engine", "llm"),
        "quality_level": "stylized_prototype",
        "collision_check": "studio_native_boxes",
        "assembly_dimensions_ldu": state.get("plan", {}).get("overall_dimensions", {}),
    }
    if state.get("final_validation_issues"):
        metadata["final_validation_issues"] = state["final_validation_issues"]

    return {
        "parts_data": parts_data,
        "parts_count": total_parts,
        "difficulty": generator._estimate_difficulty(total_parts),
        "design_notes": data["design_notes"],
        "metadata": metadata,
        "status": "completed",
    }


def _failed_return(state: DesignState) -> dict:
    err = state.get("error_message", "")
    masked = mask_api_key(err)[:500]
    return {
        "parts_data": [],
        "parts_count": 0,
        "difficulty": "Easy",
        "design_notes": "",
        "metadata": {
            "generator": "langgraph_v2_section",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "error": masked,
        },
        "status": "failed",
        "error_message": masked,
    }


def build_design_graph():
    """Compile and return the v2 section-workflow StateGraph."""
    graph = StateGraph(DesignState)

    graph.add_node("prepare_references", prepare_references_node)
    graph.add_node("plan_design", plan_design_node)
    graph.add_node("run_section_loop", run_section_loop_node)
    graph.add_node("final_validate", final_validate_node)
    graph.add_node("create_io", create_io_node)
    graph.add_node("build_parts_data", build_parts_data_node)

    graph.add_edge(START, "prepare_references")
    graph.add_edge("prepare_references", "plan_design")
    graph.add_edge("plan_design", "run_section_loop")
    graph.add_edge("run_section_loop", "final_validate")
    graph.add_edge("final_validate", "create_io")
    graph.add_edge("create_io", "build_parts_data")
    graph.add_edge("build_parts_data", END)

    return graph.compile()
