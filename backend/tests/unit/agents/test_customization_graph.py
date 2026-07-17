"""Unit tests for the customization LangGraph graph (Phase 4).

These tests mock the LLM at the `create_text_llm` boundary — the MockChatModel
returns a preset `CustomizedDesign` for `with_structured_output()`. This lets
us verify the customization nodes and the end-to-end flow without real API calls.
"""

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents import customization_graph
from app.agents.customization_graph import build_customization_graph
from app.config import settings
from tests.conftest import MockChatModel


@pytest.fixture
def patch_customization_llm(mock_customized_design):
    """Patch create_text_llm in customization_graph to return a MockChatModel."""
    mock_llm = MockChatModel(structured_output=mock_customized_design)
    with patch.object(customization_graph, "create_text_llm", return_value=mock_llm):
        yield mock_llm


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Redirect settings.storage_path to a temp dir."""
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    return tmp_path


class TestBuildLdrawNode:
    """build_ldraw_node: converts CustomizedDesign dict → LDraw content."""

    async def test_produces_valid_ldraw(self, patch_customization_llm, mock_customized_design):
        """The LDraw output contains headers and part lines."""
        state = {
            "car_info": "2020 Porsche 911 Turbo",
            "design_output": mock_customized_design.model_dump(),
        }
        result = await customization_graph.build_ldraw_node(state)
        ldr = result["ldr_content"]
        # Header should include the car info parsed as make/model
        assert "0 " in ldr
        assert "0 STEP" in ldr
        # Part lines
        assert "3024.dat" in ldr
        assert "3020.dat" in ldr

    async def test_make_model_parsed_from_car_info(self, patch_customization_llm, mock_customized_design):
        """car_info is split into make + model for the LDraw header."""
        state = {
            "car_info": "Ferrari F40 1987",
            "design_output": mock_customized_design.model_dump(),
        }
        result = await customization_graph.build_ldraw_node(state)
        assert "Ferrari" in result["ldr_content"]

    async def test_default_make_when_car_info_short(self, patch_customization_llm, mock_customized_design):
        """When car_info has < 2 words, defaults 'Custom' and 'Design' are used."""
        state = {
            "car_info": "Ferrari",
            "design_output": mock_customized_design.model_dump(),
        }
        result = await customization_graph.build_ldraw_node(state)
        # car_info="Ferrari" has only 1 word (< 2), so defaults are used
        assert "Custom Design" in result["ldr_content"]


class TestBuildPartsDataNode:
    """build_parts_data_node: deduplicates customized parts for DB storage."""

    async def test_deduplicates_parts(self, patch_customization_llm, mock_customized_design):
        """Parts with same (part_num, color_id) are merged by quantity."""
        state = {"design_output": mock_customized_design.model_dump()}
        result = await customization_graph.build_parts_data_node(state)
        parts_data = result["parts_data"]
        # mock_customized_design has 3 unique (part_num, color_id) pairs
        assert len(parts_data) == 3
        total_qty = sum(p["quantity"] for p in parts_data)
        assert total_qty == 3  # 1 + 1 + 1

    async def test_includes_metadata(self, patch_customization_llm, mock_customized_design):
        """The return dict includes generator metadata + status."""
        state = {"design_output": mock_customized_design.model_dump()}
        result = await customization_graph.build_parts_data_node(state)
        assert result["metadata"]["generator"] == "langgraph"
        assert result["metadata"]["type"] == "customization"
        assert result["status"] == "completed"

    async def test_propagates_change_counts(self, patch_customization_llm, mock_customized_design):
        """added_parts and removed_parts are surfaced from the design output."""
        state = {"design_output": mock_customized_design.model_dump()}
        result = await customization_graph.build_parts_data_node(state)
        assert result["added_parts"] == 1
        assert result["removed_parts"] == 0
        assert result["modification_summary"] == "Added a rear wing."


class TestCustomizationGraphEndToEnd:
    """Full graph invocation with mocked LLM."""

    async def test_end_to_end_mocked(
        self, patch_customization_llm, tmp_storage, mock_customized_design
    ):
        """The full graph produces a .io file and parts data."""
        graph = build_customization_graph()
        initial_state = {
            "design_id": "test-custom-001",
            "base_ldr_content": "0 FILE base.ldr\n0 NOFILE",
            "base_parts_summary": "2 plates, 1 brick",
            "car_info": "2020 Porsche 911 Turbo",
            "customization_request": "Add a large rear wing",
            "messages": [],
            "design_output": None,
            "status": "",
            "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        assert result["status"] == "completed"
        assert result.get("io_path"), "io_path should be set"
        assert result.get("ldr_path"), "ldr_path should be set"
        assert result["parts_count"] == 3
        assert len(result["parts_data"]) > 0
        assert result["added_parts"] == 1
        assert "rear wing" in result["modification_summary"].lower()

    async def test_io_file_is_valid_zip(
        self, patch_customization_llm, tmp_storage, mock_customized_design
    ):
        """The .io file written to disk is a valid ZIP."""
        graph = build_customization_graph()
        initial_state = {
            "design_id": "test-custom-zip-001",
            "base_ldr_content": "0 FILE base.ldr\n0 NOFILE",
            "base_parts_summary": "2 plates",
            "car_info": "BMW M3 2020",
            "customization_request": "Wider fenders",
            "messages": [], "design_output": None, "status": "", "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        io_full_path = Path(settings.storage_path) / result["io_path"]
        assert io_full_path.exists()

        with zipfile.ZipFile(io_full_path, "r") as zf:
            names = zf.namelist()
            assert "model.ldr" in names
            assert "model2.ldr" in names
            assert ".info" in names
