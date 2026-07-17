"""LangGraph customization graph (Phase 4).

Replaces the legacy `CustomizationService.customize()` single-shot LLM path
with a multi-node StateGraph using a proper ReAct loop:

    START → build_customization_prompt → customization_agent (ReAct)
              → finalize_customization → build_ldraw → create_io
              → build_parts_data → END

Nodes:
- `build_customization_prompt`: deterministic — assembles base parts + LDraw +
  customization request + parts catalog + colors
- `customization_agent`: LLM node — ReAct loop lets the model query the parts
  catalog for replacement options before finalizing the customization
- `finalize_customization`: LLM node — `with_structured_output(CustomizedDesign)`
  produces a complete modified parts list with `change: kept/added/modified`
  annotations
- `build_ldraw`: reuses `StudioDesignGenerator._build_ldraw`
- `create_io`: `StudioService.create_studio_file()` + saves .io/.ldr
- `build_parts_data`: reuses `StudioDesignGenerator._build_parts_data`

The graph's output dict matches the return format so callers
(`CustomizationService.customize()`, Celery tasks) don't need to change.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agents.models import create_text_llm
from app.agents.state import CustomizationState
from app.agents.tools import DESIGN_TOOLS
from app.config import settings
from app.services.customization_service import CustomizationService
from app.services.lego_parts_knowledge import CAR_PARTS_CATALOG, CAR_COLORS
from app.services.studio_design_generator import StudioDesignGenerator
from app.services.studio_service import StudioService


# ── Pydantic output models ──


class CustomizedPartPlacement(BaseModel):
    """A single part in a customized LEGO car design."""

    part_num: str = Field(..., description="LDraw part filename (e.g., '3024.dat')")
    bricklink_id: str = Field("", description="BrickLink part ID")
    color_id: int = Field(..., description="LDraw color ID")
    color_name: str = Field("", description="Human-readable color name")
    x: float = Field(..., description="X position in LDU")
    y: float = Field(..., description="Y position in LDU")
    z: float = Field(..., description="Z position in LDU")
    rotation: str = Field(
        "1 0 0 0 1 0 0 0 1",
        description="9 space-separated rotation matrix values",
    )
    quantity: int = Field(1, description="Quantity of this exact part+color+position combo")
    change: Literal["kept", "added", "modified"] = Field(
        "kept",
        description="Whether this part was kept from original, newly added, or modified",
    )


class CustomizedDesign(BaseModel):
    """Complete LLM-customized LEGO car design (structured output schema)."""

    modification_summary: str = Field(..., description="Brief explanation of what was changed and why.")
    added_parts_count: int = Field(..., description="Number of NEW parts added (not in original).")
    removed_parts_count: int = Field(..., description="Number of parts REMOVED from original.")
    total_parts: int = Field(..., description="Total parts in the modified design (sum of all quantities).")
    parts: list[CustomizedPartPlacement] = Field(
        ..., description="COMPLETE modified parts list — all parts in the final model."
    )


# ── System prompt (kept in sync with legacy CustomizationService.SYSTEM_PROMPT) ──

SYSTEM_PROMPT = CustomizationService.SYSTEM_PROMPT


# ── Graph nodes ──


async def build_customization_prompt_node(state: CustomizationState) -> dict:
    """Assemble the user prompt: base car + base parts + LDraw + customization request + catalog."""
    car_info = state["car_info"]
    base_parts_summary = state["base_parts_summary"]
    base_ldr_content = state["base_ldr_content"]
    customization_request = state["customization_request"]

    # Parts catalog
    parts_lines = [
        f"  - {p.part_num} (BL:{p.bricklink_id}) | {p.name} | {p.size} | {p.usage}"
        for p in CAR_PARTS_CATALOG
    ]
    parts_catalog_text = "\n".join(parts_lines)

    # Colors
    colors_lines = [
        f"  - ID {cid}: {cname} ({chex})"
        for cid, (cname, chex) in sorted(CAR_COLORS.items())
    ]
    colors_text = "\n".join(colors_lines)

    prompt = f"""## Base Car
{car_info}

## Base Design (existing LEGO model parts)

{base_parts_summary}

## Full Base LDraw File (reference)
```
{base_ldr_content[:8000]}  // truncated for space
```

## Customization Request
{customization_request}

## Available Parts Catalog
{parts_catalog_text}

## Available Colors
{colors_text}

Modify the base design to implement the customization request. You have tools
available to query the parts catalog for replacement options — use them to
ensure the parts you choose exist before finalizing the output.

Include ALL parts — every part from the original that should be kept, plus all
new/modified parts. Mark each part's `change` field as kept/added/modified."""

    return {
        "parts_catalog_text": parts_catalog_text,
        "colors_text": colors_text,
        "prompt": prompt,
        "messages": [],
    }


