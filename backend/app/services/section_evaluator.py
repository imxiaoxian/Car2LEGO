# backend/app/services/section_evaluator.py
"""llm_evaluate node prompt builder + 6-item checklist.

The evaluator LLM uses structured_output (SectionEvaluation) and must check
all 6 items in EVAL_CHECKLIST_ITEMS. The prompt is constructed by
build_eval_prompt() from the plan + inspection snapshot.
"""
import json

from app.agents.section_schemas import SectionEvaluation  # noqa: F401  # public API contract


EVAL_CHECKLIST_ITEMS = [
    "1. Brand features present — body_color matches plan, signature features (rear wing, headlights, etc.) are placed",
    "2. Y histogram (height distribution) — verify that actual part surfaces form the intended section profile; origin counts alone do not measure height or mass",
    "3. Z histogram (length distribution) — inspect actual footprints and silhouette for unexplained gaps or piles; lights, fascia and axles may naturally cluster at one end",
    "4. Part type diversity — not all plates/bricks; slope/wedge/special parts present where appropriate",
    "5. Connection alignment — parts at section boundaries align with previous section's connection_points",
    "6. Car recognizability — could a human recognize the car make/model from this section's silhouette?",
]


EVAL_SYSTEM_PROMPT = """You are a strict LEGO car design reviewer.

Evaluate the section just generated against the design plan. Be critical —
false positives are worse than false negatives. Only set needs_retry=false
when all applicable checklist items pass. Apply the checklist to the current
section: a chassis can be mostly plates at a uniform height, wheels need axle
symmetry rather than body slopes, and headlights/roof/windshield belong to
their relevant sections. Do not reject a section for features owned by another
section. Unknown physical connectivity is not a pass or a failure; flag visible
misalignment and treat actual clutch verification as deferred to Studio.

Output SectionEvaluation:
- quality_score: 0-100 (100 = perfect match to plan)
- semantic_issues: list of specific problems found
- needs_retry: true if ANY checklist item fails
- retry_guidance: concrete instruction for next attempt (e.g., "add 41740 slope at Z=280 Y=48")
Write semantic_issues and retry_guidance in Simplified Chinese, retaining part IDs and coordinates.
"""


def build_eval_prompt(plan: dict, inspection: dict, section: str) -> str:
    """Assemble the evaluation prompt from plan + inspection snapshot."""
    highlights = plan.get("section_highlights", {})
    section_highlight = highlights.get(section, "(no specific highlight)")
    brand_features = plan.get("brand_features_to_render", [])
    body_color = plan.get("body_color_id", "?")
    accent_color = plan.get("accent_color_id", "?")

    parts_snapshot = inspection.get("current_section_parts", inspection.get("parts_snapshot", []))
    all_stats = inspection.get("distribution_stats", {})
    stats = all_stats.get("current_section", all_stats)

    parts_json = json.dumps(parts_snapshot, ensure_ascii=False, indent=2)
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)

    checklist_text = "\n".join(EVAL_CHECKLIST_ITEMS)

    return f"""## Section Under Review: {section}

## Design Plan Context
- Current overall dimensions (LDU, authoritative): {plan.get('overall_dimensions', {})}
- Prototype coordinates: height is positive Y; rear is low Z, front is high Z.
- Body color: {body_color}, Accent color: {accent_color}
- Section highlight: {section_highlight}
- Brand features to render: {brand_features}
- Section bounds: {next((b for b in plan.get('section_bounds', []) if b.get('section') == section), {})}
- Connection verification: {inspection.get('connection_integrity', {})}

## Generated Parts (current section, right-half)
```json
{parts_json}
```

## Distribution Statistics
Histogram keys are the lower edges of buckets: Y uses 24-LDU buckets,
Z uses 60-LDU buckets. A Y bucket labeled 24 includes heights 24,32,40;
it does NOT mean that every part is at height 24. Part origins and the
rendered geometry are the source of truth. Connection points identify
assembly anchors, not a requirement for chassis endpoints to reach body bounds.
```json
{stats_json}
```

## Checklist — verify ALL 6 items
{checklist_text}

## Your Output
Return SectionEvaluation. If needs_retry=true, retry_guidance MUST be specific
(mention part_num, coordinates, and what to change).
"""
