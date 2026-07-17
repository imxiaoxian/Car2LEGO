"""LangGraph design-generation graph (Phase 2 — Template-First Architecture).

Replaces the "LLM generates everything from scratch" approach with a
template-first design: the template provides the structural base, and the
LLM only customizes colors + adds brand-specific detail parts.

    START → classify_template → parse_template → build_prompt → customize_design (LLM)
              → merge_and_validate → build_ldraw → create_io → build_parts_data → END
                                      ↑                       |
                                      └── retry (max 1) ← (on validation failure)

Nodes:
- `classify_template`: deterministic — picks chassis template via `classify_car_to_template`
- `parse_template`: deterministic — parses template LDraw into structured parts with labels
- `build_prompt`: deterministic — assembles parsed parts JSON + catalog + colors for LLM
- `customize_design`: LLM node — `with_structured_output(DesignCustomization)` outputs
  body color + recolor rules + ≤15 extra detail parts
- `merge_and_validate`: deterministic — merges template + customization, validates
- `build_ldraw`: reuses `StudioDesignGenerator._build_ldraw`
- `create_io`: `StudioService.create_studio_file()` + saves .io/.ldr
- `build_parts_data`: reuses `StudioDesignGenerator._build_parts_data`
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from langgraph.graph import END, START, StateGraph
from pydantic import BaseModel, Field

from app.agents.models import create_text_llm
from app.agents.security import mask_api_key
from app.agents.state import DesignState
from app.config import settings
from app.database import async_session
from app.services.brand_features import get_brand_features, get_brand_profile
from app.services.car_specs_service import CarSpecsService
from app.services.lego_parts_knowledge import CAR_PARTS_CATALOG, CAR_COLORS
from app.services.mod_parts_catalog import format_mods_for_llm
from app.services.studio_design_generator import StudioDesignGenerator
from app.services.studio_service import StudioService
from app.services.studio_templates import (
    CAR_TEMPLATES,
    classify_car_to_template,
    format_scale_for_prompt,
    get_template_ldr,
    validate_scale,
)
from app.services.template_parser import ParsedPart, TemplateParser


# ── Pydantic output models ──


class LegoPartPlacement(BaseModel):
    """A single LEGO part placement (legacy schema — kept for _build_ldraw compat)."""

    part_num: str = Field(..., description="LDraw part filename (e.g., '3024.dat')")
    bricklink_id: str = Field("", description="BrickLink part ID")
    color_id: int = Field(..., description="LDraw color ID")
    color_name: str = Field("", description="Human-readable color name")
    x: float = Field(..., description="X position in LDU")
    y: float = Field(..., description="Y position in LDU")
    z: float = Field(..., description="Z position in LDU")
    rotation: str = Field("1 0 0 0 1 0 0 0 1", description="9 rotation matrix values")
    quantity: int = Field(1, description="Quantity")
    step: int = Field(1, description="Build step number")


class StudioDesign(BaseModel):
    """Legacy structured output schema — kept for _build_ldraw/_build_parts_data compat."""

    design_notes: str = Field(...)
    total_parts: int = Field(...)
    body_color_id: int = Field(...)
    parts: list[LegoPartPlacement] = Field(...)


class RecolorRule(BaseModel):
    """Recolor template parts by semantic label."""

    label: str = Field(
        ...,
        description="Semantic label: chassis, body_side, roof, wheel, headlight, "
        "taillight, bumper, windshield, wheel_arch, hood, rear_body, cabin, "
        "diffuser, chassis_frame, spoiler, rear_wing, front_wing, cargo_bed",
    )
    new_color_id: int = Field(..., description="LDraw color ID")


class ReplaceRule(BaseModel):
    """Replace template parts matching a label with a different part."""

    target_label: str = Field(
        ...,
        description="Semantic label to replace (e.g., 'headlight', 'bumper', 'nose_cone')",
    )
    new_part_num: str = Field(
        ...,
        description="New LDraw part filename (e.g., '2412b.dat' for grille tile)",
    )
    new_color_id: int = Field(..., description="New LDraw color ID")
    rotation: str = Field(
        "1 0 0 0 1 0 0 0 1",
        description="Optional new rotation matrix (9 space-separated values)",
    )


class ExtraPart(BaseModel):
    """A brand-specific detail part to add (right half only, X >= 0)."""

    part_num: str = Field(..., description="LDraw part filename (e.g., '3023.dat')")
    color_id: int = Field(..., description="LDraw color ID")
    x: float = Field(..., description="X position LDU (must be >= 0, auto-mirrored)")
    y: float = Field(..., description="Y position LDU")
    z: float = Field(..., description="Z position LDU")
    rotation: str = Field("1 0 0 0 1 0 0 0 1", description="9 rotation matrix values")
    step: int = Field(0, description="Build step (0 = auto-assign)")
    reason: str = Field("", description="Why this part was added")


class DesignCustomization(BaseModel):
    """LLM output — customization applied to the base template.

    The LLM does NOT generate the full parts list. It only outputs:
    - body_color_id + accent_color_id (brand colors)
    - recolor_rules (paint template sections by label)
    - replace_rules (swap template parts by label — e.g., replace headlight
      with a grille brick)
    - extra_parts (≤25 brand-specific detail parts)
    """

    body_color_id: int = Field(
        ..., description="Primary body color LDraw ID (e.g., Ferrari=4 Red, Lamborghini=27 Lime)"
    )
    accent_color_id: int = Field(
        ..., description="Secondary/accent color LDraw ID (e.g., Black=0 for trim)"
    )
    recolor_rules: list[RecolorRule] = Field(
        ...,
        description="Recolor rules by semantic label. Common: "
        "body_side→body_color, rear_body→body_color, roof→accent, "
        "bumper→0(Black), wheel_arch→0, hood→body_color",
    )
    replace_rules: list[ReplaceRule] = Field(
        default_factory=list,
        description="Replace template parts by semantic label. E.g., replace "
        "headlight with a grille tile, or bumper with a splitter. The new part "
        "inherits the original position; only part_num, color, and optionally "
        "rotation change.",
    )
    extra_parts: list[ExtraPart] = Field(
        default_factory=list,
        description="Brand-specific parts (max 25). E.g., rear wing, pop-up "
        "headlights, NACA ducts, side skirts, exhaust tips. Only X>=0.",
    )
    design_notes: str = Field(..., description="What colors and features were applied and why")


# ── System prompt ──

SYSTEM_PROMPT = StudioDesignGenerator.SYSTEM_PROMPT


# ── Graph nodes ──


async def classify_template_node(state: DesignState) -> dict:
    """Pick the chassis template based on car make."""
    make = state["make"]
    template_id = classify_car_to_template(make)
    template_info = CAR_TEMPLATES[template_id]
    template_ldr = get_template_ldr(make)
    return {
        "template_ldr": template_ldr,
        "template_info": {
            "id": template_id,
            "name": template_info["name"],
            "body_style": template_info.get("body_style", template_id),
            "default_color": template_info.get("default_color", 15),
            "wheel_type": template_info.get("wheel_type", "4624c00"),
        },
        "retry_count": 0,
    }


async def parse_template_node(state: DesignState) -> dict:
    """Parse template LDraw into structured parts, filter to right half."""
    template_ldr = state["template_ldr"]
    all_parts = TemplateParser.parse_ldraw(template_ldr)
    right_half = TemplateParser.filter_right_half(all_parts)
    parts_json = TemplateParser.to_json_for_prompt(right_half)
    return {
        "template_parts": [asdict_safe(p) for p in right_half],
        "template_parts_json": parts_json,
        "template_part_count": len(right_half),
    }


def asdict_safe(p: ParsedPart) -> dict:
    """Convert ParsedPart to dict (rotation as list)."""
    return {
        "part_num": p.part_num,
        "color_id": p.color_id,
        "x": p.x,
        "y": p.y,
        "z": p.z,
        "rotation": p.rotation,
        "step": p.step,
        "label": p.label,
    }


async def build_prompt_node(state: DesignState) -> dict:
    """Assemble prompt with parsed template parts JSON + car info + catalog + colors."""
    make = state["make"]
    model = state["model"]
    year = state["year"]
    scale = validate_scale(state.get("scale"))
    template_info = state["template_info"]
    template_parts_json = state.get("template_parts_json", "[]")
    template_part_count = state.get("template_part_count", 0)

    # Compute reference coordinates for the LLM
    parts_data = state.get("template_parts", [])
    parsed_parts = [
        ParsedPart(
            part_num=p["part_num"],
            color_id=p["color_id"],
            x=p["x"],
            y=p["y"],
            z=p["z"],
            rotation=p.get("rotation", [1, 0, 0, 0, 1, 0, 0, 0, 1]),
            step=p.get("step", 1),
            label=p.get("label", "detail"),
        )
        for p in parts_data
    ]
    ref = TemplateParser.compute_reference_points(parsed_parts)

    # Parts catalog
    parts_lines = [
        f"  {p.part_num} (BL:{p.bricklink_id}) | {p.name} | {p.size} | {p.usage}"
        for p in CAR_PARTS_CATALOG
    ]
    parts_catalog_text = "\n".join(parts_lines)

    # Colors
    colors_lines = [
        f"  ID {cid}: {cname} ({chex})"
        for cid, (cname, chex) in sorted(CAR_COLORS.items())
    ]
    colors_text = "\n".join(colors_lines)

    # Mods
    mod_instructions = ""
    mod_ids = state.get("mod_ids") or []
    if mod_ids:
        mod_instructions = format_mods_for_llm(mod_ids)
    custom_request = state.get("custom_request") or ""
    if custom_request:
        mod_instructions += f"\n\nAdditional customization: {custom_request}"

    scale_guidance = format_scale_for_prompt(scale)

    # Brand features
    brand_features = get_brand_features(make, model)
    brand_profile = get_brand_profile(make)
    brand_section = ""
    if brand_features:
        feature_lines = []
        for f in brand_features:
            feature_lines.append(
                f"  - {f.feature_id}: {f.description}\n"
                f"    Part: {f.part_num}, Color: {f.color_id}, "
                f"Position: ({f.x}, {f.y}, {f.z})"
            )
        brand_section = f"""
