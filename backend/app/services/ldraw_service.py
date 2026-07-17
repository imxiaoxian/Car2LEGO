"""LDraw format service — parse and generate LDraw .ldr files.

LDraw file format:
  - Lines starting with '0' are comments/meta-commands
  - Lines starting with '1' are part references:
    1 <color> <x> <y> <z> <a> <b> <c> <d> <e> <f> <g> <h> <i> <file>
    (4x4 rotation matrix + position + part file reference)
  - Lines starting with '2'-'5' are geometric primitives

Color codes reference LDConfig.ldr (0-512).
"""


class LDrawService:
    """Handles LDraw file parsing, generation, and conversion."""

    # Core LEGO colors (subset of LDConfig.ldr)
    COLOR_MAP = {
        0: ("Black", "#1B2A34"),
        1: ("Blue", "#0051A8"),
        2: ("Green", "#237841"),
        4: ("Red", "#C91A09"),
        6: ("Brown", "#583927"),
        7: ("Light Gray", "#9BA19D"),
        14: ("Yellow", "#F5CD2F"),
        15: ("White", "#FFFFFF"),
        25: ("Orange", "#FE8A18"),
        71: ("Light Bluish Gray", "#A0A5A9"),
        72: ("Dark Bluish Gray", "#6C6E6C"),
        85: ("Dark Tan", "#958A73"),
    }

    @classmethod
    def get_color_name(cls, ldraw_color_id: int) -> str:
        entry = cls.COLOR_MAP.get(ldraw_color_id)
        return entry[0] if entry else f"Color_{ldraw_color_id}"

    @classmethod
    def get_color_hex(cls, ldraw_color_id: int) -> str:
        entry = cls.COLOR_MAP.get(ldraw_color_id)
        return entry[1] if entry else "#CCCCCC"

    @staticmethod
    def make_part_line(
        color: int,
        x: float,
        y: float,
        z: float,
        part_file: str,
        *,
        a: float = 1, b: float = 0, c: float = 0,
        d: float = 0, e: float = 1, f: float = 0,
        g: float = 0, h: float = 0, i: float = 1,
    ) -> str:
        """Generate a standard LDraw part reference line.

        Default rotation matrix is identity (no rotation).
        """
        return (
            f"1 {color} {x:.4f} {y:.4f} {z:.4f} "
            f"{a:.4f} {b:.4f} {c:.4f} "
            f"{d:.4f} {e:.4f} {f:.4f} "
            f"{g:.4f} {h:.4f} {i:.4f} "
            f"{part_file}"
        )

    @staticmethod
    def create_basic_ldraw(
        parts: list[tuple[int, float, float, float, str]],
        name: str = "Car2LEGO Model",
        author: str = "Car2LEGO",
    ) -> str:
        """Create a complete LDraw file from a list of part placements.

        Each part: (color_id, x, y, z, part_filename)
        """
        lines = [
            "0 Car2LEGO Generated Model",
            f"0 Name: {name}",
            f"0 Author: {author}",
            "0 !LICENSE Redistributable under CC BY 4.0",
            "",
        ]
        for color, x, y, z, part_file in parts:
            lines.append(
                LDrawService.make_part_line(color, x, y, z, part_file)
            )
        lines.append("0")

        return "\n".join(lines)
