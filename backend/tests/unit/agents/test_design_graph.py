"""Unit tests for the design-generation LangGraph graph (Template-First Architecture).

These tests mock the LLM at the `create_text_llm` boundary — the MockChatModel
returns a preset `DesignCustomization` for `with_structured_output()`. This lets
us verify the deterministic nodes (parse_template, merge_and_validate, build_ldraw,
create_io, build_parts_data) and the end-to-end flow without any real API calls.
"""

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents import design_graph
from app.agents.design_graph import build_design_graph
from app.config import settings
from app.services.studio_templates import get_template_ldr
from app.services.template_parser import TemplateParser
from tests.conftest import MockChatModel


@pytest.fixture
def patch_design_llm(mock_design_customization):
    """Patch create_text_llm in design_graph to return a MockChatModel.

    Returns a DesignCustomization (Template-First: colors + extra parts only).
    """
    mock_llm = MockChatModel(structured_output=mock_design_customization)
    with patch.object(design_graph, "create_text_llm", return_value=mock_llm):
        yield mock_llm


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Redirect settings.storage_path to a temp dir so tests don't pollute cwd."""
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    return tmp_path


@pytest.fixture
def merged_design_output():
    """Produce a realistic design_output via TemplateParser.merge_design.

    This is the dict shape that build_ldraw_node and build_parts_data_node consume.
    """
    customization = {
        "body_color_id": 4,
        "accent_color_id": 0,
        "recolor_rules": [
            {"label": "body_side", "new_color_id": 4},
            {"label": "roof", "new_color_id": 4},
        ],
        "replace_rules": [
            {
                "target_label": "headlight",
                "new_part_num": "4070.dat",
                "new_color_id": 14,
                "rotation": "1 0 0 0 1 0 0 0 1",
            }
        ],
        "extra_parts": [
            {
                "part_num": "3023.dat",
                "color_id": 0,
                "x": 40,
                "y": 96,
                "z": 20,
                "rotation": "1 0 0 0 1 0 0 0 1",
            },
        ],
        "design_notes": "Test design.",
    }
    return TemplateParser.merge_design(
        template_ldr=get_template_ldr("Ferrari"),
        customization=customization,
        scale="1:38",
    )


# ── parse_template_node ──


class TestParseTemplateNode:
    """parse_template_node: parses template LDraw into structured parts."""

    async def test_parses_sports_car_template(self):
        state = {"template_ldr": get_template_ldr("Ferrari")}
        result = await design_graph.parse_template_node(state)
        assert result["template_part_count"] > 5
        assert "body_side" in str(result["template_parts_json"])

    async def test_right_half_only(self):
        state = {"template_ldr": get_template_ldr("Ferrari")}
        result = await design_graph.parse_template_node(state)
        # All parts should have X >= -0.1 (right half + center)
        for p in result["template_parts"]:
            assert p["x"] >= -0.1


# ── build_prompt_node ──


