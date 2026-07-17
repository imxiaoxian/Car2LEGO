# backend/app/agents/design_graph.py
"""LangGraph v2 — section-by-section design workflow.

Replaces the legacy template-first single-shot approach with:
    START → plan_design → section_loop → final_validate → create_io → END

Section loop (in section_graph.py) runs 5 sections sequentially with
deterministic_check + inspect_ldr + llm_evaluate + retry per section.

Env var DESIGN_WORKFLOW=legacy falls back to design_graph_legacy.py.
"""
from datetime import datetime, timezone
from pathlib import Path

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel

from app.agents.models import create_text_llm
from app.agents.section_graph import build_section_loop_graph
from app.agents.section_schemas import DesignPlan
from app.agents.state import DesignState
from app.config import settings
from app.services.design_fallback import fallback_single_shot
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


async def plan_design_node(state: DesignState) -> dict:
    """LLM produces DesignPlan — global plan, hard constraint for 5 sections."""
    llm = create_text_llm()
    structured_llm = llm.with_structured_output(DesignPlan)

    make, model, year = state["make"], state["model"], state["year"]
    scale = validate_scale(state.get("scale"))

    # Pre-compute section bounds based on body_style classification
    body_style = classify_car_to_template(make)
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

## Your Task
Produce a DesignPlan for this car. The plan locks:
- body_color_id (primary brand color)
- accent_color_id (trim/secondary)
- overall_dimensions (LDU)
- section_bounds (use the pre-computed ones above)
- section_highlights (one sentence per section: chassis/front/body/rear/wheels)
- brand_features_to_render (e.g., ['rear_wing', 'pop_up_headlight'])

The plan is the HARD CONSTRAINT for the 5 subsequent section generators.
"""
    plan = await structured_llm.ainvoke([
        SystemMessage(content=PLAN_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])

    return {
        "plan": plan.model_dump(),
        "current_section": "chassis",
        "section_index": 0,
        "committed_parts": [],
        "pending_parts": [],
        "section_feedback": [],
        "section_retry_count": 0,
        "progress": "0/5",
    }


async def run_section_loop_node(state: DesignState) -> dict:
    """Invoke the section loop subgraph and merge results into state."""
    section_graph = build_section_loop_graph()
    result = await section_graph.ainvoke(state)
    # Merge returned state keys
    return {
        "committed_parts": result.get("committed_parts", []),
        "section_index": result.get("section_index", 5),
        "current_section": result.get("current_section", "done"),
        "progress": result.get("progress", "5/5"),
    }


async def final_validate_node(state: DesignState) -> dict:
    """Validate the full design. On failure, locate section + retry or fallback."""
    committed = state.get("committed_parts", [])

    wheels = [p for p in committed if p["part_num"] in WHEEL_PART_NUMBERS]
    slopes = [p for p in committed if p["part_num"] in SLOPE_PART_NUMBERS]
    windshield = [p for p in committed if p["color_id"] in TRANSPARENT_COLORS and p["y"] >= 64]

    issues = []
    if len(wheels) < 4:
        issues.append(f"wheels_section: only {len(wheels)} wheels (need >=4)")
    if len(slopes) < 2:
        issues.append(f"front_or_rear: only {len(slopes)} slopes (need >=2)")
    if len(windshield) == 0:
        issues.append("body: no transparent windshield at Y>=64")

    if not issues:
        return {"final_validation_issues": [], "status": "completed"}

    # Try fallback (simpler than per-section retry for v1)
    fallback_result = await fallback_single_shot(state)
    return {
        "final_validation_issues": issues,
        "status": fallback_result.get("status", "completed"),
        "committed_parts": fallback_result.get("design_output", {}).get("parts", committed),
        "fallback_used": True,
        "metadata": fallback_result.get("metadata", {}),
    }


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
    }

    generator = StudioDesignGenerator()
    ldr_content = generator._build_ldraw(data, state["make"], state["model"], state["year"])

    storage = Path(settings.storage_path)
    design_dir = storage / str(state["design_id"])
    design_dir.mkdir(parents=True, exist_ok=True)

    studio_file = StudioService.create_studio_file(
        ldr_content=ldr_content,
        name=f"{state['make']} {state['model']} {state['year']}",
        description=design_notes,
    )
    io_path = design_dir / "model.io"
    studio_file.save(io_path)

    ldr_path = design_dir / "model.ldr"
    ldr_path.write_text(ldr_content, encoding="utf-8")

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
    total_parts = len(data["parts"])

    metadata = {
        "generator": "langgraph_v2_section",
        "studio_version": "2.26.6",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "workflow": "fallback_legacy" if state.get("fallback_used") else "v2_section",
        "progress": state.get("progress", "5/5"),
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
    # app.agents.security module does not exist in this codebase; use plain
    # truncation to keep error messages short in metadata.
    err = state.get("error_message", "")
    masked = err[:200] + "..." if len(err) > 200 else err
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
    }


def build_design_graph():
    """Compile and return the v2 section-workflow StateGraph."""
    graph = StateGraph(DesignState)

    graph.add_node("plan_design", plan_design_node)
    graph.add_node("run_section_loop", run_section_loop_node)
    graph.add_node("final_validate", final_validate_node)
    graph.add_node("create_io", create_io_node)
    graph.add_node("build_parts_data", build_parts_data_node)

    graph.add_edge(START, "plan_design")
    graph.add_edge("plan_design", "run_section_loop")
    graph.add_edge("run_section_loop", "final_validate")
    graph.add_edge("final_validate", "create_io")
    graph.add_edge("create_io", "build_parts_data")
    graph.add_edge("build_parts_data", END)

    return graph.compile()
