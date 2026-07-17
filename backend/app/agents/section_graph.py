# backend/app/agents/section_graph.py
"""Section loop subgraph — runs 5 body sections sequentially.

For each section: build_section → deterministic_check → inspect_ldr → llm_evaluate
                 → (retry or advance).

Invoked by the main design_graph (Task 10).
"""
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph

from app.agents.models import create_text_llm
from app.agents.section_schemas import (
    DeterministicCheckResult, SectionEvaluation, SectionParts, SectionPartPlacement,
)
from app.agents.section_tools import search_parts, get_brand_feature, validate_placement
from app.agents.state import DesignState
from app.services.lego_parts_knowledge import CAR_PARTS_CATALOG
from app.services.section_evaluator import build_eval_prompt, EVAL_SYSTEM_PROMPT
from app.services.section_inspector import inspect_current_state
from app.services.section_planner import compute_section_bounds, SECTIONS_ORDER


MAX_SECTION_RETRIES = 2
SECTION_TOOLS = [search_parts, get_brand_feature, validate_placement]


async def build_section_node(state: DesignState) -> dict:
    """LLM ReAct agent generates parts for the current section."""
    section = state["current_section"]
    plan = state.get("plan", {})
    section_bounds = plan.get("section_bounds", [])
    current_bounds = next(
        (b for b in section_bounds if b.get("section") == section), None
    )

    # Committed parts summary (top-5 per section by semantic_label)
    committed_summary = _summarize_committed(state.get("committed_parts", []))

    feedback = state.get("section_feedback", [])
    feedback_text = "\n".join(f"- {f}" for f in feedback) if feedback else "(none)"

    prompt = f"""## Current Section: {section}
Bounds: {current_bounds}

## Design Plan
- Body color: {plan.get('body_color_id')}, Accent: {plan.get('accent_color_id')}
- Highlight: {plan.get('section_highlights', {}).get(section, '')}

## Previous Sections Summary (committed)
{committed_summary}

## Previous Retry Feedback (if any)
{feedback_text}

## Your Task
Generate SectionParts for the {section} section. Use tools to:
1. search_parts — find appropriate part_num by usage
2. get_brand_feature — get real-world coordinates for brand features
3. validate_placement — verify each (x,y,z,part_num,section) before committing

Output a SectionParts object with parts list. X must be >= 0 (auto-mirrored).
"""

    llm = create_text_llm()
    llm_with_tools = llm.bind_tools(SECTION_TOOLS)

    messages: list = [
        SystemMessage(content="You are a LEGO car design expert. Generate parts for one body section at a time."),
        HumanMessage(content=prompt),
    ]

    # Manual ReAct loop (bounded) — matches customization_graph.py pattern.
    # create_react_agent from langchain.agents is unavailable in this env.
    max_iterations = 4
    for _ in range(max_iterations):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            break
        for tc in tool_calls:
            tool_fn = _find_section_tool(tc["name"])
            if tool_fn is None:
                tool_msg = ToolMessage(
                    content=f"Error: unknown tool {tc['name']!r}",
                    tool_call_id=tc["id"],
                )
            else:
                try:
                    result = tool_fn.invoke(tc["args"])
                    content = result if isinstance(result, str) else str(result)
                    tool_msg = ToolMessage(content=content, tool_call_id=tc["id"])
                except Exception as exc:
                    tool_msg = ToolMessage(
                        content=f"Error executing {tc['name']}: {exc}",
                        tool_call_id=tc["id"],
                    )
            messages.append(tool_msg)

    # Parse last message as SectionParts — ReAct returns final answer in last message
    last_msg = messages[-1].content
    # Use structured output to coerce
    structured_llm = llm.with_structured_output(SectionParts)
    section_parts = await structured_llm.ainvoke([
        SystemMessage(content="Convert the design into SectionParts schema."),
        HumanMessage(content=last_msg),
    ])

    return {
        "pending_parts": [p.model_dump() for p in section_parts.parts],
    }


def _find_section_tool(name: str):
    """Look up a tool by name from SECTION_TOOLS."""
    for t in SECTION_TOOLS:
        if t.name == name:
            return t
    return None


def _summarize_committed(committed: list[dict]) -> str:
    """Top-5 parts per section_label for prompt brevity."""
    if not committed:
        return "(empty)"
    # Group by semantic_label, take first per group
    seen = {}
    for p in committed:
        label = p.get("semantic_label", "detail")
        if label not in seen:
            seen[label] = p
    lines = []
    for label, p in list(seen.items())[:5]:
        lines.append(f"- {label}: {p['part_num']} @ ({p['x']},{p['y']},{p['z']}) color={p['color_id']}")
    return "\n".join(lines)