class TestBuildPromptNode:
    """build_prompt_node: assembles the LLM prompt with car specs injection."""

    async def test_build_prompt_includes_car_specs(self, monkeypatch):
        """Prompt should include Real Car Specifications section when DB has specs."""
        from app.models.car_spec import CarSpec

        mock_spec = CarSpec(
            make="Porsche",
            model="911 GT3",
            year=2023,
            body_style="sports_car",
            length_mm=4573,
            width_mm=1852,
            height_mm=1279,
            wheelbase_mm=2457,
            engine_type="4.0L Flat-6",
            drive_type="RWD",
            horsepower=502,
            top_speed_kmh=318,
            distinctive_features=["round headlights", "rear wing"],
            colors_available=["White", "Yellow"],
            body_proportions="rear-engine, sloping roofline",
        )

        async def mock_get_specs(db, make, model, year):
            return mock_spec

        monkeypatch.setattr(design_graph.CarSpecsService, "get_specs", mock_get_specs)

        state = {
            "make": "Porsche",
            "model": "911 GT3",
            "year": 2023,
            "scale": "1:38",
            "template_info": {
                "id": "sports_car",
                "name": "Sports Car",
                "body_style": "sports_car",
                "default_color": 15,
                "wheel_type": "4624c00",
            },
            "template_parts_json": "[]",
            "template_part_count": 0,
            "template_parts": [],
        }
        result = await design_graph.build_prompt_node(state)

        prompt = result["prompt"]
        assert "Real Car Specifications" in prompt
        assert "2023 Porsche 911 GT3" in prompt
        assert "4573mm" in prompt
        assert "4.0L Flat-6" in prompt
        assert "502 hp" in prompt
        assert "round headlights" in prompt

    async def test_build_prompt_without_car_specs(self, monkeypatch):
        """Prompt should still work when DB has no specs (graceful degradation)."""

        async def mock_get_specs(db, make, model, year):
            return None

        monkeypatch.setattr(design_graph.CarSpecsService, "get_specs", mock_get_specs)

        state = {
            "make": "Unknown",
            "model": "Car",
            "year": 2024,
            "scale": "1:38",
            "template_info": {
                "id": "sports_car",
                "name": "Sports Car",
                "body_style": "sports_car",
                "default_color": 15,
                "wheel_type": "4624c00",
            },
            "template_parts_json": "[]",
            "template_part_count": 0,
            "template_parts": [],
        }
        result = await design_graph.build_prompt_node(state)

        prompt = result["prompt"]
        assert "Real Car Specifications" not in prompt
        assert "Target Car" in prompt  # prompt still generated


# ── merge_and_validate_node ──


class TestMergeAndValidateNode:
    """merge_and_validate_node: merges template + customization -> design_output."""

    async def test_valid_customization_succeeds(self):
        state = {
            "template_ldr": get_template_ldr("Ferrari"),
            "customization_output": {
                "body_color_id": 4,
                "accent_color_id": 0,
                "recolor_rules": [{"label": "body_side", "new_color_id": 4}],
                "replace_rules": [
                    {
                        "target_label": "headlight",
                        "new_part_num": "4070.dat",
                        "new_color_id": 14,
                    }
                ],
                "extra_parts": [],
                "design_notes": "Red Ferrari.",
            },
            "scale": "1:38",
        }
        result = await design_graph.merge_and_validate_node(state)
        assert result["status"] == "completed"
        assert "design_output" in result
        assert result["design_output"]["body_color_id"] == 4

    async def test_too_many_extras_fails(self):
        extras = [
            {"part_num": "3023.dat", "color_id": 0, "x": 20, "y": 40, "z": 100}
            for _ in range(30)
        ]
        state = {
            "template_ldr": get_template_ldr("Ferrari"),
            "customization_output": {
                "body_color_id": 4,
                "accent_color_id": 0,
                "recolor_rules": [],
                "extra_parts": extras,
                "design_notes": "Too many parts.",
            },
            "scale": "1:38",
        }
        result = await design_graph.merge_and_validate_node(state)
        assert result["status"] == "failed"
        assert "extra" in result["error_message"].lower()


# ── build_ldraw_node ──


class TestBuildLdrawNode:
    """build_ldraw_node: converts merged design_output -> LDraw content."""

    async def test_produces_valid_ldraw(
        self, patch_design_llm, tmp_storage, merged_design_output
    ):
        state = {
            "make": "Ferrari",
            "model": "F40",
            "year": 1987,
            "design_output": merged_design_output,
            "status": "completed",
        }
        result = await design_graph.build_ldraw_node(state)
        ldr = result["ldr_content"]

        # Header lines
        assert "0 1987 Ferrari F40" in ldr
        assert "0 Author: Car2LEGO AI" in ldr
        # STEP markers
        assert "0 STEP" in ldr
        # At least one part line
        assert "1 " in ldr

    async def test_body_color_extracted(
        self, patch_design_llm, tmp_storage, merged_design_output
    ):
        state = {
            "make": "Porsche",
            "model": "911",
            "year": 2020,
            "design_output": merged_design_output,
            "status": "completed",
        }
        result = await design_graph.build_ldraw_node(state)
        assert result["body_color_id"] == 4


