"""Unit tests for the vision-analysis LangGraph graph (Phase 3).

These tests mock the vision LLM at the `create_vision_llm` boundary — the
MockChatModel returns a preset `CarFeaturesOutput` Pydantic instance for
`with_structured_output()`. This lets us verify the parse_features node
logic (other→custom_* fallback, taxonomy suggestions) without real API calls.
"""

import base64
from pathlib import Path
from unittest.mock import patch

import pytest

from app.agents import vision_graph
from app.agents.vision_graph import build_vision_graph
from app.services.vision_analyzer import CarFeatures
from tests.conftest import MockChatModel


@pytest.fixture
def patch_vision_llm(mock_car_features_output):
    """Patch create_vision_llm to return a MockChatModel with preset CarFeaturesOutput."""
    from app.agents.vision_graph import CarFeaturesOutput
    output = CarFeaturesOutput(**mock_car_features_output)
    mock_llm = MockChatModel(structured_output=output)
    with patch.object(vision_graph, "create_vision_llm", return_value=mock_llm):
        yield mock_llm


@pytest.fixture
def tmp_image(tmp_path):
    """Create a minimal valid JPEG file for testing encode_image_node."""
    # A tiny 1x1 pixel JPEG (valid JPEG header + EOI marker)
    img_path = tmp_path / "test_car.jpg"
    # Minimal JPEG: SOI + APP0 + minimal data + EOI
    img_path.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xdb\x00C\x00\x08\xff\xd9")
    return str(img_path)


class TestEncodeImageNode:
    """encode_image_node: reads image file → base64 + media_type."""

    async def test_encodes_jpeg(self, tmp_image):
        """A .jpg file is read and base64-encoded with media_type=jpeg."""
        state = {"image_path": tmp_image}
        result = await vision_graph.encode_image_node(state)
        assert result["base64_image"]  # non-empty
        assert result["media_type"] == "jpeg"
        # Verify the base64 decodes back to the original bytes
        decoded = base64.b64decode(result["base64_image"])
        assert decoded == Path(tmp_image).read_bytes()

    async def test_missing_file_fails(self, tmp_path):
        """A non-existent image file returns a failed status."""
        state = {"image_path": str(tmp_path / "nonexistent.jpg")}
        result = await vision_graph.encode_image_node(state)
        assert result["status"] == "failed"
        assert "not found" in result["error_message"].lower()

    async def test_png_media_type(self, tmp_path):
        """A .png file gets media_type=png."""
        img_path = tmp_path / "car.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 20)
        state = {"image_path": str(img_path)}
        result = await vision_graph.encode_image_node(state)
        assert result["media_type"] == "png"

    async def test_includes_taxonomy_prompt(self, tmp_image):
        """The node populates taxonomy_prompt for the LLM node."""
        state = {"image_path": tmp_image}
        result = await vision_graph.encode_image_node(state)
        assert "Vehicle Classification Taxonomy" in result["taxonomy_prompt"]