## Brand Features Reference ({make} {model})
The following brand-specific features should be replicated via extra_parts or replace_rules:
{chr(10).join(feature_lines)}

Use these coordinates as guidance when placing extra_parts."""
    elif brand_profile:
        brand_section = f"""
## Brand Reference ({make})
- Default body color: {brand_profile.default_body_color}
- Default accent color: {brand_profile.default_accent_color}
No model-specific features in library — use your knowledge of {make} {model}."""

    # Car specs from knowledge base
    car_specs_section = ""
    try:
        async with async_session() as db:
            specs = await CarSpecsService.get_specs(db, make, model, year)
            if specs:
                car_specs_section = CarSpecsService.specs_to_prompt_section(specs)
    except Exception:
        car_specs_section = ""

    prompt = f"""## Target Car
{year} {make} {model}
Template: {template_info['name']}

{scale_guidance}

## Template Structure (RIGHT HALF — {template_part_count} parts, auto-mirrored to left)
```json
{template_parts_json}
```

## Template Reference Coordinates
- Front Z={ref['front_z']}, Rear Z={ref['rear_z']}
- Roof Y={ref['roof_y']}, Chassis Y={ref['chassis_y']}
- Right edge X={ref['right_edge_x']}, Center X=0
- Front wheel Z={ref['wheel_front_z']}, Rear wheel Z={ref['wheel_rear_z']}

