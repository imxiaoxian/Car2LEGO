import copy

import numpy as np
import pytest
import trimesh

from car2lego3d.carfit import design, fit_mesh
from car2lego3d.common import ROOT
from car2lego3d.requirements import plan_design
from car2lego3d.vehicle import load_spec


def countach():
    spec = copy.deepcopy(load_spec(ROOT / "data/vehicles/ferrari_f40_1987.json"))
    spec.update(model="Lamborghini Countach", variant="1988 QV")
    spec["sources"]["test"] = dict(title="Constructed dimensions for layout regression", file=__file__)
    for name, value in dict(length=4140, width=2000, height=1070, wheelbase=2450,
                             front_overhang=1000, rear_overhang=690).items():
        spec["measurements"][name].update(value=value, status="estimated", source="test")
    return spec


def fitted():
    mesh = trimesh.creation.box((4.14, 2, 1.07))
    return fit_mesh(mesh, specifications=countach(), scale="1:24", color=15)


def test_short_vehicle_keeps_requested_scale_without_changing_other_recipes():
    spec = countach()
    plan = plan_design(spec, "1:24")
    assert plan["grid"]["length_studs"] == 22
    assert plan["target_scale_denominator"] == 24
    assert plan["generation"]["draft_recipe_available"]
    spec["model"] = "Unknown compact car"
    assert not plan_design(spec, "1:24")["generation"]["draft_recipe_available"]


def test_each_window_belongs_to_its_door_and_seats_directly_on_its_studs():
    car = design(fitted())
    doors = [p for p in car.parts if p.part == "14718"]
    windows = [p for p in car.parts if p.part == "15207"]
    assert len(doors) == len(windows) == 2
    for door in doors:
        window, = [p for p in windows if p.module == door.module]
        rotation = np.asarray(door.rotation).reshape(3, 3)
        np.testing.assert_allclose(rotation, np.asarray(window.rotation).reshape(3, 3))
        for x in (-30, -10, 10, 30):
            stud_seat = np.asarray(door.position) + rotation @ np.array([x, 0, 0])
            socket_seat = np.asarray(window.position) + rotation @ np.array([x, 24, 0])
            np.testing.assert_allclose(stud_seat, socket_seat)


def test_wedge_uses_broad_surfaces_and_preserves_symmetric_native_parts():
    car = design(fitted(), rear_wing=False)
    assert sum(p.module == "red seats" for p in car.parts) == 2
    assert sum(p.module == "modular wedge bonnet" for p in car.parts) <= 8
    assert not any("wing" in p.module and "mirror" not in p.module for p in car.parts)
    for part in car.parts:
        rotation = np.asarray(part.rotation).reshape(3, 3)
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3))
        assert np.linalg.det(rotation) == pytest.approx(1)


def test_lens_sockets_meet_the_side_stud_plane_of_each_lamp_housing():
    car = design(fitted())
    for prefix, stud_offset in (("front", -10), ("rear", 10)):
        mounts = [p for p in car.parts if p.module == prefix+" lamp housings"]
        lenses = [p for p in car.parts if p.module == (
            "paired front lamp lenses" if prefix == "front" else "segmented tail lamp lenses")]
        assert len(mounts) == len(lenses) == 4
        for mount in mounts:
            lens, = [p for p in lenses if p.position[2] == mount.position[2]]
            seat = np.asarray(mount.position)+np.array([stud_offset,10,0])
            socket = np.asarray(lens.position)+np.asarray(lens.rotation).reshape(3,3)@np.array([0,8,0])
            np.testing.assert_allclose(seat,socket,atol=1e-8)
