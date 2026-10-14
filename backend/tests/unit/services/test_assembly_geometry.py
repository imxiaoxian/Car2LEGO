"""Regressions against real Studio collision geometry."""
import pytest

from app.services.assembly_geometry import collision_issues, expanded_placements
from app.services.constrained_assembly import build_assembly
from app.services.io_validator import STUDIO_LDRAW_PARTS

pytestmark = pytest.mark.skipif(
    not (STUDIO_LDRAW_PARTS.parent / "collider").exists(),
    reason="Studio native collision library required",
)


def plate(x=0, height=8, mirror=False):
    return dict(part_num="3020.dat", color_id=0, x=x, y=height, z=100, mirror=mirror)


def test_stacked_plates_connect_without_collision():
    assert collision_issues([plate(height=8), plate(height=16)]) == []


def test_distinct_origins_do_not_hide_solid_overlap():
    assert collision_issues([plate(), plate(x=20)])
    assert collision_issues([plate(x=20, mirror=True)])


@pytest.mark.parametrize("profile,wing", [("low_coupe", False), ("low_coupe", True), ("boxy", False), ("boxy", True)])
def test_assembly_has_four_wheels_and_no_collisions(profile, wing):
    sections = build_assembly(dict(assembly_profile=profile, rear_wing=wing))
    parts = [p for section in sections.values() for p in section]
    assert collision_issues(parts) == []
    tyres = [p for p in expanded_placements(sections["wheels"]) if p["part"]["part_num"] == "6015.dat"]
    assert {(p["origin"][0], p["origin"][2]) for p in tyres} == {(-74, 60), (74, 60), (-74, 260), (74, 260)}