## Available Parts Catalog
{parts_catalog_text}

## Available LEGO Colors
{colors_text}
{brand_section}
{car_specs_section}
## Your Task
You are customizing the template to look like a {year} {make} {model}.
The template already has correct chassis, body, roof, wheels — do NOT recreate them.

1. Choose body_color_id (primary body color for this car brand)
2. Choose accent_color_id (secondary color for details/trim)
3. Write recolor_rules to paint template sections by label
4. Write replace_rules to swap template parts for better brand match (grille, lights, etc.)
5. Add extra_parts (max 25) for brand-specific features:
   - Rear wings, spoilers, diffusers
   - Pop-up headlights, fog lights, DRLs
   - Side mirrors, NACA ducts, air intakes
   - Exhaust tips, badges, trim pieces
   - F1: halo, nose_cone details, sidepod fins

Only output X >= 0 for extra_parts (system auto-mirrors).
Coordinates will be snapped to grid (X/Z multiples of 20, Y multiples of 8)."""

    if mod_instructions:
        prompt += f"\n\n## Modifications to Apply\n{mod_instructions}"

    flagship = state.get("flagship_metadata")
    if flagship:
        fs = flagship
        prompt += f"""

## Target Car Technical Specifications
- Engine: {fs.get('engine', 'Unknown')}
- Door type: {fs.get('doors', 'standard')}
- Real car: {fs.get('real_hp', '?')} hp, {fs.get('real_top_speed_kmh', '?')} km/h
- Distinctive features: {', '.join(fs.get('distinctive_features', []))}

