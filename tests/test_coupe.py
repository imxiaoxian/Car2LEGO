import copy

import numpy as np
import pytest
import trimesh

from car2lego3d.carfit import design, fit_mesh, convert_car
from car2lego3d.common import ROOT
from car2lego3d.coupe import fit_coupe, styling
from car2lego3d.image import compose_prompt
from car2lego3d.studio import export_studio, verify_archive
from car2lego3d.vehicle import load_spec


def specification():
    spec = copy.deepcopy(load_spec(ROOT / "data/vehicles/ferrari_f40_1987.json"))
    spec.update(model="BMW M4 G82 Coupe", variant="G82 480 hp coupe")
    values = {"length": 4794, "width": 1887, "height": 1393, "wheelbase": 2857,
              "front_track": 1617, "rear_track": 1605, "front_tyre_width": 275,
              "rear_tyre_width": 285, "front_tyre_aspect": 40, "rear_tyre_aspect": 35,
              "front_rim_diameter": 18, "rear_rim_diameter": 19}
    for key, value in values.items():
        spec["measurements"][key]["value"] = value
    return spec


def vehicle(roof_length=4):
    body = trimesh.creation.box((16, 6, 2))
    roof = trimesh.creation.box((roof_length, 4, 2))
    roof.apply_translation((2, 0, 2))
    return trimesh.util.concatenate((body, roof))


def test_coupe_roof_length_and_height_follow_geometry_and_specs():
    short = fit_mesh(vehicle(), specifications=specification(), scale="1:24")
    long = fit_mesh(vehicle(7), specifications=specification(), scale="1:24")
    span = lambda fit: fit["roof_end_stud"] - fit["roof_start_stud"]
    assert short["recipe"] == "coupe-v1" and span(long) > span(short)
    assert short["layout"]["engine_position"] == "front"
    taller_spec = specification()
    taller_spec["measurements"]["height"]["value"] = 1520
    taller = fit_mesh(vehicle(), specifications=taller_spec, scale="1:24")
    assert taller["roof_top_plates"] > short["roof_top_plates"]
    assert abs(short["physical_constraints"]["dimensions"]["height"]["error_percent"]) < 2


def test_wheel_selection_and_dimension_report_use_selected_native_parts():
    fit = fit_mesh(vehicle(), specifications=specification(), scale="1:24")
    assert {wheel["tyre"] for wheel in fit["wheel_families"]} == {"58090"}
    assert fit["physical_constraints"]["dimensions"]["front_tyre_diameter"]["fitted_mm"] == 30.4
    small_spec = specification()
    small_spec["measurements"]["front_rim_diameter"]["value"] = 14
    small_spec["measurements"]["front_tyre_width"]["value"] = 200
    small = fit_mesh(vehicle(), specifications=small_spec, scale="1:24")
    assert small["wheel_families"][0]["diameter_mm"] < fit["wheel_families"][0]["diameter_mm"]


def test_model_styling_is_scoped_to_resolved_generation():
    spec = specification()
    assert styling(spec) == "bmw-m4-g82"
    assert "vertical twin kidney" in compose_prompt("a blue BMW M4", spec)
    spec.update(model="BMW M4 F82", variant="F82")
    assert styling(spec) is None
    assert "vertical twin kidney" not in compose_prompt("a blue BMW M4", spec)
    assert styling(None) is None


@pytest.mark.parametrize("width", [8, 10, 12])
def test_coupe_does_not_include_mid_engine_sports_car_features_and_has_native_connections(width):
    car = design(fit_mesh(vehicle(), specifications=specification(), scale="1:24", width=width))
    modules = {p.module for p in car.parts}
    assert {"front windscreen", "rear windscreen", "coupe roof", "G82 vertical kidney grilles"} <= modules
    assert not {"engine cover", "recessed side intake", "rear wing"} & modules
    for part in car.parts:
        rotation = np.array(part.rotation).reshape(3, 3)
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3))
        assert np.linalg.det(rotation) == pytest.approx(1)
    for skin in [p for p in car.parts if p.module == "door skin"]:
        for x in (-30, 30):
            socket = np.array(skin.position) + np.array(skin.rotation).reshape(3, 3) @ (x, 8, 0)
            assert any(np.allclose(socket, np.array(m.position) + np.array(m.rotation).reshape(3, 3) @ (0, 10, -10))
                       for m in car.parts if m.module == "door mounts")
    for grille in [p for p in car.parts if p.module == "G82 vertical kidney grilles"]:
        for z in (-10, 10):
            socket = np.array(grille.position) + np.array(grille.rotation).reshape(3, 3) @ (10, 8, z)
            assert any(np.allclose(socket, np.array(m.position) + np.array(m.rotation).reshape(3, 3) @ (0, 10, -10))
                       for m in car.parts if m.module == "front fascia mounts")


def test_coupe_archive_roundtrip_preserves_parts_and_transforms(tmp_path):
    import json
    mesh = tmp_path / "car.glb"
    spec = tmp_path / "spec.json"
    vehicle().export(mesh)
    spec.write_text(json.dumps(specification()), encoding="utf-8")
    ldraw = convert_car(mesh, tmp_path / "lego", vehicle_spec=spec, scale="1:24")
    io = export_studio(ldraw, tmp_path / "studio")
    result = verify_archive(io, ldraw)
    assert result["part_count"] > 150
    fit = json.loads((ldraw.parent / "fit.json").read_text())
    assert fit["recipe"] == "coupe-v1"


def test_roof_fit_ignores_disjoint_high_artifact():
    fit = {"length_studs": 25, "width_studs": 10, "target_scale_denominator": 24,
           "height_profile_studs": [4]*10 + [7]*5 + [4]*8 + [6.97, 4], "limitations": []}
    result = fit_coupe(fit, specification())
    assert result["roof_end_stud"] < 20
