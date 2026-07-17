# backend/tests/unit/services/test_section_evaluator.py
"""Section evaluator tests — prompt builder + 6-item checklist."""
from app.services.section_evaluator import build_eval_prompt, EVAL_CHECKLIST_ITEMS


def test_checklist_has_six_items():
    assert len(EVAL_CHECKLIST_ITEMS) == 6
    # Must include the 6 critical items from spec
    keywords = " ".join(EVAL_CHECKLIST_ITEMS).lower()
    for kw in ["brand", "y histogram", "z histogram", "type diversity", "connection", "recognizability"]:
        assert kw in keywords, f"missing checklist item: {kw}"


def test_build_eval_prompt_includes_plan():
    plan = {
        "body_color_id": 4,
        "accent_color_id": 0,
        "section_highlights": {"front": "Ferrari red nose with pop-up headlights"},
        "brand_features_to_render": ["rear_wing"],
    }
    inspection = {
        "section": "front",
        "parts_snapshot": [{"part_num": "4070.dat", "color_id": 4, "x": 40, "y": 48, "z": 280}],
        "distribution_stats": {"y_histogram": {48: 1}, "z_histogram": {240: 1}, "color_dist": {4: 1}},
    }
    prompt = build_eval_prompt(plan=plan, inspection=inspection, section="front")
    assert "Ferrari red nose" in prompt
    assert "rear_wing" in prompt
    assert "front" in prompt


def test_build_eval_prompt_includes_all_six_checklist_items():
    prompt = build_eval_prompt(plan={}, inspection={"section": "chassis"}, section="chassis")
    for item in EVAL_CHECKLIST_ITEMS:
        assert item in prompt
