"""Template LDraw parser — converts template text to structured part placements.

Parses LDraw template strings into `ParsedPart` objects with semantic labels,
filters to right-half (X >= 0), applies recolor rules, adds extra parts,
snaps to grid, mirrors, and validates the bounding box.

Used by the design graph's `parse_template_node` and `merge_and_validate_node`
to provide a deterministic structural base that the LLM only customizes
(colors + brand-specific detail parts) rather than generating from scratch.
"""

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.services.lego_parts_knowledge import CAR_PARTS_CATALOG
from app.services.studio_templates import get_scale_spec


@dataclass
class ParsedPart:
    """A single LEGO part placement parsed from a template."""

    part_num: str
    color_id: int
    x: float
    y: float
    z: float
    rotation: list[float] = field(default_factory=lambda: [1, 0, 0, 0, 1, 0, 0, 0, 1])
    step: int = 1
    label: str = "detail"


class TemplateParser:
    """Parse LDraw templates and merge LLM customizations deterministically."""

    COMMENT_LABEL_MAP: dict[str, str] = {
        "chassis base": "chassis",
        "chassis frame": "chassis_frame",
        "rear body": "rear_body",
        "engine cover": "rear_body",
        "side panels": "body_side",
        "side panel": "body_side",
        "body side": "body_side",
        "sidepod": "sidepod",
        "cabin": "cabin",
        "cockpit": "cabin",
        "windshield": "windshield",
        "windscreen": "windshield",
        "roof": "roof",
        "front hood": "hood",
        "hood": "hood",
        "nose cone": "nose_cone",
        "front bumper": "bumper",
        "bumper": "bumper",
        "headlights": "headlight",
        "headlight": "headlight",
        "taillights": "taillight",
        "taillight": "taillight",
        "rear lights": "taillight",
        "wheel arches": "wheel_arch",
        "wheel arch": "wheel_arch",
        "wheels": "wheel",
        "wheel": "wheel",
        "rear diffuser": "diffuser",
        "diffuser": "diffuser",
        "side skirt": "side_skirt",
        "spoiler": "spoiler",
        "rear wing": "rear_wing",
        "front wing": "front_wing",
        "cargo bed": "cargo_bed",
        "engine": "engine",
        "halo": "halo",
        "front splitter": "splitter",
        "air intake": "air_intake",
        "exhaust": "exhaust",
        "mirror": "mirror",
    }

    @classmethod
    def parse_ldraw(cls, ldr_text: str) -> list[ParsedPart]:
        """Parse LDraw text into structured ParsedPart list.

        Tracks section comments (`0 // ── XXX ──`) for semantic labels
        and `0 STEP` lines for build step numbers.
        """
        parts: list[ParsedPart] = []
        current_step = 0
        current_label = "detail"

        for raw_line in ldr_text.split("\n"):
            line = raw_line.strip()
            if not line:
                continue

            if line.startswith("0 STEP"):
                current_step += 1
                continue

            if line.startswith("0 //"):
                comment_text = line[4:].strip().lstrip("─").strip().lower()
                matched = cls._match_comment_label(comment_text)
                if matched:
                    current_label = matched
                continue

            if line.startswith("0 "):
                continue

            if line.startswith("1 "):
                parsed = cls._parse_part_line(line, current_step, current_label)
                if parsed:
                    parts.append(parsed)

        return parts

    @classmethod
    def _match_comment_label(cls, comment_text: str) -> str | None:
        """Match a comment string to a semantic label."""
        for key, label in cls.COMMENT_LABEL_MAP.items():
            if key in comment_text:
                return label
        return None

    @classmethod
    def _parse_part_line(
        cls, line: str, step: int, label: str
    ) -> ParsedPart | None:
        """Parse a `1 <color> <x> <y> <z> <9 matrix> <part>` line."""
        tokens = line.split()
        if len(tokens) < 15:
            return None

        try:
            color_id = int(tokens[1])
            x = float(tokens[2])
            y = float(tokens[3])
            z = float(tokens[4])
            rotation = [float(t) for t in tokens[5:14]]
            part_num = tokens[-1]
        except (ValueError, IndexError):
            return None

        if not label or label == "detail":
            label = cls.infer_label(part_num, x, y, z)

        return ParsedPart(
            part_num=part_num,
            color_id=color_id,
            x=x,
            y=y,
            z=z,
            rotation=rotation,
            step=step,
            label=label,
        )

    @classmethod
    def infer_label(cls, part_num: str, x: float, y: float, z: float) -> str:
        """Infer a semantic label from part characteristics when no comment exists."""
        part_lower = part_num.lower()

        if part_lower.startswith(("4624", "56904", "6014")):
            return "wheel"
        if part_lower.startswith(("3823", "2437", "4176")):
            return "windshield"
        if part_lower.startswith("4070"):
            return "headlight" if z > 150 else "taillight"
        if part_lower.startswith(("11477", "50950")):
            return "wheel_arch"
        if part_lower.startswith(("3020", "3021", "3022", "3460", "3034", "4282", "3795", "3666")):
            return "chassis" if y <= 16 else "body_side"
        if part_lower.startswith(("3068b", "87079")):
            return "roof" if y >= 80 else "body_side"
        if part_lower.startswith(("3010", "3004", "3009", "3008", "3001", "3622", "3002", "2456")):
            return "body_side" if 16 < y < 80 else "chassis"
        if part_lower.startswith("3298"):
            return "hood"
        if part_lower.startswith("3023"):
            return "bumper"
        if part_lower.startswith("30236"):
            return "headlight"

        return "detail"

    @classmethod
    def filter_right_half(cls, parts: list[ParsedPart]) -> list[ParsedPart]:
        """Keep only parts with X >= -0.1 (right half + center line)."""
        return [p for p in parts if p.x >= -0.1]

    @classmethod
    def apply_recolor_rules(
        cls, parts: list[ParsedPart], rules: list[dict]
    ) -> list[ParsedPart]:
        """Recolor parts matching semantic labels.

        rules: [{"label": "body_side", "new_color_id": 4}, ...]
        """
        rule_map: dict[str, int] = {}
        for r in rules:
            label = r.get("label", "")
            color = r.get("new_color_id")
            if label and color is not None:
                rule_map[label] = int(color)

        for p in parts:
            if p.label in rule_map:
                p.color_id = rule_map[p.label]

        return parts

    @classmethod
    def apply_replace_rules(
        cls, parts: list[ParsedPart], rules: list[dict]
    ) -> list[ParsedPart]:
        """Replace parts matching target_label with new part_num/color/rotation.

        rules: [{"target_label": "headlight", "new_part_num": "2412b.dat",
                 "new_color_id": 0, "rotation": "1 0 0 0 1 0 0 0 1"}, ...]

        The new part inherits the original position (x, y, z); only part_num,
        color_id, and optionally rotation change.
        """
        rule_map: dict[str, dict] = {}
        for r in rules:
            label = r.get("target_label", "")
            if label:
                rule_map[label] = r

        for p in parts:
            if p.label in rule_map:
                rule = rule_map[p.label]
                new_part = rule.get("new_part_num", "")
                if new_part:
                    p.part_num = new_part
                if "new_color_id" in rule and rule["new_color_id"] is not None:
                    p.color_id = int(rule["new_color_id"])
                rot_str = rule.get("rotation", "")
                if rot_str:
                    try:
                        rot = [float(v) for v in rot_str.split()]
                        if len(rot) == 9:
                            p.rotation = rot
                    except ValueError:
                        pass

        return parts

    @classmethod
    def add_extra_parts(
        cls,
        parts: list[ParsedPart],
        extras: list[dict],
        base_step: int,
    ) -> list[ParsedPart]:
        """Add LLM-specified extra parts to the list."""
        result = list(parts)
        for ep in extras:
            part_num = ep.get("part_num", "")
            if not part_num:
                continue
            x = float(ep.get("x", 0))
            y = float(ep.get("y", 0))
            z = float(ep.get("z", 0))
            rotation_str = ep.get("rotation", "1 0 0 0 1 0 0 0 1")
            try:
                rotation = [float(v) for v in rotation_str.split()]
            except ValueError:
                rotation = [1, 0, 0, 0, 1, 0, 0, 0, 1]
            if len(rotation) != 9:
                rotation = [1, 0, 0, 0, 1, 0, 0, 0, 1]

            result.append(
                ParsedPart(
                    part_num=part_num,
                    color_id=int(ep.get("color_id", 0)),
                    x=x,
                    y=y,
                    z=z,
                    rotation=rotation,
                    step=ep.get("step", base_step) or base_step,
                    label="extra",
                )
            )
        return result

    @classmethod
    def snap_to_grid(cls, parts: list[ParsedPart]) -> list[ParsedPart]:
        """Snap extra parts to LDU grid (template parts are already aligned)."""
        for p in parts:
            if p.label == "extra":
                p.x = round(p.x / 20.0) * 20.0
                p.z = round(p.z / 20.0) * 20.0
                p.y = round(p.y / 8.0) * 8.0
        return parts

    @classmethod
    def mirror_parts(cls, parts: list[ParsedPart]) -> list[ParsedPart]:
        """Mirror parts with X > 0.1 to -X, flipping rotation matrix X-column."""
        result: list[ParsedPart] = []
        for p in parts:
            result.append(p)
            if abs(p.x) > 0.1:
                mirrored = ParsedPart(
                    part_num=p.part_num,
                    color_id=p.color_id,
                    x=-p.x,
                    y=p.y,
                    z=p.z,
                    rotation=list(p.rotation),
                    step=p.step,
                    label=p.label,
                )
                rot = mirrored.rotation
                rot[0] = -rot[0]
                rot[3] = -rot[3]
                rot[6] = -rot[6]
                result.append(mirrored)
        return result

    @classmethod
    def validate_bounding_box(
        cls, parts: list[ParsedPart], scale: str = "1:38"
    ) -> tuple[bool, str]:
        """Check that all parts are within the scale's bounding box.

        SCALE_SPECS dimensions are total car size (length/width/height), not
        coordinate ranges. A 360-LDU-long car spans Z=0 to Z=360, a 160-LDU-wide
        car spans X=-80 to X=+80.
        """
        spec = get_scale_spec(scale)
        z_max = spec["length_ldu"][1]
        x_half_max = spec["width_ldu"][1] / 2
        y_max = spec["height_ldu"][1]
        tol = 1.2

        for p in parts:
            if abs(p.x) > x_half_max * tol:
                return False, f"Part {p.part_num} X={p.x} exceeds width ±{x_half_max}"
            if p.z < -20 or p.z > z_max * tol:
                return False, f"Part {p.part_num} Z={p.z} exceeds length 0-{z_max}"
            if p.y < -8 or p.y > y_max * tol:
                return False, f"Part {p.part_num} Y={p.y} exceeds height 0-{y_max}"
        return True, ""

    @classmethod
    def to_design_output(
        cls,
        parts: list[ParsedPart],
        body_color_id: int,
        design_notes: str,
        catalog: list = None,
    ) -> dict:
        """Convert ParsedPart list to _build_ldraw-compatible design_output dict."""
        if catalog is None:
            catalog = CAR_PARTS_CATALOG

        bl_map: dict[str, str] = {}
        for p in catalog:
            bl_map[p.part_num] = p.bricklink_id

        color_names: dict[int, str] = {}
        from app.services.lego_parts_knowledge import CAR_COLORS

        for cid, (cname, _) in CAR_COLORS.items():
            color_names[cid] = cname

        parts_list: list[dict] = []
        total = 0
        for p in parts:
            bl_id = bl_map.get(p.part_num, p.part_num.replace(".dat", ""))
            cname = color_names.get(p.color_id, f"Color_{p.color_id}")
            rot_str = " ".join(f"{v:.6g}" for v in p.rotation)
            parts_list.append(
                {
                    "part_num": p.part_num,
                    "bricklink_id": bl_id,
                    "color_id": p.color_id,
                    "color_name": cname,
                    "x": p.x,
                    "y": p.y,
                    "z": p.z,
                    "rotation": rot_str,
                    "quantity": 1,
                    "step": p.step,
                }
            )
            total += 1

        return {
            "design_notes": design_notes,
            "total_parts": total,
            "body_color_id": body_color_id,
            "parts": parts_list,
        }

    @classmethod
    def merge_design(
        cls,
        template_ldr: str,
        customization: dict,
        catalog: list = None,
        scale: str = "1:38",
    ) -> dict:
        """Main merge function — chains all steps.

        1. Parse template LDraw
        2. Filter to right half (X >= 0)
        3. Apply recolor rules
        4. Add extra parts
        5. Snap extra parts to grid
        6. Validate bounding box
        7. Convert to design_output dict (right-half only — _build_ldraw mirrors)

        Returns dict compatible with _build_ldraw, or {"error": "..."} on failure.

        Note: Mirroring is intentionally NOT done here. `_build_ldraw` and
        `_build_parts_data` handle auto-mirroring (each part with X > 0 gets
        a copy at -X). This keeps the merge output consistent with the
        customization graph's LLM output (also right-half-only).
        """
        if catalog is None:
            catalog = CAR_PARTS_CATALOG

        all_parts = cls.parse_ldraw(template_ldr)
        right_half = cls.filter_right_half(all_parts)

        recolor_rules = customization.get("recolor_rules", [])
        right_half = cls.apply_recolor_rules(right_half, recolor_rules)

        replace_rules = customization.get("replace_rules", [])
        right_half = cls.apply_replace_rules(right_half, replace_rules)

        extra_parts = customization.get("extra_parts", [])
        if len(extra_parts) > 25:
            return {"error": f"Too many extra parts: {len(extra_parts)} (max 25)"}

        max_step = max((p.step for p in right_half), default=0)
        merged = cls.add_extra_parts(right_half, extra_parts, base_step=max_step + 1)

        merged = cls.snap_to_grid(merged)

        ok, msg = cls.validate_bounding_box(merged, scale)
        if not ok:
            return {"error": msg}

        body_color_id = customization.get("body_color_id", 4)
        design_notes = customization.get("design_notes", "")

        return cls.to_design_output(merged, body_color_id, design_notes, catalog)

    @classmethod
    def to_json_for_prompt(cls, parts: list[ParsedPart]) -> str:
        """Serialize parts as compact JSON for the LLM prompt."""
        lines: list[dict] = []
        for p in parts:
            lines.append(
                {
                    "part_num": p.part_num,
                    "color_id": p.color_id,
                    "x": p.x,
                    "y": p.y,
                    "z": p.z,
                    "rotation": " ".join(f"{v:.0f}" for v in p.rotation),
                    "step": p.step,
                    "label": p.label,
                }
            )
        return json.dumps(lines, indent=2, ensure_ascii=False)

    @classmethod
    def compute_reference_points(cls, parts: list[ParsedPart]) -> dict:
        """Compute key reference coordinates from the parsed parts."""
        if not parts:
            return {
                "front_z": 300,
                "rear_z": 10,
                "roof_y": 96,
                "chassis_y": 8,
                "right_edge_x": 60,
                "center_x": 0,
                "wheel_front_z": 60,
                "wheel_rear_z": 200,
            }

        xs = [p.x for p in parts]
        ys = [p.y for p in parts]
        zs = [p.z for p in parts]
        wheels = [p for p in parts if p.label == "wheel"]
        wheel_zs = [p.z for p in wheels] if wheels else [60, 200]

        return {
            "front_z": max(zs),
            "rear_z": min(zs),
            "roof_y": max(ys),
            "chassis_y": min(ys),
            "right_edge_x": max(xs),
            "center_x": 0,
            "wheel_front_z": min(wheel_zs),
            "wheel_rear_z": max(wheel_zs),
        }