async def deterministic_check_node(state: DesignState) -> dict:
    """Code-only checks: part existence, bounds, X>=0, color, overlap."""
    pending = state.get("pending_parts", [])
    plan = state.get("plan", {})
    section = state["current_section"]
    bounds_list = plan.get("section_bounds", [])
    bounds = next((b for b in bounds_list if b.get("section") == section), None)

    valid_part_nums = {p.part_num for p in CAR_PARTS_CATALOG}
    issues = []
    failed_indices = []

    for i, p in enumerate(pending):
        if p["part_num"] not in valid_part_nums:
            issues.append(f"part_{i}: {p['part_num']} not in catalog")
            failed_indices.append(i)
            continue
        if p["x"] < 0:
            issues.append(f"part_{i}: x={p['x']} < 0")
            failed_indices.append(i)
            continue
        if bounds:
            z_min, z_max = bounds["z_range"]
            y_min, y_max = bounds["y_range"]
            if not (z_min <= p["z"] <= z_max):
                issues.append(f"part_{i}: z={p['z']} out of [{z_min},{z_max}]")
                failed_indices.append(i)
                continue
            if not (y_min <= p["y"] <= y_max):
                issues.append(f"part_{i}: y={p['y']} out of [{y_min},{y_max}]")
                failed_indices.append(i)
                continue

    # Overlap check (same part_num within ±20 LDU)
    for i in range(len(pending)):
        for j in range(i + 1, len(pending)):
            if pending[i]["part_num"] == pending[j]["part_num"]:
                dx = abs(pending[i]["x"] - pending[j]["x"])
                dy = abs(pending[i]["y"] - pending[j]["y"])
                dz = abs(pending[i]["z"] - pending[j]["z"])
                if dx < 20 and dy < 20 and dz < 20:
                    issues.append(f"overlap: part_{i} and part_{j} same {pending[i]['part_num']} within 20 LDU")
                    if i not in failed_indices:
                        failed_indices.append(i)

    passed = len(failed_indices) == 0
    result = DeterministicCheckResult(
        passed=passed, issues=issues, failed_part_indices=failed_indices,
    )
    # Store in inspection_snapshot (DesignState has no check_result field;
    # inspect_ldr_node overwrites this when the check passes and routing
    # continues to inspect_ldr).
    return {"inspection_snapshot": result.model_dump()}


async def inspect_ldr_node(state: DesignState) -> dict:
    """LDR roundtrip + distribution stats (no ZIP packaging)."""
    inspection = inspect_current_state(
        committed_parts=state.get("committed_parts", []),
        pending_parts=state.get("pending_parts", []),
        section=state["current_section"],
        make=state["make"], model=state["model"], year=state["year"],
    )
    return {"inspection_snapshot": inspection.model_dump()}


async def llm_evaluate_node(state: DesignState) -> dict:
    """LLM evaluates the section against the 6-item checklist."""
    llm = create_text_llm()
    structured_llm = llm.with_structured_output(SectionEvaluation)

    plan = state.get("plan", {})
    inspection = state.get("inspection_snapshot", {})
    section = state["current_section"]

    prompt = build_eval_prompt(plan=plan, inspection=inspection, section=section)
    evaluation = await structured_llm.ainvoke([
        SystemMessage(content=EVAL_SYSTEM_PROMPT),
        HumanMessage(content=prompt),
    ])
    return {"evaluation_result": evaluation.model_dump()}


def _route_after_eval(state: DesignState) -> Literal["build_section", "advance_section"]:
    """Retry if needed and within limit; otherwise advance."""
    eval_result = state.get("evaluation_result", {})
    needs_retry = eval_result.get("needs_retry", False)
    retry_count = state.get("section_retry_count", 0)

    if needs_retry and retry_count < MAX_SECTION_RETRIES:
        return "build_section"
    return "advance_section"


def deterministic_check_route(state: DesignState) -> Literal["build_section", "inspect_ldr"]:
    """If deterministic check failed, retry build; otherwise inspect.

    Reads the check result from ``inspection_snapshot`` (where
    deterministic_check_node stores its DeterministicCheckResult) — DesignState
    has no dedicated ``check_result`` field.
    """
    check = state.get("inspection_snapshot", {}) or {}
    if not check.get("passed", False):
        return "build_section"
    return "inspect_ldr"


async def advance_section_node(state: DesignState) -> dict:
    """Commit pending → committed, increment section_index, clear retry state."""
    committed = list(state.get("committed_parts", []))
    committed.extend(state.get("pending_parts", []))

    next_index = state["section_index"] + 1
    next_section = SECTIONS_ORDER[next_index] if next_index < len(SECTIONS_ORDER) else "done"

    return {
        "committed_parts": committed,
        "pending_parts": [],
        "section_retry_count": 0,
        "section_feedback": [],
        "section_index": next_index,
        "current_section": next_section,
        "progress": f"{next_index}/{len(SECTIONS_ORDER)}",
    }


async def retry_section_node(state: DesignState) -> dict:
    """Clear pending, append retry guidance to feedback, increment retry count."""
    eval_result = state.get("evaluation_result", {})
    guidance = eval_result.get("retry_guidance", "")
    # Check issues live in inspection_snapshot (set by deterministic_check_node)
    check_snapshot = state.get("inspection_snapshot", {}) or {}
    check_issues = check_snapshot.get("issues", [])

    feedback = list(state.get("section_feedback", []))
    if guidance:
        feedback.append(f"eval feedback: {guidance}")
    for issue in check_issues:
        feedback.append(f"check failed: {issue}")

    return {
        "pending_parts": [],
        "section_feedback": feedback,
        "section_retry_count": state.get("section_retry_count", 0) + 1,
    }


def build_section_loop_graph():
    """Compile and return the section-loop StateGraph."""
    graph = StateGraph(DesignState)

    graph.add_node("build_section", build_section_node)
    graph.add_node("deterministic_check", deterministic_check_node)
    graph.add_node("inspect_ldr", inspect_ldr_node)
    graph.add_node("llm_evaluate", llm_evaluate_node)
    graph.add_node("retry_section", retry_section_node)
    graph.add_node("advance_section", advance_section_node)

    graph.add_edge(START, "build_section")
    graph.add_edge("build_section", "deterministic_check")
    graph.add_conditional_edges(
        "deterministic_check",
        deterministic_check_route,
        {"build_section": "retry_section", "inspect_ldr": "inspect_ldr"},
    )
    graph.add_edge("retry_section", "build_section")
    graph.add_edge("inspect_ldr", "llm_evaluate")
    graph.add_conditional_edges(
        "llm_evaluate",
        _route_after_eval,
        {"build_section": "retry_section", "advance_section": "advance_section"},
    )
    graph.add_edge("advance_section", END)

    return graph.compile()
