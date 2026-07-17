"""Unit tests for TemplateParser — the Template-First merge engine.

Verifies parsing, filtering, recoloring, mirroring, validation, and end-to-end
merge of LDraw templates with LLM customizations.
"""

import pytest

from app.services.studio_templates import get_template_ldr
from app.services.template_parser import ParsedPart, TemplateParser


# ── parse_ldraw ──


class TestParseLdraw:
    def test_parses_sports_car_template(self):
        ldr = get_template_ldr("Ferrari")
        parts = TemplateParser.parse_ldraw(ldr)
        assert len(parts) > 10
        labels = {p.label for p in parts}
        assert "chassis" in labels
        assert "body_side" in labels

    def test_assigns_steps(self):
        ldr = get_template_ldr("Ferrari")
        parts = TemplateParser.parse_ldraw(ldr)
        steps = {p.step for p in parts}
        assert len(steps) > 1  # Multiple build steps

    def test_infers_label_without_comment(self):
        ldr = "1 7 0 8 30 1 0 0 0 1 0 0 0 1 3020.dat"
        parts = TemplateParser.parse_ldraw(ldr)
        assert len(parts) == 1
        assert parts[0].label == "chassis"  # 3020 at y=8 -> chassis

    def test_skips_non_part_lines(self):
        ldr = """0 FILE test.ldr
0 Name: Test
0 STEP
0 // ── Chassis Base ──
1 7 0 8 30 1 0 0 0 1 0 0 0 1 3020.dat
0 STEP
2 4 0 0 0 40 0 0 40 40 0
"""
        parts = TemplateParser.parse_ldraw(ldr)
        assert len(parts) == 1  # Only the `1` line parsed, `2` line skipped
        assert parts[0].part_num == "3020.dat"

    def test_malformed_part_line_skipped(self):
        ldr = "1 7 0 8 1 0 0 0 1 0 0 0 1 missingmatrix.dat"
        parts = TemplateParser.parse_ldraw(ldr)
        assert len(parts) == 0  # Too few tokens


# ── filter_right_half ──


class TestFilterRightHalf:
    def test_keeps_right_and_center(self):
        parts = [
            ParsedPart("3024.dat", 4, -40, 0, 0),
            ParsedPart("3024.dat", 4, 0, 0, 0),
            ParsedPart("3024.dat", 4, 40, 0, 0),
        ]
        right = TemplateParser.filter_right_half(parts)
        assert len(right) == 2  # X=0 and X=40 kept, X=-40 removed

    def test_keeps_tolerance_boundary(self):
        parts = [ParsedPart("3024.dat", 4, -0.05, 0, 0)]
        right = TemplateParser.filter_right_half(parts)
        assert len(right) == 1  # -0.05 >= -0.1, kept


# ── apply_recolor_rules ──


class TestApplyRecolorRules:
    def test_recolors_by_label(self):
        parts = [
            ParsedPart("3010.dat", 4, 40, 24, 90, label="body_side"),
            ParsedPart("3068b.dat", 4, 0, 96, 150, label="roof"),
        ]
        rules = [{"label": "body_side", "new_color_id": 15}]
        result = TemplateParser.apply_recolor_rules(parts, rules)
        assert result[0].color_id == 15  # Recolored
        assert result[1].color_id == 4  # Unchanged

    def test_multiple_rules(self):
        parts = [
            ParsedPart("3010.dat", 4, 40, 24, 90, label="body_side"),
            ParsedPart("3068b.dat", 4, 0, 96, 150, label="roof"),
            ParsedPart("3023.dat", 7, 40, 40, 300, label="bumper"),
        ]
        rules = [
            {"label": "body_side", "new_color_id": 4},
            {"label": "roof", "new_color_id": 0},
            {"label": "bumper", "new_color_id": 0},
        ]
        result = TemplateParser.apply_recolor_rules(parts, rules)
        assert result[0].color_id == 4
        assert result[1].color_id == 0
        assert result[2].color_id == 0

    def test_empty_rules_no_change(self):
        parts = [ParsedPart("3010.dat", 4, 40, 24, 90, label="body_side")]
        result = TemplateParser.apply_recolor_rules(parts, [])
        assert result[0].color_id == 4


# ── apply_replace_rules ──


