"""Constructed geometry diagnostics; no generated vehicle or physical acceptance implied."""
import copy

import pytest
from PIL import Image, ImageDraw

from car2lego3d.common import write_json
from car2lego3d.model_quality import assess_model, new_failures


@pytest.fixture
def scene(tmp_path):
    spec = {"model": "Constructed coupe", "measurements": {k: {"value": v} for k, v in dict(
        length=4000, width=1800, height=1200, wheelbase=2400, front_overhang=800,
        front_track=1500, rear_track=1500, front_tyre_width=200, rear_tyre_width=200,
        front_tyre_aspect=50, rear_tyre_aspect=50, front_rim_diameter=16, rear_rim_diameter=16).items()}}
    objects = [dict(name="body", role="body", bounds_m=[[0, -.9, .15], [4, .9, .8]]),
               dict(name="roof", role="roof", bounds_m=[[1.5, -.7, 1.1], [2.5, .7, 1.2]])]
    for axle, x in (("front", .8), ("rear", 3.2)):
        for side, y in (("left", -.75), ("right", .75)):
            objects.append(dict(name=f"tyre_{axle}_{side}", bounds_m=[
                [x-.3032, y-.1, 0], [x+.3032, y+.1, .6064]]))
    contacts = []
    for side in ("left", "right"):
        objects.append(dict(name=side+"_glass", role="side_window", bounds_m=[[1, 0, .8], [2, .1, 1.1]]))
        contacts.append(dict(door=side+"_door", window=side+"_glass", lower_edge_anchor_distances_m=[.003, .006]))
    metrics = dict(bounds_m=[[0, -.9, 0], [4, .9, 1.2]], objects=objects, triangles=5000,
                   door_window_contacts=contacts)
    for view in ("front", "back", "left", "right", "three-quarter", "rear-quarter"):
        image = Image.new("RGBA", (100, 70))
        ImageDraw.Draw(image).rectangle((10, 20, 90, 50), fill="white")
        image.save(tmp_path / f"render-{view}.png")
    return tmp_path, spec, metrics


def test_geometry_report_uses_tyre_spec_and_does_not_claim_appearance(scene):
    directory, spec, metrics = scene
    write_json(directory / "scene-metrics.json", metrics)
    result = assess_model(directory, spec)
    assert result["status"] == "pass"
    assert result["appearance_accepted"] is False


@pytest.mark.parametrize("problem", ["wrong_axle", "wrong_tyre_axis", "detached_window", "missing_door",
                                     "blank_render", "floating_assembly", "hidden_glass", "inward_body"])
def test_real_diagnostic_failures_are_reported(scene, problem):
    directory, spec, metrics = scene
    metrics = copy.deepcopy(metrics)
    if problem == "wrong_axle":
        for p in metrics["objects"][2]["bounds_m"]:
            p[0] += .2
    if problem == "wrong_tyre_axis":
        bounds = metrics["objects"][2]["bounds_m"]
        for p in bounds:
            p[1], p[2] = p[2], p[1]
    if problem == "detached_window":
        metrics["door_window_contacts"][0]["lower_edge_anchor_distances_m"] = [.003, .12]
    if problem == "missing_door":
        metrics["door_window_contacts"].pop()
    if problem == "blank_render":
        Image.new("RGBA", (100, 70)).save(directory / "render-front.png")
    if problem == "floating_assembly":
        for point in metrics["objects"][-1]["bounds_m"]:
            point[2] += .5
    if problem == "hidden_glass":
        metrics["glass_visibility"] = [dict(window="left_glass", visible_fraction=.2, first_hits=["body"])]
    if problem == "inward_body":
        metrics["objects"][0].update(boundary_edges=0, signed_volume_m3=-2)
    write_json(directory / "scene-metrics.json", metrics)
    result = assess_model(directory, spec)
    assert result["status"] == "needs_revision"
    assert result["failed_checks"] > 0


def test_body_loss_is_rejected_even_if_more_window_checks_are_fixed():
    before = dict(checks=[dict(name="floating_left", passed=False), dict(name="floating_right", passed=False),
                          dict(name="body_width", passed=True)])
    after = dict(checks=[dict(name="floating_left", passed=True), dict(name="floating_right", passed=True),
                         dict(name="body_width", passed=False)])
    assert new_failures(before, after) == ["body_width"]


@pytest.mark.parametrize("distances,length,targets,passed", [
    ([.002, .004, .003], .3, ["body"], True),
    ([.002, .065, .003], .3, ["body"], False),
    ([None, None, None], .3, [], False),
    ([.001], .0, ["body"], False),
])
def test_connection_checks_catch_midspan_gaps_and_missing_supports(scene, distances, length, targets, passed):
    directory, spec, metrics = scene
    metrics["surface_connections"] = [dict(source="buttress", seam="join_body", region="rear",
        targets=targets, distances_m=distances, sample_count=len(distances), sampled_length_m=length)]
    write_json(directory / "scene-metrics.json", metrics)
    report = assess_model(directory, spec)
    check = next(c for c in report["checks"] if c["name"] == "buttress.connection.join_body")
    assert check["passed"] is passed
    assert check["tolerance_m"] == .012


def test_refinement_cannot_silence_a_measured_connection_by_removing_the_seam():
    before = dict(checks=[dict(name="cowl.connection.join_body", passed=True)])
    assert new_failures(before, dict(checks=[])) == ["cowl.connection.join_body"]


def test_splitting_two_valid_seam_rails_does_not_count_as_removing_the_connection():
    before = dict(checks=[dict(name="cowl.connection.join_body", passed=True)])
    after = dict(checks=[dict(name="cowl.connection.join_body__a", passed=True),
                         dict(name="cowl.connection.join_body__b", passed=True)])
    assert new_failures(before, after) == []


def test_open_wheel_policy_uses_explicit_body_style_and_keeps_closed_f1_road_car_checked(scene):
    directory, spec, metrics = scene
    metrics["objects"] = [o for o in metrics["objects"] if o.get("role") not in {"roof", "side_window"}]
    metrics["door_window_contacts"] = []
    spec["model"] = "McLaren F1"
    write_json(directory / "scene-metrics.json", metrics)
    road = assess_model(directory, spec)
    assert {c["name"] for c in road["checks"] if not c["passed"]} == {"roof_role", "door_window_assemblies"}
    assert assess_model(directory, spec, body_style="f1_race")["status"] == "pass"
