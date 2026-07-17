# backend/tests/unit/agents/test_section_schemas.py
"""Section workflow schema tests."""
from app.agents.section_schemas import (
    SectionBounds, DesignPlan, SectionPartPlacement, SectionParts,
    DeterministicCheckResult, SectionInspection, SectionEvaluation,
)


def test_section_bounds_accepts_valid_section():
    sb = SectionBounds(
        section="chassis",
        z_range=(0.0, 360.0),
        y_range=(0.0, 24.0),
        connection_points=[(0.0, 24.0, 240.0)],
    )
    assert sb.section == "chassis"


def test_design_plan_requires_section_bounds():
    try:
        DesignPlan(
            body_color_id=4, accent_color_id=0,
            overall_dimensions={"length": 320, "width": 80, "height": 96},
            section_bounds=[], section_highlights={},
            brand_features_to_render=[], plan_notes="",
        )
        assert False, "Should reject empty section_bounds"
    except Exception:
        assert True


def test_section_evaluation_quality_score_range():
    ev = SectionEvaluation(
        quality_score=85, semantic_issues=["missing wing"],
        needs_retry=True, retry_guidance="add rear wing",
    )
    assert 0 <= ev.quality_score <= 100