class TestParseFeaturesNode:
    """parse_features_node: converts structured output dict → CarFeatures-shaped dict."""

    async def test_basic_parsing(self, patch_vision_llm, mock_car_features_output):
        """The parsed CarFeatures dict has the expected fields."""
        state = {"features_output": mock_car_features_output, "status": ""}
        result = await vision_graph.parse_features_node(state)
        assert result["status"] == "completed"
        car = result["car_features"]
        assert car["make"] == "Ferrari"
        assert car["model"] == "F40"
        assert car["year"] == 1987
        assert car["body_style"] == "sports_car"
        assert car["closest_lego_color"] == 4
        assert "analysis_text" in car

    async def test_other_body_style_uses_custom(self, patch_vision_llm, mock_car_features_output):
        """When body_style='other', the custom_body_style is used instead."""
        data = dict(mock_car_features_output)
        data["body_style"] = "other"
        data["custom_body_style"] = "3-wheeled reverse trike"
        state = {"features_output": data, "status": ""}
        result = await vision_graph.parse_features_node(state)
        car = result["car_features"]
        assert car["body_style"] == "3-wheeled reverse trike"

    async def test_other_era_uses_custom(self, patch_vision_llm, mock_car_features_output):
        """When era='other', the custom_era is used."""
        data = dict(mock_car_features_output)
        data["era"] = "other"
        data["custom_era"] = "art_deco"
        state = {"features_output": data, "status": ""}
        result = await vision_graph.parse_features_node(state)
        assert result["car_features"]["era"] == "art_deco"

    async def test_collects_taxonomy_suggestions(self, patch_vision_llm, mock_car_features_output):
        """Taxonomy suggestions from the LLM are propagated to the output."""
        data = dict(mock_car_features_output)
        data["taxonomy_suggestions"] = [{
            "category": "body_style",
            "suggested_id": "amphibious",
            "suggested_label": "Amphibious Vehicle",
            "description": "A car that can drive on land and water",
            "similar_existing": "suv",
        }]
        state = {"features_output": data, "status": ""}
        result = await vision_graph.parse_features_node(state)
        suggestions = result["taxonomy_suggestions"]
        assert any(s["suggested_id"] == "amphibious" for s in suggestions)

    async def test_auto_suggests_for_other_body_style(self, patch_vision_llm, mock_car_features_output):
        """When body_style='other' without an explicit suggestion, one is auto-created."""
        data = dict(mock_car_features_output)
        data["body_style"] = "other"
        data["custom_body_style"] = "hovercar"
        state = {"features_output": data, "status": ""}
        result = await vision_graph.parse_features_node(state)
        suggestions = result["taxonomy_suggestions"]
        assert any(s["suggested_id"] == "hovercar" for s in suggestions)

    async def test_empty_output_fails(self, patch_vision_llm):
        """Missing features_output returns a failure."""
        state = {"features_output": None, "status": ""}
        result = await vision_graph.parse_features_node(state)
        assert result["status"] == "failed"

    async def test_custom_features_merged_into_front(self, patch_vision_llm, mock_car_features_output):
        """custom_features are prepended to front_features with a CUSTOM: prefix."""
        data = dict(mock_car_features_output)
        data["custom_features"] = ["novel door design"]
        state = {"features_output": data, "status": ""}
        result = await vision_graph.parse_features_node(state)
        front = result["car_features"]["front_features"]
        assert any("CUSTOM: novel door design" == f for f in front)


class TestVisionGraphEndToEnd:
    """Full graph invocation with mocked vision LLM."""

    async def test_end_to_end_mocked(self, patch_vision_llm, tmp_image, mock_car_features_output):
        """The full graph reads the image, calls the (mocked) LLM, and returns CarFeatures."""
        graph = build_vision_graph()
        initial_state = {
            "image_path": tmp_image,
            "base64_image": "",
            "media_type": "jpeg",
            "taxonomy_prompt": "",
            "messages": [],
            "features_output": None,
            "car_features": None,
            "taxonomy_suggestions": [],
            "status": "",
            "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        assert result["status"] == "completed"
        car_dict = result["car_features"]
        assert car_dict is not None
        assert car_dict["make"] == "Ferrari"
        assert car_dict["model"] == "F40"

    async def test_missing_image_fails_gracefully(self, patch_vision_llm, tmp_path):
        """A non-existent image causes the graph to return status=failed."""
        graph = build_vision_graph()
        initial_state = {
            "image_path": str(tmp_path / "nonexistent.jpg"),
            "base64_image": "", "media_type": "jpeg", "taxonomy_prompt": "",
            "messages": [], "features_output": None, "car_features": None,
            "taxonomy_suggestions": [], "status": "", "error_message": "",
        }
        result = await graph.ainvoke(initial_state)
        assert result["status"] == "failed"
        assert result.get("car_features") is None
