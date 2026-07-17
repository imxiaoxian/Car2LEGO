"""Unit tests for ColorService — RGB→LEGO color mapping."""

import math
from app.services.color_service import ColorService, LegoColor, LEGO_COLORS


class TestRgbDistance:
    """Weighted RGB distance calculation."""

    def test_identical_colors_zero_distance(self):
        d = ColorService.rgb_distance((100, 100, 100), (100, 100, 100))
        assert d == 0.0

    def test_black_vs_white(self):
        d = ColorService.rgb_distance((0, 0, 0), (255, 255, 255))
        assert d > 400  # Should be very large

    def test_symmetry(self):
        d1 = ColorService.rgb_distance((10, 50, 200), (30, 70, 180))
        d2 = ColorService.rgb_distance((30, 70, 180), (10, 50, 200))
        assert math.isclose(d1, d2, rel_tol=1e-9)

    def test_red_vs_green_is_larger_than_red_vs_dark_red(self):
        """Red-green perception difference should be more significant."""
        d_rg = ColorService.rgb_distance((255, 0, 0), (0, 255, 0))
        d_rdr = ColorService.rgb_distance((255, 0, 0), (128, 0, 0))
        assert d_rg > d_rdr


class TestNearestLegoColor:
    """Nearest LEGO color lookup."""

    def test_white_maps_to_white(self):
        result = ColorService.nearest_lego_color((255, 255, 255))
        assert result.name == "White"
        assert result.id == 15

    def test_black_maps_to_black(self):
        result = ColorService.nearest_lego_color((0, 0, 0))
        assert result.name == "Black"
        assert result.id == 0

    def test_pure_red_maps_to_red(self):
        result = ColorService.nearest_lego_color((255, 0, 0))
        assert result.id == 4  # Red

    def test_returns_a_color_for_any_input(self):
        """Should never return None."""
        for rgb in [(128, 128, 128), (1, 2, 3), (254, 253, 252), (0, 0, 1)]:
            result = ColorService.nearest_lego_color(rgb)  # type: ignore[arg-type]
            assert result is not None
            assert isinstance(result, LegoColor)


class TestQuantizeColors:
    """Dominant color extraction."""

    def test_single_color_dominates(self):
        pixels = [(255, 255, 255)] * 100 + [(0, 0, 0)] * 10
        results = ColorService.quantize_colors(pixels, n_colors=2)
        assert len(results) <= 2
        assert results[0][1] > results[1][1]  # White > Black proportion
        assert results[0][0].name == "White"

    def test_empty_pixels_returns_default(self):
        results = ColorService.quantize_colors([], n_colors=5)
        assert len(results) == 1
        assert results[0][0].id == 0  # Black default
        assert results[0][1] == 1.0

    def test_n_colors_limits_output(self):
        pixels = [(i, i, i) for i in range(256)]
        results = ColorService.quantize_colors(pixels, n_colors=3)
        assert len(results) <= 3
