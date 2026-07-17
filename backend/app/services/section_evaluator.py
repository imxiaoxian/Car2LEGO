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
    "2. Y histogram (height distribution) — parts form pyramid/hourglass shape, NOT uniform stack across Y buckets",
    "3. Z histogram (length distribution) — parts within this section's z_range are balanced (no single Z bucket > 50%)",
    "4. Part type diversity — not all plates/bricks; slope/wedge/special parts present where appropriate",
    "5. Connection alignment — parts at section boundaries align with previous section's connection_points",
    "6. Car recognizability — could a human recognize the car make/model from this section's silhouette?",
]


EVAL_SYSTEM_PROMPT = """You are a strict LEGO car design reviewer.

Evaluate the section just generated against the design plan. Be critical —
false positives are worse than false negatives. Only set needs_retry=false
when ALL 6 checklist items pass.

Output SectionEvaluation:
- quality_score: 0-100 (100 = perfect match to plan)
- semantic_issues: list of specific problems found
- needs_retry: true if ANY checklist item fails
- retry_guidance: concrete instruction for next attempt (e.g., "add 41740 slope at Z=280 Y=48")
"""


def build_eval_prompt(plan: dict, inspection: dict, section: str) -> str:
    """Assemble the evaluation prompt from plan + inspection snapshot."""
    highlights = plan.get("section_highlights", {})
    section_highlight = highlights.get(section, "(no specific highlight)")
    brand_features = plan.get("brand_features_to_render", [])
    body_color = plan.get("body_color_id", "?")
    accent_color = plan.get("accent_color_id", "?")

    parts_snapshot = inspection.get("parts_snapshot", [])
    stats = inspection.get("distribution_stats", {})

    parts_json = json.dumps(parts_snapshot[:30], ensure_ascii=False, indent=2)  # cap at 30 for prompt
    stats_json = json.dumps(stats, ensure_ascii=False, indent=2)

    checklist_text = "\n".join(EVAL_CHECKLIST_ITEMS)

    return f"""## Section Under Review: {section}

## Design Plan Context
- Body color: {body_color}, Accent color: {accent_color}
- Section highlight: {section_highlight}
- Brand features to render: {brand_features}

## Generated Parts (right-half, max 30 shown)
```json
{parts_json}
```

## Distribution Statistics
```json
{stats_json}
```

## Checklist — verify ALL 6 items
{checklist_text}

## Your Output
Return SectionEvaluation. If needs_retry=true, retry_guidance MUST be specific
(mention part_num, coordinates, and what to change).
"""
