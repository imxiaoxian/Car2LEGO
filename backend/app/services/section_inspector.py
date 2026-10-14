# backend/app/services/section_inspector.py
"""inspect_ldr node logic — LDR roundtrip + distribution stats.

Steps:
1. merged = committed + pending
2. ldr_text = StudioDesignGenerator._build_ldraw(merged)
3. reparsed = TemplateParser.parse_ldraw(ldr_text)  # validates reverse-parseable
4. Compute Y/Z/color/type distribution stats
5. Check connection integrity with previous section
"""
from collections import Counter

from app.agents.section_schemas import SectionInspection
from app.services.studio_design_generator import StudioDesignGenerator
from app.services.template_parser import TemplateParser


def inspect_current_state(
    committed_parts: list[dict],
    pending_parts: list[dict],
    section: str,
    make: str,
    model: str,
    year: int,
) -> SectionInspection:
    """Build merged parts → LDR → reparse → stats. No ZIP packaging."""
    merged = list(committed_parts) + list(pending_parts)

    # Build LDR via existing helper
    generator = StudioDesignGenerator()
    # _build_ldraw expects a dict with "parts" and "design_notes"
    data = {"parts": merged, "design_notes": "", "positive_y_is_height": True}
    ldr_text = generator._build_ldraw(data, make, model, year)

    # Reverse-parse to validate the LDR is well-formed
    reparsed = TemplateParser.parse_ldraw(ldr_text)

    # parts_snapshot — right-half only (parser already filters via filter_right_half
    # if called; here we use raw parse which keeps all parts including mirrors).
    # For LLM prompt clarity, return right-half (X >= 0) only.
    right_half = [{**p, "y": -p["y"]} for p in _parsed_to_dicts(reparsed) if p["x"] >= 0]

    # Distribution stats
    y_hist = Counter()
    z_hist = Counter()
    color_dist = Counter()
    type_dist = Counter()
    for p in right_half:
        y_bucket = int(p["y"] // 24) * 24
        z_bucket = int(p["z"] // 60) * 60
        y_hist[y_bucket] += 1
        z_hist[z_bucket] += 1
        color_dist[p["color_id"]] += 1
        type_dist[p["part_num"]] += 1

    # Boundary occupancy
    if right_half:
        xs = [p["x"] for p in right_half]
        ys = [p["y"] for p in right_half]
        zs = [p["z"] for p in right_half]
        boundary = {
            "x_min": min(xs), "x_max": max(xs),
            "y_min": min(ys), "y_max": max(ys),
            "z_min": min(zs), "z_max": max(zs),
        }
    else:
        boundary = {}

    # Part origins cannot prove clutch/connectivity without connection geometry.
    integrity = {"with_previous": None, "gaps": [], "method": "not_physically_verified"}
    section_stats = {
        "y_histogram": dict(Counter(int(p["y"] // 24) * 24 for p in pending_parts)),
        "z_histogram": dict(Counter(int(p["z"] // 60) * 60 for p in pending_parts)),
        "color_dist": dict(Counter(p["color_id"] for p in pending_parts)),
        "type_dist": dict(Counter(p["part_num"] for p in pending_parts)),
        "total_parts": len(pending_parts),
    }

    return SectionInspection(
        section=section,
        parts_snapshot=right_half,
        current_section_parts=list(pending_parts),
        boundary_occupancy=boundary,
        connection_integrity=integrity,
        distribution_stats={
            "y_histogram": dict(y_hist),
            "z_histogram": dict(z_hist),
            "color_dist": dict(color_dist),
            "type_dist": dict(type_dist),
            "total_parts": len(right_half),
            "current_section": section_stats,
        },
    )


def _parsed_to_dicts(parts: list) -> list[dict]:
    """Convert ParsedPart list to dicts with string rotation."""
    out = []
    for p in parts:
        rot = p.rotation if isinstance(p.rotation, list) else list(p.rotation)
        rot_str = " ".join(str(v) for v in rot) if len(rot) == 9 else "1 0 0 0 1 0 0 0 1"
        out.append({
            "part_num": p.part_num,
            "color_id": p.color_id,
            "x": p.x, "y": p.y, "z": p.z,
            "rotation": rot_str,
            "step": p.step,
            "semantic_label": getattr(p, "label", "detail"),
        })
    return out
