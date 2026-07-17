# backend/tests/unit/services/test_design_fallback.py
"""Design fallback tests — graceful degradation to legacy single-shot."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.design_fallback import fallback_single_shot


@pytest.mark.asyncio
async def test_fallback_returns_dict_with_required_keys():
    state = {
        "design_id": "test-uuid",
        "make": "Ferrari", "model": "F40", "year": 1990,
        "scale": "1:38",
        "committed_parts": [],
        "metadata": {},
        "mod_ids": [],
        "custom_request": "",
        "flagship_metadata": None,
    }
    # Mock the legacy graph's ainvoke to avoid real LLM call
    async def mock_ainvoke(input_state):
        return {
            "status": "completed",
            "design_output": {"parts": [], "design_notes": "mocked"},
            "metadata": {"generator": "legacy_mock"},
            "parts_count": 0,
            "difficulty": "Easy",
            "io_path": "test-uuid/model.io",
            "ldr_path": "test-uuid/model.ldr",
            "ldr_content": "",
            "body_color_id": 4,
            "design_notes": "mocked",
            "parts_data": [],
            "error_message": "",
        }

    with patch("app.services.design_fallback.build_legacy_graph") as mock_build:
        mock_graph = mock_build.return_value
        mock_graph.ainvoke = mock_ainvoke
        result = await fallback_single_shot(state)

    assert isinstance(result, dict)
    # Must signal fallback in metadata for tracking
    assert result.get("metadata", {}).get("workflow") == "fallback_legacy"
    assert result.get("fallback_used") is True
