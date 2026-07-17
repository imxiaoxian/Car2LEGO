"""Color mapping service — convert RGB colors to nearest LEGO colors.

Used by the L3/L4 matching pipeline to sample colors from car images
and map them to the closest LEGO brick colors.
"""

from dataclasses import dataclass


@dataclass
class LegoColor:
    id: int
    name: str
    hex_rgb: str
    rgb: tuple[int, int, int]


# Standard LEGO color palette (~40 most common colors)
LEGO_COLORS = [
    LegoColor(0, "Black", "#1B2A34", (27, 42, 52)),
    LegoColor(1, "Blue", "#0051A8", (0, 81, 168)),
    LegoColor(2, "Green", "#237841", (35, 120, 65)),
    LegoColor(4, "Red", "#C91A09", (201, 26, 9)),
    LegoColor(5, "Dark Pink", "#C870A0", (200, 112, 160)),
    LegoColor(6, "Brown", "#583927", (88, 57, 39)),
    LegoColor(7, "Light Gray", "#9BA19D", (155, 161, 157)),
    LegoColor(8, "Dark Gray", "#6D6E6C", (109, 110, 108)),
    LegoColor(9, "Light Blue", "#B4D2E7", (180, 210, 231)),
    LegoColor(10, "Bright Green", "#4B9F4A", (75, 159, 74)),
    LegoColor(11, "Light Turquoise", "#55A5AF", (85, 165, 175)),
    LegoColor(12, "Salmon", "#F2705E", (242, 112, 94)),
    LegoColor(13, "Pink", "#FC97AC", (252, 151, 172)),
    LegoColor(14, "Yellow", "#F5CD2F", (245, 205, 47)),
    LegoColor(15, "White", "#FFFFFF", (255, 255, 255)),
    LegoColor(17, "Light Green", "#C2DAB8", (194, 218, 184)),
    LegoColor(18, "Light Yellow", "#FBE696", (251, 230, 150)),
    LegoColor(19, "Tan", "#E4CD9E", (228, 205, 158)),
    LegoColor(20, "Light Violet", "#CDA4DE", (205, 164, 222)),
    LegoColor(21, "Glow in Dark Opaque", "#D4D5C9", (212, 213, 201)),
    LegoColor(22, "Purple", "#81007B", (129, 0, 123)),
    LegoColor(23, "Dark Blue-Violet", "#2032B0", (32, 50, 176)),
    LegoColor(25, "Orange", "#FE8A18", (254, 138, 24)),
    LegoColor(26, "Magenta", "#923978", (146, 57, 120)),
    LegoColor(27, "Lime", "#BBE90B", (187, 233, 11)),
    LegoColor(28, "Dark Tan", "#958A73", (149, 138, 115)),
    LegoColor(29, "Bright Pink", "#E4ADC8", (228, 173, 200)),
    LegoColor(31, "Medium Lavender", "#AC78BA", (172, 120, 186)),
    LegoColor(33, "Trans-Black", "#635F52", (99, 95, 82)),
    LegoColor(34, "Trans-Red", "#C91A09", (201, 26, 9)),
    LegoColor(71, "Light Bluish Gray", "#A0A5A9", (160, 165, 169)),
    LegoColor(72, "Dark Bluish Gray", "#6C6E6C", (108, 110, 108)),
    LegoColor(73, "Medium Blue", "#5A91C3", (90, 145, 195)),
    LegoColor(74, "Medium Green", "#73DCA1", (115, 220, 161)),
    LegoColor(77, "Light Pink", "#FECCCF", (254, 204, 207)),
    LegoColor(78, "Light Flesh", "#F6D7B3", (246, 215, 179)),
    LegoColor(84, "Medium Dark Flesh", "#CC702A", (204, 112, 42)),
    LegoColor(85, "Dark Tan", "#958A73", (149, 138, 115)),
    LegoColor(86, "Light Brown", "#7C5030", (124, 80, 48)),
    LegoColor(89, "Dark Blue", "#1B2A34", (27, 42, 52)),
]


class ColorService:
    """Map RGB colors to the nearest LEGO color."""

    @staticmethod
    def rgb_distance(
        a: tuple[int, int, int], b: tuple[int, int, int]
    ) -> float:
        """Weighted Euclidean distance in RGB space, tuned for LEGO color perception."""
        r_mean = (a[0] + b[0]) / 2
        dr = a[0] - b[0]
        dg = a[1] - b[1]
        db = a[2] - b[2]
        # Weighted by human perception (red-green is more important)
        return ((2 + r_mean / 256) * dr * dr +
                4 * dg * dg +
                (2 + (255 - r_mean) / 256) * db * db) ** 0.5

    @classmethod
    def nearest_lego_color(cls, rgb: tuple[int, int, int]) -> LegoColor:
        """Find the nearest LEGO color for a given RGB value."""
        best = None
        best_dist = float("inf")
        for lc in LEGO_COLORS:
            dist = cls.rgb_distance(rgb, lc.rgb)
            if dist < best_dist:
                best_dist = dist
                best = lc
        return best or LEGO_COLORS[0]

    @classmethod
    def quantize_colors(
        cls, pixels: list[tuple[int, int, int]], n_colors: int = 5
    ) -> list[tuple[LegoColor, float]]:
        """Extract dominant colors from image pixels, mapped to LEGO colors.

        Uses simple histogram bucketing (for production, use k-means clustering).
        Returns list of (LegoColor, proportion) sorted by proportion descending.
        """
        if not pixels:
            return [(LEGO_COLORS[0], 1.0)]

        from collections import Counter

        # Map each pixel to nearest LEGO color
        mapped = [cls.nearest_lego_color(p) for p in pixels]
        counts = Counter(c.id for c in mapped)
        total = sum(counts.values())

        results = []
        for color_id, count in counts.most_common(n_colors):
            lc = next((c for c in LEGO_COLORS if c.id == color_id), LEGO_COLORS[0])
            results.append((lc, count / total))

        return results
