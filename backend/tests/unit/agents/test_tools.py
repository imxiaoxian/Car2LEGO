"""Unit tests for the @tool functions in app/agents/tools.py.

These tests call the tool functions directly (via `.invoke()`) without any
LangChain runtime — they verify the catalog-lookup logic against the real
CAR_PARTS_CATALOG and CAR_TEMPLATES data.
"""

import pytest

from app.agents.tools import (
    DESIGN_TOOLS,
    get_brand_color,
    get_template_info,
    search_parts_catalog,
    validate_part_exists,
)


class TestSearchPartsCatalog:
    """search_parts_catalog tool — keyword search over the curated catalog."""

    def test_finds_wheels(self):
        """Searching 'wheel' returns wheel parts."""
        results = search_parts_catalog.invoke({"query": "wheel"})
        assert isinstance(results, list)
        assert len(results) > 0
        # All results should contain the query keyword in name or usage
        for r in results:
            assert "wheel" in r["name"].lower() or "wheel" in r["usage"].lower()
        # Each result has the expected fields
        first = results[0]
        assert "part_num" in first
        assert "bricklink_id" in first
        assert "name" in first
        assert "category" in first
        assert "size" in first
        assert "usage" in first

    def test_finds_plate(self):
        """Searching 'plate' returns plate parts."""
        results = search_parts_catalog.invoke({"query": "plate"})
        assert len(results) > 0
        assert any("plate" in r["name"].lower() for r in results)

    def test_empty_query_returns_empty(self):
        """Empty/whitespace query returns empty list."""
        assert search_parts_catalog.invoke({"query": ""}) == []
        assert search_parts_catalog.invoke({"query": "   "}) == []

    def test_no_match_returns_empty(self):
        """A nonsense query returns an empty list."""
        results = search_parts_catalog.invoke({"query": "zzz_nonexistent_zzz"})
        assert results == []

    def test_max_ten_results(self):
        """Results are capped at 10 entries."""
        # 'plate' matches many catalog entries; verify cap
        results = search_parts_catalog.invoke({"query": "plate"})
        assert len(results) <= 10


class TestGetBrandColor:
    """get_brand_color tool — canonical LEGO color IDs per car brand."""

    def test_ferrari(self):
        """Ferrari → primary color_id=4 (Red)."""
        result = get_brand_color.invoke({"make": "Ferrari"})
        assert result["primary_color_id"] == 4
        assert result["primary_color_name"].lower() == "red"
        assert isinstance(result["secondary_color_ids"], list)

    def test_lamborghini_has_secondary(self):
        """Lamborghini → primary=27 (Lime), secondary=[14] (Yellow)."""
        result = get_brand_color.invoke({"make": "Lamborghini"})
        assert result["primary_color_id"] == 27
        assert 14 in result["secondary_color_ids"]

    def test_case_insensitive(self):
        """Brand lookup is case-insensitive."""
        lower = get_brand_color.invoke({"make": "ferrari"})
        upper = get_brand_color.invoke({"make": "FERRARI"})
        assert lower["primary_color_id"] == upper["primary_color_id"] == 4

    def test_unknown_brand_defaults_to_white(self):
        """Unknown brand → primary_color_id=15 (White)."""
        result = get_brand_color.invoke({"make": "UnknownBrandXYZ"})
        assert result["primary_color_id"] == 15
        assert "white" in result["primary_color_name"].lower()

    def test_chevy_alias(self):
        """'chevy' is an alias for 'chevrolet'."""
        chevy = get_brand_color.invoke({"make": "chevy"})
        chevrolet = get_brand_color.invoke({"make": "chevrolet"})
        assert chevy["primary_color_id"] == chevrolet["primary_color_id"] == 4


class TestValidatePartExists:
    """validate_part_exists tool — checks part_num against the catalog."""

    def test_valid_part(self):
        """A known part_num returns True."""
        assert validate_part_exists.invoke({"part_num": "3024.dat"}) is True

    def test_another_valid_part(self):
        """A wheel part returns True."""
        assert validate_part_exists.invoke({"part_num": "4624.dat"}) is True

    def test_invalid_part(self):
        """A fabricated part_num returns False."""
        assert validate_part_exists.invoke({"part_num": "9999.dat"}) is False

    def test_empty_string(self):
        """Empty string returns False."""
        assert validate_part_exists.invoke({"part_num": ""}) is False

    def test_part_without_dat_suffix(self):
        """A part_num without .dat suffix returns False (exact match required)."""
        assert validate_part_exists.invoke({"part_num": "3024"}) is False


class TestGetTemplateInfo:
    """get_template_info tool — chassis template lookup by car make."""

    def test_ferrari_returns_sports_car(self):
        """Ferrari maps to the sports_car template."""
        result = get_template_info.invoke({"make": "Ferrari"})
        assert result["template_id"] == "sports_car"
        assert "name" in result
        assert "body_style" in result
        assert "default_color_id" in result
        assert "template_ldr_preview" in result
        # Preview should be non-empty LDraw content
        assert len(result["template_ldr_preview"]) > 0

    def test_jeep_returns_suv(self):
        """Jeep maps to the suv template."""
        result = get_template_info.invoke({"make": "Jeep Wrangler"})
        assert result["template_id"] == "suv"

    def test_preview_is_truncated(self):
        """The template_ldr_preview is capped at 2000 chars."""
        result = get_template_info.invoke({"make": "Ferrari"})
        assert len(result["template_ldr_preview"]) <= 2000


class TestDesignToolsExport:
    """DESIGN_TOOLS list contains all 4 tools."""

    def test_four_tools(self):
        assert len(DESIGN_TOOLS) == 4

    def test_tool_names(self):
        names = {t.name for t in DESIGN_TOOLS}
        assert names == {
            "search_parts_catalog",
            "get_brand_color",
            "get_template_info",
            "validate_part_exists",
        }
