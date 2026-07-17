"""Unit tests for PricingService."""

import pytest
from app.services.pricing_service import PricingService


class TestEstimatePartPrice:
    """Individual part price estimation."""

    def test_direct_match_brick_2x4(self):
        price, confidence = PricingService.estimate_part_price("3001")
        assert price == 0.12
        assert confidence == "estimated"

    def test_direct_match_plate_1x1(self):
        price, confidence = PricingService.estimate_part_price("3024")
        assert price == 0.03

    def test_direct_match_wheel(self):
        price, confidence = PricingService.estimate_part_price("56904")
        assert price == 0.60

    def test_strips_dat_suffix(self):
        """Should strip .dat suffix before lookup."""
        price, confidence = PricingService.estimate_part_price("3001.dat")
        assert price == 0.12

    def test_strips_assembly_suffix(self):
        """Part with c00 suffix resolves via category fallback after stripping."""
        # "4624c00" strips to "4624" which matches wheel category
        price, confidence = PricingService.estimate_part_price("4624c00")
        assert price == 0.25  # direct match for 4624 (wheel small)

    def test_category_fallback_plate(self):
        """Unknown plate-like part → default plate price."""
        price, confidence = PricingService.estimate_part_price("3024a")
        assert price == 0.06  # default_plate

    def test_category_fallback_brick(self):
        """Unknown brick-like part → default brick price."""
        price, confidence = PricingService.estimate_part_price("3005a")
        assert price == 0.10  # default_brick

    def test_category_fallback_wheel(self):
        """Unknown wheel-like part → default wheel price."""
        price, confidence = PricingService.estimate_part_price("6014xyz")
        assert price == 0.50  # default_wheel

    def test_unknown_part_default(self):
        """Completely unknown part → default_special price."""
        price, confidence = PricingService.estimate_part_price("99999")
        assert price == 0.15
        assert confidence == "estimated"


class TestPricePartsList:
    """Full parts list pricing."""

    def test_simple_list(self):
        parts = [
            {"part_num": "3001", "bricklink_id": "3001", "color_name": "Red", "quantity": 4},
            {"part_num": "3024", "bricklink_id": "3024", "color_name": "White", "quantity": 10},
        ]
        result = PricingService.price_parts_list(parts)
        assert result["total_parts"] == 14
        assert result["total_cost_usd"] == round(0.12 * 4 + 0.03 * 10, 2)
        assert result["currency"] == "USD"
        assert result["confidence"] == "estimated"

    def test_sorted_by_cost_descending(self):
        parts = [
            {"part_num": "3024", "bricklink_id": "3024", "color_name": "W", "quantity": 1},
            {"part_num": "56904", "bricklink_id": "56904", "color_name": "B", "quantity": 1},
        ]
        result = PricingService.price_parts_list(parts)
        # Most expensive (56904 = 0.60) should be first
        assert result["parts"][0]["part_num"] == "56904"

    def test_empty_list(self):
        result = PricingService.price_parts_list([])
        assert result["total_parts"] == 0
        assert result["total_cost_usd"] == 0.0
        assert result["parts"] == []

    def test_missing_fields_default(self):
        """Missing part_num or quantity should not crash."""
        parts = [{"quantity": 1}, {"part_num": "3001"}]
        result = PricingService.price_parts_list(parts)  # Should not raise
        assert result["total_parts"] >= 0