# ── build_parts_data_node ──


class TestBuildPartsDataNode:
    """build_parts_data_node: deduplicates parts for DB storage."""

    async def test_deduplicates_parts(
        self, patch_design_llm, merged_design_output
    ):
        state = {
            "make": "Ferrari",
            "design_output": merged_design_output,
            "status": "completed",
        }
        result = await design_graph.build_parts_data_node(state)
        parts_data = result["parts_data"]
        # Template + extras + mirrors yield a non-empty deduplicated list
        assert len(parts_data) > 0
        total_qty = sum(p["quantity"] for p in parts_data)
        assert total_qty > 0

    async def test_includes_metadata(self, patch_design_llm, merged_design_output):
        state = {
            "make": "Porsche",
            "design_output": merged_design_output,
            "status": "completed",
        }
        result = await design_graph.build_parts_data_node(state)
        assert result["metadata"]["generator"] == "langgraph"
        assert result["status"] == "completed"
        assert "generated_at" in result["metadata"]


# ── End-to-end (mocked LLM) ──


class TestDesignGraphEndToEnd:
    """Full graph invocation with mocked LLM — from make/model/year to .io file."""

    async def test_end_to_end_mocked(
        self, patch_design_llm, tmp_storage, mock_design_customization
    ):
        """The full graph produces a .io file and parts data."""
        graph = build_design_graph()
        initial_state = {
            "design_id": "test-e2e-001",
            "make": "Ferrari",
            "model": "F40",
            "year": 1987,
            "scale": "1:38",
            "mod_ids": [],
            "custom_request": "",
            "flagship_metadata": None,
            "messages": [],
            "design_output": None,
            "retry_count": 0,
            "status": "",
            "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        # Status
        assert result["status"] == "completed"
        # Files written
        assert result.get("io_path"), "io_path should be set"
        assert result.get("ldr_path"), "ldr_path should be set"
        # Parts — template + extras + mirrors, well above 10
        assert result["parts_count"] > 10
        assert len(result["parts_data"]) > 0
        # Design notes propagated from the mock
        assert "Red body" in result["design_notes"]

    async def test_io_file_is_valid_zip(
        self, patch_design_llm, tmp_storage, mock_design_customization
    ):
        """The .io file written to disk is a valid ZIP containing model.ldr."""
        graph = build_design_graph()
        initial_state = {
            "design_id": "test-zip-001",
            "make": "Toyota",
            "model": "Supra",
            "year": 2024,
            "scale": "1:38",
            "mod_ids": [],
            "custom_request": "",
            "flagship_metadata": None,
            "messages": [],
            "design_output": None,
            "retry_count": 0,
            "status": "",
            "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        io_full_path = Path(settings.storage_path) / result["io_path"]
        assert io_full_path.exists(), f".io file should exist at {io_full_path}"

        with zipfile.ZipFile(io_full_path, "r") as zf:
            names = zf.namelist()
            assert "model.ldr" in names, "ZIP must contain model.ldr"
            assert "model2.ldr" in names, "ZIP must contain model2.ldr"
            assert ".info" in names, "ZIP must contain .info metadata"
            model_ldr = zf.read("model.ldr").decode("utf-8", errors="replace")
            assert "Toyota" in model_ldr or "Supra" in model_ldr

    async def test_ldr_file_written_to_disk(
        self, patch_design_llm, tmp_storage, mock_design_customization
    ):
        """The .ldr file is also written alongside the .io file."""
        graph = build_design_graph()
        initial_state = {
            "design_id": "test-ldr-001",
            "make": "BMW",
            "model": "M3",
            "year": 2020,
            "scale": "1:38",
            "mod_ids": [],
            "custom_request": "",
            "flagship_metadata": None,
            "messages": [],
            "design_output": None,
            "retry_count": 0,
            "status": "",
            "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        ldr_full_path = Path(settings.storage_path) / result["ldr_path"]
        assert ldr_full_path.exists()
        content = ldr_full_path.read_text(encoding="utf-8")
        assert "0 STEP" in content
        assert "1 " in content  # At least one part line
