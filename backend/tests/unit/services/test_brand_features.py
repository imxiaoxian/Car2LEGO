"""Unit tests for brand_features — brand signature features library."""

import pytest

from app.services.brand_features import (
    BRAND_PROFILES,
    BrandFeature,
    BrandProfile,
    get_brand_features,
    get_brand_profile,
)


class TestGetBrandFeatures:
    def test_ferrari_f40_returns_9_features(self):
        features = get_brand_features("Ferrari", "F40")
        assert len(features) == 9
        ids = {f.feature_id for f in features}
        assert "rear_wing" in ids
        assert "pop_up_headlight" in ids
        assert "quad_taillight" in ids

    def test_ferrari_default_features(self):
        features = get_brand_features("Ferrari", "Testarossa")
        assert len(features) > 0
        ids = {f.feature_id for f in features}
        assert "rear_wing" in ids

    def test_porsche_911_returns_features(self):
        features = get_brand_features("Porsche", "911")
        assert len(features) > 0

    def test_unknown_car_returns_empty(self):
        features = get_brand_features("UnknownBrand", "XYZ")
        assert features == []

    def test_case_insensitive_make(self):
        features_lower = get_brand_features("ferrari", "f40")
        features_upper = get_brand_features("FERRARI", "F40")
        assert len(features_lower) == len(features_upper)
        assert len(features_lower) > 0


class TestGetBrandProfile:
    def test_ferrari_profile(self):
        profile = get_brand_profile("Ferrari")
        assert profile is not None
        assert profile.brand == "Ferrari"
        assert profile.default_body_color == 4  # Red
        assert profile.default_accent_color == 0  # Black

    def test_unknown_returns_none(self):
        profile = get_brand_profile("Unknown")
        assert profile is None

    def test_case_insensitive(self):
        profile = get_brand_profile("bmw")
        assert profile is not None
        assert profile.brand == "BMW"


class TestBrandProfilesRegistry:
    def test_has_13_brands(self):
        assert len(BRAND_PROFILES) == 13

    def test_all_entries_are_brand_profiles(self):
        for key, profile in BRAND_PROFILES.items():
            assert isinstance(profile, BrandProfile)
            assert profile.brand
            assert isinstance(profile.default_body_color, int)
            assert isinstance(profile.default_accent_color, int)

    def test_all_features_are_brand_features(self):
        for profile in BRAND_PROFILES.values():
            for model_key, features in profile.features.items():
                for f in features:
                    assert isinstance(f, BrandFeature)
                    assert f.feature_id
                    assert f.part_num
                    assert isinstance(f.color_id, int)
                    assert isinstance(f.x, (int, float))
                    assert isinstance(f.y, (int, float))
                    assert isinstance(f.z, (int, float))
                    assert len(f.rotation.split()) == 9