class TestApplyReplaceRules:
    def test_replaces_part_by_label(self):
        parts = [
            ParsedPart("3023.dat", 4, 40, 24, 90, label="headlight"),
            ParsedPart("3068b.dat", 4, 0, 96, 150, label="roof"),
        ]
        rules = [
            {"target_label": "headlight", "new_part_num": "4070.dat", "new_color_id": 14}
        ]
        result = TemplateParser.apply_replace_rules(parts, rules)
        assert result[0].part_num == "4070.dat"
        assert result[0].color_id == 14
        assert result[1].part_num == "3068b.dat"  # Unchanged

    def test_keeps_position(self):
        parts = [
            ParsedPart("3023.dat", 4, 40, 24, 90, label="headlight"),
        ]
        rules = [
            {"target_label": "headlight", "new_part_num": "4070.dat", "new_color_id": 14}
        ]
        result = TemplateParser.apply_replace_rules(parts, rules)
        assert result[0].x == 40
        assert result[0].y == 24
        assert result[0].z == 90

    def test_no_match_no_change(self):
        parts = [
            ParsedPart("3023.dat", 4, 40, 24, 90, label="headlight"),
        ]
        rules = [
            {"target_label": "bumper", "new_part_num": "3024.dat", "new_color_id": 0}
        ]
        result = TemplateParser.apply_replace_rules(parts, rules)
        assert result[0].part_num == "3023.dat"  # No change
        assert result[0].color_id == 4

    def test_updates_rotation(self):
        parts = [
            ParsedPart("3023.dat", 4, 40, 24, 90, label="headlight"),
        ]
        new_rot = "0 0 1 0 1 0 -1 0 0"
        rules = [
            {
                "target_label": "headlight",
                "new_part_num": "4070.dat",
                "new_color_id": 14,
                "rotation": new_rot,
            }
        ]
        result = TemplateParser.apply_replace_rules(parts, rules)
        assert result[0].rotation == [0, 0, 1, 0, 1, 0, -1, 0, 0]


# ── add_extra_parts ──


class TestAddExtraParts:
    def test_adds_parts(self):
        base = [ParsedPart("3020.dat", 7, 0, 8, 30, label="chassis")]
        extras = [
            {
                "part_num": "3023.dat",
                "color_id": 0,
                "x": 40,
                "y": 96,
                "z": 20,
                "rotation": "1 0 0 0 1 0 0 0 1",
            }
        ]
        result = TemplateParser.add_extra_parts(base, extras, base_step=5)
        assert len(result) == 2
        assert result[1].part_num == "3023.dat"
        assert result[1].label == "extra"
        assert result[1].step == 5

    def test_malored_rotation_falls_back_to_identity(self):
        base = []
        extras = [
            {
                "part_num": "3023.dat",
                "color_id": 0,
                "x": 40,
                "y": 96,
                "z": 20,
                "rotation": "bad rotation",
            }
        ]
        result = TemplateParser.add_extra_parts(base, extras, base_step=1)
        assert result[0].rotation == [1, 0, 0, 0, 1, 0, 0, 0, 1]


# ── snap_to_grid ──


class TestSnapToGrid:
    def test_snaps_extra_parts(self):
        parts = [
            ParsedPart("3020.dat", 7, 0, 8, 30, label="chassis"),
            ParsedPart("3023.dat", 0, 35, 90, 17, label="extra"),
        ]
        result = TemplateParser.snap_to_grid(parts)
        # Template part unchanged
        assert result[0].x == 0
        assert result[0].z == 30
        # Extra part snapped
        assert result[1].x == 40  # 35 -> 40 (nearest multiple of 20)
        assert result[1].z == 20  # 17 -> 20
        assert result[1].y == 88  # 90 -> 88 (nearest multiple of 8)


# ── mirror_parts ──


class TestMirrorParts:
    def test_mirrors_positive_x(self):
        parts = [ParsedPart("3024.dat", 4, 40, 0, 0)]
        mirrored = TemplateParser.mirror_parts(parts)
        assert len(mirrored) == 2
        assert mirrored[0].x == 40
        assert mirrored[1].x == -40

    def test_does_not_mirror_center(self):
        parts = [ParsedPart("3024.dat", 4, 0, 0, 0)]
        mirrored = TemplateParser.mirror_parts(parts)
        assert len(mirrored) == 1  # X=0 not mirrored

    def test_flips_rotation_x_column(self):
        parts = [
            ParsedPart(
                "3024.dat",
                4,
                40,
                0,
                0,
                rotation=[0, 0, 1, 0, 1, 0, -1, 0, 0],
            )
        ]
        mirrored = TemplateParser.mirror_parts(parts)
        # X-column (indices 0, 3, 6) should be negated
        assert mirrored[1].rotation[0] == 0  # -0 = 0
        assert mirrored[1].rotation[3] == 0  # -0 = 0
        assert mirrored[1].rotation[6] == 1  # -(-1) = 1


# ── validate_bounding_box ──


