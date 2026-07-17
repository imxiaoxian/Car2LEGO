# backend/tests/unit/agents/test_section_tools.py
"""Section tools tests — search_parts / get_brand_feature / validate_placement."""
from app.agents.section_tools import search_parts, get_brand_feature, validate_placement


def test_search_parts_finds_headlight():
    result = search_parts.invoke({"usage_keyword": "headlight"})
    assert isinstance(result, list)
    assert any("4070" in p["part_num"] for p in result)


def test_search_parts_returns_empty_for_unknown():
    result = search_parts.invoke({"usage_keyword": "nonexistent_xyz"})
    assert result == []


def test_get_brand_feature_for_ferrari_f40():
    result = get_brand_feature.invoke({
        "make": "Ferrari", "model": "F40", "feature_id": "",
    })
    # Returns dict (possibly empty if no library entry, but must be dict)
    assert isinstance(result, dict)


def test_validate_placement_rejects_negative_x():
    result = validate_placement.invoke({
        "x": -10.0, "y": 8.0, "z": 100.0,
        "part_num": "3020.dat", "section": "chassis",
    })
    assert result["valid"] is False
    assert "x" in result["reason"].lower()


def test_validate_placement_accepts_valid():
    result = validate_placement.invoke({
        "x": 40.0, "y": 8.0, "z": 100.0,
        "part_num": "3020.dat", "section": "chassis",
    })
    assert result["valid"] is True