Match these features in your extra_parts and recolor_rules."""

    return {
        "parts_catalog_text": parts_catalog_text,
        "colors_text": colors_text,
        "mod_instructions": mod_instructions,
        "scale_guidance": scale_guidance,
        "prompt": prompt,
    }


async def customize_design_node(state: DesignState) -> dict:
    """LLM outputs DesignCustomization — colors + extra parts only."""
    llm = create_text_llm()
    structured_llm = llm.with_structured_output(DesignCustomization)

    messages = [
        SystemMessage(content=SYSTEM_PROMPT),
        HumanMessage(content=state["prompt"]),
        HumanMessage(
            content=(
                "Output your customization. Remember:\n"
                "1. recolor_rules paint template sections by label\n"
                "2. replace_rules swap template parts by label (keeps position)\n"
                "3. extra_parts max 25, only X >= 0\n"
                "4. System auto-mirrors + snaps to grid"
            )
        ),
    ]

    customization = await structured_llm.ainvoke(messages)
    return {"customization_output": customization.model_dump()}


async def merge_and_validate_node(state: DesignState) -> dict:
    """Deterministic merge: template parts + LLM customization → design_output."""
    customization = state.get("customization_output")
    if not customization:
        return {"status": "failed", "error_message": "No customization output produced."}

    result = TemplateParser.merge_design(
        template_ldr=state["template_ldr"],
        customization=customization,
        catalog=CAR_PARTS_CATALOG,
        scale=state.get("scale", "1:38"),
    )

    if "error" in result:
        return {
            "status": "failed",
            "error_message": result["error"],
            "retry_count": state.get("retry_count", 0) + 1,
        }

    return {"status": "completed", "design_output": result}


def _route_after_validate(state: DesignState) -> Literal["customize_design", "build_ldraw"]:
    """Conditional edge: retry customize_design if merge failed and retry_count <= 1."""
    if state.get("status") == "failed" and state.get("retry_count", 0) <= 1:
        return "customize_design"
    return "build_ldraw"


async def build_ldraw_node(state: DesignState) -> dict:
    """Build LDraw content from the structured design dict."""
    if state.get("status") == "failed":
        return {}
    generator = StudioDesignGenerator()
    data = state["design_output"]
    ldr_content = generator._build_ldraw(data, state["make"], state["model"], state["year"])
    return {"ldr_content": ldr_content, "body_color_id": data.get("body_color_id", 4)}


async def create_io_node(state: DesignState) -> dict:
    """Wrap LDraw in a Studio .io ZIP and persist .io + .ldr files."""
    if state.get("status") == "failed":
        return {}
    ldr_content = state["ldr_content"]
    make = state["make"]
    model = state["model"]
    year = state["year"]
    design_id = state["design_id"]

    storage = Path(settings.storage_path)
    design_dir = storage / str(design_id)
    design_dir.mkdir(parents=True, exist_ok=True)

    studio_file = StudioService.create_studio_file(
        ldr_content=ldr_content,
        name=f"{make} {model} {year}",
        description=state["design_output"].get("design_notes", ""),
    )

    io_path = design_dir / "model.io"
    studio_file.save(io_path)

    ldr_path = design_dir / "model.ldr"
    ldr_path.write_text(ldr_content, encoding="utf-8")

    return {
        "io_path": str(io_path.relative_to(storage)),
        "ldr_path": str(ldr_path.relative_to(storage)),
    }


async def build_parts_data_node(state: DesignState) -> dict:
    """Deduplicate parts and assemble the final return dict."""
    if state.get("status") == "failed":
        return {
            "parts_data": [],
            "parts_count": 0,
            "difficulty": "Easy",
            "design_notes": "",
            "metadata": {
                "generator": "langgraph",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "error": mask_api_key(state.get("error_message", "")),
            },
        }

    generator = StudioDesignGenerator()
    data = state["design_output"]
    parts_data = generator._build_parts_data(data)
    total_parts = data.get("total_parts", len(data.get("parts", [])))

    return {
        "parts_data": parts_data,
        "parts_count": total_parts,
        "difficulty": generator._estimate_difficulty(total_parts),
        "design_notes": data.get("design_notes", ""),
        "metadata": {
            "generator": "langgraph",
            "studio_version": "2.26.6",
            "template": classify_car_to_template(state["make"]),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        },
        "status": "completed",
    }


# ── Graph builder ──


def build_design_graph():
    """Compile and return the design-generation StateGraph."""
    graph = StateGraph(DesignState)

    graph.add_node("classify_template", classify_template_node)
    graph.add_node("parse_template", parse_template_node)
    graph.add_node("build_prompt", build_prompt_node)
    graph.add_node("customize_design", customize_design_node)
    graph.add_node("merge_and_validate", merge_and_validate_node)
    graph.add_node("build_ldraw", build_ldraw_node)
    graph.add_node("create_io", create_io_node)
    graph.add_node("build_parts_data", build_parts_data_node)

    graph.add_edge(START, "classify_template")
    graph.add_edge("classify_template", "parse_template")
    graph.add_edge("parse_template", "build_prompt")
    graph.add_edge("build_prompt", "customize_design")
    graph.add_edge("customize_design", "merge_and_validate")
    graph.add_conditional_edges(
        "merge_and_validate",
        _route_after_validate,
        {
            "customize_design": "customize_design",
            "build_ldraw": "build_ldraw",
        },
    )
    graph.add_edge("build_ldraw", "create_io")
    graph.add_edge("create_io", "build_parts_data")
    graph.add_edge("build_parts_data", END)

    return graph.compile()
