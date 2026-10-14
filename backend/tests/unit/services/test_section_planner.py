# backend/tests/unit/services/test_section_planner.py
"""Section planner tests — boundary computation for 5 body sections."""
import pytest

from app.services.section_planner import compute_section_bounds, SECTIONS_ORDER


def test_sections_order_is_fixed():
    assert SECTIONS_ORDER == ["chassis", "front", "body", "rear", "wheels"]


@pytest.mark.parametrize("body_style", [
    "sports_car", "suv", "sedan", "pickup", "hatchback", "f1_race",
])
def test_compute_section_bounds_returns_5_sections(body_style):
    bounds = compute_section_bounds(scale="1:38", body_style=body_style)
    assert len(bounds) == 5
    assert [b.section for b in bounds] == SECTIONS_ORDER


def test_chassis_z_range_covers_full_length():
    bounds = compute_section_bounds(scale="1:38", body_style="sports_car")
    chassis = next(b for b in bounds if b.section == "chassis")
    assert chassis.z_range == (0.0, 320.0)
    assert chassis.y_range == (0.0, 40.0)


def test_front_section_z_range():
    bounds = compute_section_bounds(scale="1:38", body_style="sports_car")
    front = next(b for b in bounds if b.section == "front")
    assert front.z_range == (200.0, 360.0)


def test_wheels_section_has_two_axle_z_positions():
    bounds = compute_section_bounds(scale="1:38", body_style="sedan")
    wheels = next(b for b in bounds if b.section == "wheels")
    # Wheel Z positions encoded in connection_points (front axle, rear axle)
    z_values = [cp[2] for cp in wheels.connection_points]
    assert 60.0 in z_values  # front axle
    assert 260.0 in z_values  # front axle


def test_unsupported_scale_raises():
    with pytest.raises(ValueError, match="unsupported scale"):
        compute_section_bounds(scale="1:12", body_style="sports_car")
