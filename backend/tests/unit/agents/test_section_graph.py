# backend/tests/unit/agents/test_section_graph.py
"""Section loop subgraph tests — 5 sections × build/check/inspect/eval/route."""
import pytest

from app.agents.section_graph import (
    build_section_loop_graph, SECTIONS_ORDER,
)


def test_sections_order_matches_planner():
    from app.services.section_planner import SECTIONS_ORDER as planner_order
    assert SECTIONS_ORDER == planner_order


@pytest.mark.asyncio
async def test_graph_compiles():
    graph = build_section_loop_graph()
    assert graph is not None


@pytest.mark.asyncio
async def test_chassis_node_advances_to_front(monkeypatch):
    """After chassis completes (eval needs_retry=false), section_index increments."""
    from app.agents import section_graph as sg
    from app.agents.section_schemas import (
        DeterministicCheckResult, SectionEvaluation, SectionInspection,
    )

    async def mock_build(state):
        return {"pending_parts": [{"part_num": "3020.dat", "color_id": 7, "x": 40.0, "y": 8.0, "z": 100.0, "rotation": "1 0 0 0 1 0 0 0 1", "quantity": 1, "semantic_label": "chassis"}]}

    async def mock_check(state):
        # deterministic_check_node stores its result in inspection_snapshot
        # (DesignState has no check_result field; LangGraph discards unknown keys)
        return {"inspection_snapshot": DeterministicCheckResult(passed=True).model_dump()}

    async def mock_inspect(state):
        return {"inspection_snapshot": SectionInspection(
            section="chassis", parts_snapshot=[], boundary_occupancy={},
            connection_integrity={}, distribution_stats={},
        ).model_dump()}

    async def mock_eval(state):
        return {"evaluation_result": SectionEvaluation(
            quality_score=90, semantic_issues=[],
            needs_retry=False, retry_guidance="",
        ).model_dump()}

    monkeypatch.setattr(sg, "build_section_node", mock_build)
    monkeypatch.setattr(sg, "deterministic_check_node", mock_check)
    monkeypatch.setattr(sg, "inspect_ldr_node", mock_inspect)
    monkeypatch.setattr(sg, "llm_evaluate_node", mock_eval)

    graph = build_section_loop_graph()
    initial = {
        "section_index": 0, "current_section": "chassis",
        "committed_parts": [], "pending_parts": [],
        "section_feedback": [], "section_retry_count": 0,
        "make": "Ferrari", "model": "F40", "year": 1990,
        "plan": {"section_highlights": {}, "brand_features_to_render": [], "section_bounds": []},
    }
    result = await graph.ainvoke(initial)
    # After chassis passes, section_index should advance
    assert result["section_index"] >= 1
