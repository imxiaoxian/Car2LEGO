"""Unit tests for LDrawService — LDraw format helpers."""

import pytest
from app.services.ldraw_service import LDrawService


class TestGetColorName:
    """Color ID → color name mapping."""

    def test_known_colors(self):
        assert LDrawService.get_color_name(0) == "Black"
        assert LDrawService.get_color_name(1) == "Blue"
        assert LDrawService.get_color_name(4) == "Red"
        assert LDrawService.get_color_name(14) == "Yellow"
        assert LDrawService.get_color_name(15) == "White"
        assert LDrawService.get_color_name(71) == "Light Bluish Gray"
        assert LDrawService.get_color_name(72) == "Dark Bluish Gray"

    def test_unknown_color_returns_formatted_string(self):
        result = LDrawService.get_color_name(999)
        assert "999" in result

    def test_edge_color_ids(self):
        """Boundary values should not crash."""
        result0 = LDrawService.get_color_name(511)
        assert result0 is not None
        result1 = LDrawService.get_color_name(-1)
        assert result1 is not None


class TestGetColorHex:
    """Color ID → hex color mapping."""

    def test_known_colors(self):
        assert LDrawService.get_color_hex(15) == "#FFFFFF"  # White
        assert LDrawService.get_color_hex(0) == "#1B2A34"   # Black

    def test_unknown_color_default(self):
        result = LDrawService.get_color_hex(999)
        assert result == "#CCCCCC"


class TestMakePartLine:
    """LDraw part reference line generation."""

    def test_default_identity_rotation(self):
        line = LDrawService.make_part_line(color=4, x=0, y=-24, z=0,
                                            part_file="3024.dat")
        assert line.startswith("1 4 ")
        assert "3024.dat" in line
        assert "1.0000 0.0000 0.0000" in line  # identity rotation

    def test_custom_rotation(self):
        line = LDrawService.make_part_line(
            color=15, x=10, y=0, z=20, part_file="3001.dat",
            a=0, b=0, c=-1,  # 90° rotation
            d=0, e=1, f=0,
            g=1, h=0, i=0,
        )
        assert "-1.0000" in line  # rotation component

    def test_float_precision(self):
        line = LDrawService.make_part_line(color=0, x=1.5, y=-2.5, z=3.5,
                                            part_file="test.dat")
        assert "1.5000" in line
        assert "-2.5000" in line


class TestCreateBasicLdraw:
    """Complete LDraw file generation."""

    def test_creates_valid_ldraw_structure(self):
        parts = [(4, 0, -24, 0, "3024.dat"),
                 (15, 10, -48, 0, "3001.dat")]
        result = LDrawService.create_basic_ldraw(parts, name="Test Car")
        lines = result.split("\n")
        assert lines[0] == "0 Car2LEGO Generated Model"
        assert "0 Name: Test Car" in lines
        assert "0 Author: Car2LEGO" in lines
        # Should contain both part lines
        part_lines = [l for l in lines if l.startswith("1 ")]
        assert len(part_lines) == 2

    def test_empty_parts_list(self):
        result = LDrawService.create_basic_ldraw([], name="Empty")
        assert "0 Car2LEGO Generated Model" in result
        part_lines = [l for l in result.split("\n") if l.startswith("1 ")]
        assert len(part_lines) == 0
