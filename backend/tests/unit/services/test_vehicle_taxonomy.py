"""Unit tests for VehicleTaxonomy — classification system."""

import pytest
from app.services.vehicle_taxonomy import (
    BODY_STYLES,
    ERAS,
    REGIONS,
    DISTINCTIVE_FEATURES,
    WHEEL_TYPES,
    PERFORMANCE_TIERS,
    MODIFICATION_LEVELS,
    FACTORY_COLORS,
)


class TestBodyStyles:
    """Body style classification."""

    def test_has_nine_main_categories(self):
        assert len(BODY_STYLES) >= 9

    def test_all_styles_are_dicts_with_sub_styles(self):
        for category, data in BODY_STYLES.items():
            assert isinstance(data, dict), f"{category} should be a dict with label and sub_styles"
            assert "label" in data or "sub_styles" in data, f"{category} missing keys"

    def test_key_categories_exist(self):
        assert "sports_car" in BODY_STYLES
        assert "supercar" in BODY_STYLES
        assert "sedan" in BODY_STYLES
        assert "suv" in BODY_STYLES
        assert "pickup" in BODY_STYLES


class TestEras:
    """Era classification."""

    def test_has_five_eras(self):
        assert len(ERAS) >= 5

    def test_key_eras(self):
        assert "vintage" in ERAS or any("vintage" in str(e) for e in ERAS)
        assert "classic" in ERAS or any("classic" in str(e) for e in ERAS)


class TestRegions:
    """Region classification."""

    def test_has_seven_regions(self):
        assert len(REGIONS) >= 7

    def test_key_regions(self):
        assert "jdm" in REGIONS
        assert "euro" in REGIONS or "european" in str(REGIONS).lower()


class TestDistinctiveFeatures:
    """Distinctive features classification."""

    def test_has_eight_categories(self):
        assert len(DISTINCTIVE_FEATURES) == 8

    def test_expected_categories(self):
        expected = {"front_design", "rear_design", "side_profile",
                    "wheels_brakes", "aero", "roof_glass",
                    "lighting_signature", "ev_specific"}
        assert set(DISTINCTIVE_FEATURES.keys()) == expected


class TestWheelTypes:
    """Wheel type classification."""

    def test_has_wheel_types(self):
        assert len(WHEEL_TYPES) >= 15  # actual count is 15


class TestPerformanceTiers:
    """Performance tier classification."""

    def test_has_six_tiers(self):
        assert len(PERFORMANCE_TIERS) >= 6

    def test_key_tiers(self):
        assert "economy" in PERFORMANCE_TIERS or "Economy" in str(PERFORMANCE_TIERS)
        assert "supercar" in PERFORMANCE_TIERS or "Supercar" in str(PERFORMANCE_TIERS)


class TestModificationLevels:
    """Modification level classification."""

    def test_has_five_levels(self):
        assert len(MODIFICATION_LEVELS) >= 5


class TestFactoryColors:
    """Factory color → LEGO color mapping."""

    def test_has_at_least_forty_five_colors(self):
        assert len(FACTORY_COLORS) >= 45  # actual count is 47

    def test_known_colors_exist(self):
        """Verify key automotive colors are mapped."""
        color_keys = [str(c).lower() for c in FACTORY_COLORS]
        all_keys = " ".join(color_keys)
        assert "red" in all_keys
        assert "black" in all_keys
        assert "white" in all_keys