async def customization_agent_node(state: CustomizationState) -> dict:
    """ReAct loop: LLM may call DESIGN_TOOLS to find replacement parts.

    Bounded to 4 iterations. The accumulated message history is then passed
    to `finalize_customization_node` for structured output.
    """
    llm = create_text_llm()
    llm_with_tools = llm.bind_tools(DESIGN_TOOLS)

    messages: list = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=state["prompt"]),
    ]

    max_iterations = 4
    for _ in range(max_iterations):
        response = await llm_with_tools.ainvoke(messages)
        messages.append(response)
        tool_calls = getattr(response, "tool_calls", None) or []
        if not tool_calls:
            break
        for tc in tool_calls:
            tool_fn = _find_tool(tc["name"])
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

    return {"messages": messages}


async def finalize_customization_node(state: CustomizationState) -> dict:
    """Produce the structured `CustomizedDesign` output from the accumulated context.

    Uses only the system prompt + user prompt + final instruction — does NOT
    pass the ReAct tool-call messages (they confuse the structured output parser).
    """
    llm = create_text_llm()
    structured_llm = llm.with_structured_output(CustomizedDesign)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=state["prompt"]),
        HumanMessage(
            content=(
                "Now produce your final structured output. Include the COMPLETE "
                "modified parts list — all kept parts, all added parts, all modified "
                "parts. Mark each with change=kept/added/modified. "
                "CRITICAL: Only output parts with X >= 0 (right half + center). "
                "The system auto-mirrors every part with X > 0 to create the left side."
            )
        ),
    ]

    design = await structured_llm.ainvoke(messages)
    return {"design_output": design.model_dump()}


async def build_ldraw_node(state: CustomizationState) -> dict:
    """Build LDraw content from the structured customized design dict."""
    generator = StudioDesignGenerator()
    data = state["design_output"]

    # Parse make/model from car_info for the LDraw header
    car_info = state.get("car_info") or ""
    make_label = "Custom"
    model_label = "Design"
    parts_info = car_info.split()
    if len(parts_info) >= 2:
        make_label = parts_info[0]
        model_label = " ".join(parts_info[1:])

    ldr_content = generator._build_ldraw(data, make_label, model_label, 0)
    return {"ldr_content": ldr_content}


async def create_io_node(state: CustomizationState) -> dict:
    """Wrap LDraw in a Studio .io ZIP and persist .io + .ldr files."""
    ldr_content = state["ldr_content"]
    car_info = state.get("car_info") or "Custom Design"
    design_id = state["design_id"]
    data = state["design_output"]

    storage = Path(settings.storage_path)
    design_dir = storage / str(design_id)
    design_dir.mkdir(parents=True, exist_ok=True)

    studio_file = StudioService.create_studio_file(
        ldr_content=ldr_content,
        name=car_info,
        description=data.get("modification_summary", ""),
    )

    io_path = design_dir / "model.io"
    studio_file.save(io_path)

    ldr_path = design_dir / "model.ldr"
    ldr_path.write_text(ldr_content, encoding="utf-8")

    return {
        "io_path": str(io_path.relative_to(storage)),
        "ldr_path": str(ldr_path.relative_to(storage)),
    }


async def build_parts_data_node(state: CustomizationState) -> dict:
    """Deduplicate parts and assemble the final return dict (matches legacy format)."""
    generator = StudioDesignGenerator()
    data = state["design_output"]
    parts_data = generator._build_parts_data(data)
    total_parts = data.get("total_parts", len(data.get("parts", [])))

    return {
        "parts_data": parts_data,
        "parts_count": total_parts,
        "difficulty": generator._estimate_difficulty(total_parts),
        "modification_summary": data.get("modification_summary", ""),
        "added_parts": data.get("added_parts_count", 0),
        "removed_parts": data.get("removed_parts_count", 0),
        "metadata": {
            "generator": "langgraph",
            "type": "customization",
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "status": "completed",
    }


# ── Error handling ──
# The customization graph does not have a retry loop (unlike the design graph).
# If an LLM node raises, the exception propagates to `CustomizationService.customize()`,
# which wraps the whole invocation in try/except and returns a failure dict.


# ── Helpers ──


def _find_tool(name: str):
    """Look up a tool by name from DESIGN_TOOLS."""
    for t in DESIGN_TOOLS:
        if t.name == name:
            return t
    return None


# ── Graph builder ──


def build_customization_graph():
    """Compile and return the customization StateGraph.

    The graph is async; call via `await graph.ainvoke(initial_state)`.
    """
    graph = StateGraph(CustomizationState)

    graph.add_node("build_customization_prompt", build_customization_prompt_node)
    graph.add_node("customization_agent", customization_agent_node)
    graph.add_node("finalize_customization", finalize_customization_node)
    graph.add_node("build_ldraw", build_ldraw_node)
    graph.add_node("create_io", create_io_node)
    graph.add_node("build_parts_data", build_parts_data_node)

    graph.add_edge(START, "build_customization_prompt")
    graph.add_edge("build_customization_prompt", "customization_agent")
    graph.add_edge("customization_agent", "finalize_customization")
    graph.add_edge("finalize_customization", "build_ldraw")
    graph.add_edge("build_ldraw", "create_io")
    graph.add_edge("create_io", "build_parts_data")
    graph.add_edge("build_parts_data", END)

    return graph.compile()
