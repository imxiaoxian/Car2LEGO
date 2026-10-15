import copy

import numpy as np
import pytest
import trimesh

from car2lego3d.carfit import design, fit_mesh
from car2lego3d.common import ROOT
from car2lego3d.image import compose_prompt
from car2lego3d.suv import styling
from car2lego3d.vehicle import load_spec


def specification():
    # Synthetic, sourced-shape fixture for the SUV routing and quantization contract.
    spec = copy.deepcopy(load_spec(ROOT / "data/vehicles/ferrari_f40_1987.json"))
    spec.update(model="Lotus For Me", variant="standard 21-inch wheels")
    values = {"length": 5103, "width": 2019, "height": 1636, "wheelbase": 3019,
              "front_track": 1738, "rear_track": 1744,
              "front_tyre_width": 265, "rear_tyre_width": 285,
              "front_tyre_aspect": 45, "rear_tyre_aspect": 45,
              "front_rim_diameter": 21, "rear_rim_diameter": 21}
    for field, value in values.items():
        spec["measurements"][field]["value"] = value
    return spec


def mesh():
    body = trimesh.creation.box((16, 6, 2))
    roof = trimesh.creation.box((7, 5, 2))
    roof.apply_translation((2, 0, 2))
    return trimesh.util.concatenate((body, roof))


@pytest.mark.parametrize("width", [8, 10, 12])
def test_for_me_uses_four_door_cabin_with_rigid_native_parts(width):
    fit = fit_mesh(mesh(), specifications=specification(), scale="1:24", width=width)
    assert fit["recipe"] == "suv-v1"
    assert fit["roof_end_stud"]-fit["roof_start_stud"] >= 8
    assert abs(fit["physical_constraints"]["dimensions"]["height"]["error_percent"]) < 5
    assert fit["cabin_width_studs"] == (6 if width == 8 else 8)
    car = design(fit)
    assert sum(p.module == "door skin" for p in car.parts) == 4
    lights = [p for p in car.parts if p.module == "continuous SUV tail lights"]
    assert len(lights) == (width-2)//2
    # Leave one stud of body at either end of the continuous light strip.
    z = sorted(p.position[2] for p in lights)
    assert np.diff(z).tolist() == [40] * (len(lights)-1)
    assert not {"G82 vertical kidney grilles", "engine cover", "rear wing"} & {p.module for p in car.parts}
    for p in car.parts:
        matrix = np.array(p.rotation).reshape(3, 3)
        np.testing.assert_allclose(matrix.T @ matrix, np.eye(3))
        assert np.linalg.det(matrix) == pytest.approx(1)
    for skin in [p for p in car.parts if p.module == "door skin"]:
        for x in (-30, 30):
            sockets = [np.array(skin.position) + np.array(skin.rotation).reshape(3, 3) @ (x, 8, z)
                       for z in (-10, 10)]
            assert any(np.allclose(socket, np.array(m.position) + np.array(m.rotation).reshape(3, 3) @ (0, 10, -10))
                       for socket in sockets for m in car.parts if m.module == "door mounts")


def test_identity_proxy_retains_user_color_and_scope():
    text = compose_prompt("a white Lotus For Me SUV", specification())
    assert "white Lotus Eletre" in text and "Four doors" in text
    spec = specification()
    spec.update(model="Lotus Emira")
    assert styling(spec) is None
    assert "Eletre" not in compose_prompt("a Lotus Emira", spec)


def test_narrow_mesh_selects_narrow_glazing_without_stretching_parts():
    body = trimesh.creation.box((16, 6, 2))
    roof = trimesh.creation.box((7, 3.9, 2))
    roof.apply_translation((2, 0, 2))
    fit = fit_mesh(trimesh.util.concatenate((body, roof)), specifications=specification(), scale="1:24", width=10)
    assert .60 < fit["source_upper_body_width_ratio"] < .70
    assert fit["cabin_width_studs"] == 6
    assert fit["windscreen_part"] == "92583"
    assert fit["deck_top_plates"] == fit["roof_top_plates"]-8
    parts = design(fit).parts
    assert any(p.part == "87552" and p.color == 40 for p in parts)
    assert not any(p.part in ("60592", "60601") for p in parts)