class TestValidateBoundingBox:
    def test_valid_parts_pass(self):
        parts = [ParsedPart("3024.dat", 4, 40, 24, 100)]
        ok, msg = TemplateParser.validate_bounding_box(parts, "1:38")
        assert ok

    def test_x_exceeds_fails(self):
        parts = [ParsedPart("3024.dat", 4, 200, 24, 100)]
        ok, msg = TemplateParser.validate_bounding_box(parts, "1:38")
        assert not ok
        assert "X" in msg

    def test_z_exceeds_fails(self):
        parts = [ParsedPart("3024.dat", 4, 40, 24, 500)]
        ok, msg = TemplateParser.validate_bounding_box(parts, "1:38")
        assert not ok
        assert "Z" in msg

    def test_y_exceeds_fails(self):
        parts = [ParsedPart("3024.dat", 4, 40, 200, 100)]
        ok, msg = TemplateParser.validate_bounding_box(parts, "1:38")
        assert not ok
        assert "Y" in msg


# ── merge_design (end-to-end) ──


class TestMergeDesign:
    def test_end_to_end_merge(self):
        ldr = get_template_ldr("Ferrari")
        customization = {
            "body_color_id": 4,
            "accent_color_id": 0,
            "recolor_rules": [{"label": "body_side", "new_color_id": 4}],
            "extra_parts": [
                {"part_num": "3023.dat", "color_id": 0, "x": 40, "y": 96, "z": 20},
            ],
            "design_notes": "Test.",
        }
        result = TemplateParser.merge_design(ldr, customization, scale="1:38")
        assert "error" not in result
        assert result["body_color_id"] == 4
        assert len(result["parts"]) > 10  # Template + extras + mirrors

    def test_recolor_applied_in_merge(self):
        ldr = get_template_ldr("Ferrari")
        customization = {
            "body_color_id": 15,  # White
            "accent_color_id": 0,
            "recolor_rules": [{"label": "body_side", "new_color_id": 15}],
            "extra_parts": [],
            "design_notes": "White car.",
        }
        result = TemplateParser.merge_design(ldr, customization, scale="1:38")
        assert "error" not in result
        # At least one body_side part should now be color 15
        body_side_parts = [
            p for p in result["parts"] if p.get("color_id") == 15
        ]
        assert len(body_side_parts) > 0

    def test_too_many_extras_returns_error(self):
        ldr = get_template_ldr("Ferrari")
        extras = [
            {"part_num": "3023.dat", "color_id": 0, "x": 20, "y": 40, "z": 100}
            for _ in range(30)
        ]
        customization = {
            "body_color_id": 4,
            "accent_color_id": 0,
            "recolor_rules": [],
            "extra_parts": extras,
            "design_notes": "",
        }
        result = TemplateParser.merge_design(ldr, customization, scale="1:38")
        assert "error" in result

    def test_extra_parts_appear_in_output(self):
        ldr = get_template_ldr("Ferrari")
        customization = {
            "body_color_id": 4,
            "accent_color_id": 0,
            "recolor_rules": [],
            "extra_parts": [
                {"part_num": "3023.dat", "color_id": 0, "x": 40, "y": 96, "z": 20},
            ],
            "design_notes": "With extra.",
        }
        result = TemplateParser.merge_design(ldr, customization, scale="1:38")
        assert "error" not in result
        # The extra part should appear at least once (and its mirror)
        extra_parts = [
            p for p in result["parts"] if p["part_num"] == "3023.dat"
        ]
        assert len(extra_parts) >= 1

    def test_output_is_right_half_only(self):
        """merge_design does NOT mirror — _build_ldraw handles mirroring."""
        ldr = get_template_ldr("Ferrari")
        customization = {
            "body_color_id": 4,
            "accent_color_id": 0,
            "recolor_rules": [],
            "extra_parts": [],
            "design_notes": "",
        }
        result = TemplateParser.merge_design(ldr, customization, scale="1:38")
        assert "error" not in result
        parts = result["parts"]
        # All parts should have X >= 0 (right half + center, NOT mirrored)
        right_count = sum(1 for p in parts if p["x"] > 0.1)
        left_count = sum(1 for p in parts if p["x"] < -0.1)
        assert right_count > 0
        assert left_count == 0  # No left-side parts — mirroring is _build_ldraw's job


# ── compute_reference_points ──


class TestComputeReferencePoints:
    def test_returns_expected_keys(self):
        parts = [
            ParsedPart("3020.dat", 7, 40, 8, 30, label="chassis"),
            ParsedPart("3068b.dat", 4, 0, 96, 150, label="roof"),
            ParsedPart("4624c00.dat", 0, 40, 8, 60, label="wheel"),
        ]
        ref = TemplateParser.compute_reference_points(parts)
        assert "front_z" in ref
        assert "rear_z" in ref
        assert "roof_y" in ref
        assert "chassis_y" in ref
        assert "right_edge_x" in ref
        assert "wheel_front_z" in ref
        assert "wheel_rear_z" in ref

    def test_empty_parts_returns_defaults(self):
        ref = TemplateParser.compute_reference_points([])
        assert ref["front_z"] == 300
        assert ref["rear_z"] == 10
        assert ref["right_edge_x"] == 60
