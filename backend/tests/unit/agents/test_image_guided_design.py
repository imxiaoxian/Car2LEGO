"""Offline regressions for the real v2 graph, using constructed images/LLM output."""

import json
import zipfile
from unittest.mock import AsyncMock

import pytest

from app.agents import section_graph
from app.agents.section_schemas import SectionBounds, SectionPartPlacement, DesignPlan
from app.config import settings
from app.services.studio_design_generator import StudioDesignGenerator
from app.services.studio_service import StudioService


async def test_full_v2_pipeline_reads_images_and_builds_five_sections(
    tmp_path, monkeypatch, mock_reference_images, mock_image_guided_llm,
):
    monkeypatch.setattr(settings, "design_workflow", "v2")
    result = await StudioDesignGenerator(str(tmp_path)).generate("v2-car", "Ferrari", "F40", 1990)
    assert result["status"] == "completed", result.get("error_message")
    assert result["metadata"]["workflow"] == "v2_section"
    assert result["metadata"]["progress"] == "5/5"
    assert result["parts_count"] == sum(p["quantity"] for p in result["parts_data"])
    with zipfile.ZipFile(tmp_path / result["file_io_path"]) as package:
        ldr = package.read("model.ldr").decode()
        assert ldr.count("0 STEP") == 5
        assert len(StudioService.extract_parts_from_ldr(ldr)) == result["parts_count"]
    for schema, messages in mock_image_guided_llm:
        assert any(isinstance(m.content, list) and any(b.get("type") == "image_url" for b in m.content)
                   for m in messages), f"{schema} did not receive reference images"
    assert len(mock_image_guided_llm) == 6  # Plan + 5 reviews of code-owned placements
    assert (tmp_path / "v2-car" / "assembly_preview.png").is_file()
    assert result["metadata"]["quality_level"] == "stylized_prototype"
    progress = json.loads((tmp_path / "v2-car" / "generation_status.json").read_text())
    assert progress == {"stage": "completed", "progress": 100}


@pytest.mark.parametrize("failure", ["deterministic", "evaluation"])
async def test_section_retries_are_bounded_and_do_not_commit_failed_parts(monkeypatch, failure):
    builds = []

    async def build(state):
        builds.append(state["current_section"])
        return {"pending_parts": [{"part_num": "3020.dat", "color_id": 7, "x": 0, "y": 8, "z": 100}]}

    monkeypatch.setattr(section_graph, "build_section_node", build)
    monkeypatch.setattr(section_graph, "deterministic_check_node", AsyncMock(return_value={
        "inspection_snapshot": {"passed": failure != "deterministic", "issues": ["test rejection"]},
    }))
    monkeypatch.setattr(section_graph, "inspect_ldr_node", AsyncMock(return_value={"inspection_snapshot": {}}))
    monkeypatch.setattr(section_graph, "llm_evaluate_node", AsyncMock(return_value={
        "evaluation_result": {"needs_retry": True, "retry_guidance": "repair this part"},
    }))
    state = {"current_section": "chassis", "section_index": 0, "committed_parts": [],
             "pending_parts": [], "section_feedback": [], "section_retry_count": 0}
    result = await section_graph.build_section_loop_graph().ainvoke(state)
    assert len(builds) == 3
    assert result["committed_parts"] == []
    assert result["pending_parts"] == []
    assert "chassis" in result["section_failure"]


async def test_reference_generation_failure_is_reported(tmp_path, monkeypatch):
    from app.services.reference_images import ReferenceImageService
    monkeypatch.setattr(ReferenceImageService, "generate", AsyncMock(side_effect=ValueError("gpt-image-2.5-sunburst unavailable")))
    result = await StudioDesignGenerator(str(tmp_path)).generate("failed-car", "Ford", "GT", 2020)
    assert result["status"] == "failed"
    assert "gpt-image-2.5-sunburst unavailable" in result["error_message"]
    assert not (tmp_path / "failed-car" / "model.io").exists()


async def test_rejected_assembly_reports_reason_and_never_exports_fallback(tmp_path, monkeypatch, mock_reference_images, mock_image_guided_llm):
    monkeypatch.setattr(settings, "design_workflow", "v2")
    monkeypatch.setattr(section_graph, "llm_evaluate_node", AsyncMock(return_value={"evaluation_result": {
        "needs_retry": True, "semantic_issues": ["wheel mount misaligned"], "retry_guidance": "check axle",
    }}))
    result = await StudioDesignGenerator(str(tmp_path)).generate("rejected", "Ferrari", "F40", 1990)
    assert result["status"] == "failed"
    assert "wheel mount misaligned" in result["error_message"]
    assert not (tmp_path / "rejected" / "model.io").exists()


async def test_adjacent_plates_are_legal_but_duplicates_are_rejected():
    parts = [{"part_num": "3020.dat", "color_id": 7, "x": 40, "y": y, "z": 100} for y in (8, 16)]
    state = {"pending_parts": parts, "current_section": "chassis", "plan": {"section_bounds": [
        SectionBounds(section="chassis", z_range=(0, 360), y_range=(0, 24)).model_dump(),
    ]}}
    assert (await section_graph.deterministic_check_node(state))["inspection_snapshot"]["passed"]
    state["pending_parts"].append(parts[0])
    assert not (await section_graph.deterministic_check_node(state))["inspection_snapshot"]["passed"]


def test_plan_rejects_duplicate_sections():
    with pytest.raises(ValueError, match="unique"):
        DesignPlan(body_color_id=4, accent_color_id=0, overall_dimensions={}, section_highlights={},
                   section_bounds=[SectionBounds(section="chassis", z_range=(0, 360), y_range=(0, 24))] * 5)


def test_invalid_rotations_and_coordinates_rejected():
    for extra in ({"rotation": "bad"}, {"z": float("nan")}, {"quantity": 0}, {"quantity": 2}):
        values = {"part_num": "3020.dat", "color_id": 7, "x": 0, "y": 8, "z": 100, **extra}
        with pytest.raises(ValueError):
            SectionPartPlacement(**values)


def test_rotated_part_reflects_in_world_x_and_height_converts_to_ldraw(tmp_path):
    generator = StudioDesignGenerator(str(tmp_path))
    ldr = generator._build_ldraw({"positive_y_is_height": True, "parts": [{
        "part_num": "3020.dat", "color_id": 7, "x": 40, "y": 24, "z": 100,
        "rotation": "0 0 1 0 1 0 -1 0 0",
    }]}, "Ferrari", "F40", 1990)
    parts = StudioService.extract_parts_from_ldr(ldr)
    assert len(parts) == 2
    assert "1 7 40.0 -24.0 100.0 0 0 1 0 1 0 -1 0 0 3020.dat" in ldr
    assert "1 7 -40.0 -24.0 100.0 -0 -0 -1 0 1 0 -1 0 0 3020.dat" in ldr
