# backend/app/agents/section_tools.py
"""LangChain tools for the build_section ReAct agent.

Three tools — kept minimal to avoid LLM迷失:
- search_parts: query CAR_PARTS_CATALOG by usage keyword
- get_brand_feature: query brand_features library for real coords
- validate_placement: realtime check part existence + bounds + X>=0
"""
from langchain_core.tools import tool

from app.agents.section_schemas import SectionBounds
from app.services.lego_parts_knowledge import CAR_PARTS_CATALOG
from app.services.section_planner import compute_section_bounds
from app.services.brand_features import get_brand_features


@tool
def search_parts(usage_keyword: str) -> list[dict]:
    """Search CAR_PARTS_CATALOG by usage keyword (e.g., 'headlight', 'slope', 'wheel').

    Returns list of {part_num, name, size, usage}.
    """
    kw = usage_keyword.lower()
    results = []
    for p in CAR_PARTS_CATALOG:
        if kw in p.usage.lower() or kw in p.name.lower():
            results.append({
                "part_num": p.part_num,
                "name": p.name,
                "size": p.size,
                "usage": p.usage,
            })
    return results


@tool
def get_brand_feature(make: str, model: str, feature_id: str = "") -> dict:
    """Get brand-specific feature coordinates (rear_wing height, exhaust position, etc.).

    Returns {feature_id: {part_num, color_id, x, y, z, description}} or {} if not found.
    """
    features = get_brand_features(make, model)
    if not features:
        return {}
    if feature_id:
        for f in features:
            if f.feature_id == feature_id:
                return {
                    f.feature_id: {
                        "part_num": f.part_num,
                        "color_id": f.color_id,
                        "x": f.x, "y": f.y, "z": f.z,
                        "description": f.description,
                    }
                }
        return {}
    return {
        f.feature_id: {
            "part_num": f.part_num,
            "color_id": f.color_id,
            "x": f.x, "y": f.y, "z": f.z,
            "description": f.description,
        }
        for f in features
    }


@tool
def validate_placement(
    x: float, y: float, z: float, part_num: str, section: str,
) -> dict:
    """Realtime check: part existence + (x,y,z) within section bounds + X>=0.

    Returns {valid: bool, reason: str}.
    """
    if x < 0:
        return {"valid": False, "reason": f"x must be >= 0 (right-half only), got {x}"}

    # Part existence
    valid_part_nums = {p.part_num for p in CAR_PARTS_CATALOG}
    if part_num not in valid_part_nums:
        return {"valid": False, "reason": f"part_num {part_num!r} not in catalog"}

    # Section bounds (use sports_car default; body_style unknown at tool-call time)
    try:
        bounds_list = compute_section_bounds(scale="1:38", body_style="sports_car")
    except ValueError as e:
        return {"valid": False, "reason": str(e)}

    bounds = next((b for b in bounds_list if b.section == section), None)
    if bounds is None:
        return {"valid": False, "reason": f"unknown section {section!r}"}

    z_min, z_max = bounds.z_range
    y_min, y_max = bounds.y_range
    if not (z_min <= z <= z_max):
        return {"valid": False, "reason": f"z={z} out of {section} range [{z_min}, {z_max}]"}
    if not (y_min <= y <= y_max):
        return {"valid": False, "reason": f"y={y} out of {section} range [{y_min}, {y_max}]"}

    return {"valid": True, "reason": "ok"}
