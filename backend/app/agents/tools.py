"""Real callable tools for the LangGraph agent layer.

These tools let the LLM query the parts catalog, brand colors, and chassis
templates — turning the legacy "single-shot structured output" pattern into
a proper ReAct loop where the model can gather context before producing a
design.

Each tool is a plain Python function decorated with `@tool` so it can be:
- Called directly in unit tests (no LangChain runtime needed)
- Bound to a ChatModel via `llm.bind_tools([...])` for the ReAct loop

Tools are intentionally synchronous — they read in-memory catalog data and
return instantly. No I/O means no async overhead.
"""

from langchain_core.tools import tool

from app.services.lego_parts_knowledge import CAR_PARTS_CATALOG, CAR_COLORS
from app.services.studio_templates import (
    CAR_TEMPLATES,
    classify_car_to_template,
    get_template_ldr,
)


# ── Brand → LEGO color mapping (extracted from studio_design_generator SYSTEM_PROMPT) ──
# Each entry: (primary_color_id, [secondary_color_ids])
# Color names are resolved at call time from CAR_COLORS so the source of
# truth for color IDs stays in one place.
_BRAND_COLORS: dict[str, tuple[int, list[int]]] = {
    "ferrari":     (4,  []),
    "lamborghini": (27, [14]),
    "mclaren":     (25, []),
    "porsche":     (15, [4]),
    "bugatti":     (1,  [89]),
    "koenigsegg":  (0,  []),
    "bmw":         (1,  [15]),
    "mercedes":    (71, [0]),
    "audi":        (15, [71]),
    "ford":        (1,  [4]),
    "chevrolet":   (4,  [14]),
    "chevy":       (4,  [14]),
    "nissan":      (4,  [15]),
    "toyota":      (4,  [15]),
    "honda":       (15, [4]),
}


def _color_name(color_id: int) -> str:
    """Look up the human-readable color name. Falls back to 'Color <id>'."""
    entry = CAR_COLORS.get(color_id)
    if entry:
        return entry[0]
    return f"Color {color_id}"


@tool
def search_parts_catalog(query: str) -> list[dict]:
    """Search the curated LEGO parts catalog by name or usage description.

    Use this to find specific part numbers (e.g. 'wheel', 'windshield', 'slope')
    before placing them in a design. Returns up to 10 matches with part_num,
    bricklink_id, name, category, size, and usage fields.

    Args:
        query: A keyword or short phrase (e.g. 'wheel', '1x2 plate', 'curved slope').

    Returns:
        List of matching part dicts (max 10). Empty list if no match.
    """
    query_lower = query.strip().lower()
    if not query_lower:
        return []
    results: list[dict] = []
    for p in CAR_PARTS_CATALOG:
        if query_lower in p.name.lower() or query_lower in p.usage.lower():
            results.append({
                "part_num": p.part_num,
                "bricklink_id": p.bricklink_id,
                "name": p.name,
                "category": p.category,
                "size": p.size,
                "usage": p.usage,
            })
            if len(results) >= 10:
                break
    return results


@tool
def get_brand_color(make: str) -> dict:
    """Get the canonical LEGO color IDs for a car brand.

    Brands like Ferrari, Lamborghini, and Porsche have signature colors that
    should be used for the body. Call this before assigning body color_ids.

    Args:
        make: Car manufacturer (e.g. 'Ferrari', 'lamborghini', 'PORSCHE').

    Returns:
        Dict with `primary_color_id`, `primary_color_name`, and
        `secondary_color_ids` (alternate brand colors). Defaults to white(15)
        for unknown brands.
    """
    make_lower = make.strip().lower()
    primary_id, secondary_ids = _BRAND_COLORS.get(make_lower, (15, []))
    return {
        "primary_color_id": primary_id,
        "primary_color_name": _color_name(primary_id),
        "secondary_color_ids": secondary_ids,
        "secondary_color_names": [_color_name(c) for c in secondary_ids],
    }


@tool
def get_template_info(make: str) -> dict:
    """Get the chassis template (body style + LDraw preview) for a car make.

    Speed Champions cars start from one of 6 chassis templates (sports_car,
    suv, sedan, pickup, hatchback, f1_race). Call this to see the template's
    starting LDraw structure before customizing it.

    Args:
        make: Car manufacturer or model name (e.g. 'Ferrari F40', 'Jeep Wrangler').

    Returns:
        Dict with `template_id`, `name`, `body_style`, `default_color_id`,
        `default_color_name`, `wheel_type`, `roof_style`, `car_makes`, and
        `template_ldr_preview` (first 2000 chars of the LDraw template).
    """
    template_id = classify_car_to_template(make)
    info = CAR_TEMPLATES.get(template_id, CAR_TEMPLATES["sports_car"])
    template_ldr = get_template_ldr(make)
    return {
        "template_id": template_id,
        "name": info.get("name", template_id),
        "body_style": info.get("body_style", template_id),
        "default_color_id": info.get("default_color", 15),
        "default_color_name": _color_name(info.get("default_color", 15)),
        "wheel_type": info.get("wheel_type", "4624c00"),
        "roof_style": info.get("roof_style", ""),
        "car_makes": info.get("car_makes", []),
        "template_ldr_preview": template_ldr[:2000],
    }


@tool
def validate_part_exists(part_num: str) -> bool:
    """Verify that a LEGO part number exists in the curated catalog.

    Use this before placing a part in a design to ensure the part_num is
    real and not hallucinated. Only parts in the catalog can be reliably
    sourced from BrickLink.

    Args:
        part_num: LDraw part filename (e.g. '3024.dat', '4624c00.dat').

    Returns:
        True if the part exists in the catalog, False otherwise.
    """
    return any(p.part_num == part_num for p in CAR_PARTS_CATALOG)


# Convenience export for graphs that want to bind all tools at once
DESIGN_TOOLS = [
    search_parts_catalog,
    get_brand_color,
    get_template_info,
    validate_part_exists,
]
