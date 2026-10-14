"""Offline policy cases. Constructed reports do not establish build acceptance."""

from types import SimpleNamespace

import pytest

from app.services.assembly_v3.requirements import requirements_for_scale, scene_requirements, mechanism_checks, SCALES
from app.services.assembly_v3.delivery import delivery_requirements
from app.services.reference_images import reference_plan, reference_fingerprint
from app.services.vehicle_physics import VehiclePhysicalProfile, FIELDS


def test_every_scale_has_an_independent_progressive_contract():
    policies = [requirements_for_scale(s) for s in SCALES]
    assert [len(p["reference_views"]) for p in policies] == [6, 14, 18, 20]
    assert [len(p["visual_requirements"]) for p in policies] == [6, 9, 10, 13]
    assert [p["max_step_parts"] for p in policies] == [12, 12, 10, 8]
    for previous, current in zip(policies, policies[1:]):
        assert set(previous["required_measurements"]) < set(current["required_measurements"])
        assert {m["id"] for m in previous["mechanisms"]} < {m["id"] for m in current["mechanisms"]}
    assert set(policies[-1]["required_measurements"]) == set(FIELDS)
    assert all(p["dimension_tolerances_percent"] == {"length": 3, "wheelbase": 3, "width": 5, "height": 5} for p in policies[1:])
    with pytest.raises(ValueError):
        requirements_for_scale("1:8")
    policies[0]["mechanisms"].clear()
    assert requirements_for_scale("1:38")["mechanisms"]


def test_small_scale_omits_opening_details_but_explicit_requests_still_work():
    state = dict(workflow_version="assembly_v3", scale="1:38")
    assert "doors" not in reference_plan(state)
    assert "doors" in reference_plan(state | {"requested_reference_shots": [dict(view="doors", focus="Door style")]})
    large = reference_plan(state | {"scale": "1:12"})
    assert {"door_hinges", "hood_hinges", "dashboard", "steering", "suspension", "underbody"} <= set(large)
    assert reference_fingerprint(state) == reference_fingerprint(state | {"scale": "1:12"})  # reuse paid exterior sheets


def test_all_required_instances_must_pass_and_duplicate_children_cannot_cover_wheels():
    policy = requirements_for_scale("1:38")
    reports = [dict(id=f"spin{i}", child=f"wheel{i}", capability="rolling_wheels", status="passed") for i in range(4)]
    assert mechanism_checks(policy, reports)[0]["status"] == "passed"
    assert mechanism_checks(policy, reports[:1])[0]["status"] == "failed"
    reports[-1]["status"] = "failed"
    assert mechanism_checks(policy, reports)[0]["status"] == "failed"
    reports[-1].update(status="passed", child="wheel0")
    assert mechanism_checks(policy, reports)[0]["status"] == "failed"
    checks = mechanism_checks(requirements_for_scale("1:12"), [])
    assert next(c for c in checks if c["id"] == "independent_suspension")["minimum_instances"] == 4


def test_delivery_uses_policy_and_cannot_upgrade_a_recipe_to_verified():
    scene = SimpleNamespace(vehicle=dict(make="Ferrari", model="F40"), scale="1:38", planning={}, parts=[])
    compact = delivery_requirements(scene, [])
    assert "engine" not in {c["id"] for c in compact["checks"]}
    assert not compact["vehicle_recipe_verified"]
    scene.scale = "1:12"
    assert {"engine_detail", "underbody", "suspension_detail", "doors"} <= {c["id"] for c in delivery_requirements(scene, [])["checks"]}


def test_scene_policy_snapshot_is_reused_and_rejects_the_wrong_ratio():
    snapshot = requirements_for_scale("1:16")
    snapshot["max_step_parts"] = 9
    scene = SimpleNamespace(scale="1:16", planning={"scale_requirements": snapshot})
    assert scene_requirements(scene)["max_step_parts"] == 9
    scene.scale = "1:24"
    with pytest.raises(ValueError, match="incompatible"):
        scene_requirements(scene)


def test_missing_physical_data_is_classified_per_scale():
    profile = VehiclePhysicalProfile(make="Ferrari", model="F40", year=1990)
    compact, large = profile.resolved("1:38"), profile.resolved("1:12")
    assert "door_opening_angle" not in compact["missing_required"]
    assert "door_opening_angle" in large["missing_required"]
    assert "engine_length" in large["missing_required"]
    assert compact["missing"] == large["missing"]  # retain legacy field


def test_optional_conflict_does_not_fail_compact_required_geometry(monkeypatch):
    from app.services.assembly_v3 import physical_quality as quality
    policy = requirements_for_scale("1:38")
    measurements = {n: dict(grounded=True, target_ldu=60) for n in policy["required_measurements"]}
    measurements["door_length"] = dict(grounded=False, conflicted=True)
    wheels = [SimpleNamespace(id=f"wheel{i}", module=f"wheel{i}", feature="tyre",
        transform=SimpleNamespace(position=(x, 0, z))) for i, (x, z) in enumerate([(-30, 0), (30, 0), (-30, 100), (30, 100)])]
    scene = SimpleNamespace(scale="1:38", planning={}, parts=wheels, placements=lambda: [{}] * 4,
        specifications={"physical_data": {"measurements": measurements, "conflicts": [{"name": "door_length"}]}})
    monkeypatch.setattr(quality, "geometry_bounds", lambda group: [{"x": [0, 30], "z": [0, 60]} for _ in group])
    report = quality.physical_geometry_report(scene)
    assert report["status"] == "passed" and not report["missing_required"]
    assert report["optional_findings"]
    scene.scale = "1:16"
    assert quality.physical_geometry_report(scene)["status"] == "failed"


def test_tyre_check_detects_individual_errors_hidden_by_an_average(monkeypatch):
    from app.services.assembly_v3 import physical_quality as quality
    wheels = [SimpleNamespace(id=str(i), module=str(i), feature="tyre", transform=SimpleNamespace(position=(i*60, 0, 0))) for i in range(2)]
    scene = SimpleNamespace(scale="1:24", planning={}, parts=wheels, placements=lambda: [{}, {}],
        specifications={"physical_data": {"measurements": {"front_tyre_diameter": dict(grounded=True, target_ldu=60)}}})
    monkeypatch.setattr(quality, "geometry_bounds", lambda _: [{"x": [0, 30], "z": [0, 50]}, {"x": [0, 30], "z": [0, 70]}])
    report = quality.physical_geometry_report(scene)
    check = next(c for c in report["checks"] if c["name"] == "front_tyre_diameter")
    assert check["status"] == "failed" and check["actual_ldu"] == [50, 70]


async def test_pause_resume_preserves_policy_without_model_calls(tmp_path, monkeypatch):
    from app.services.assembly_v3 import pipeline
    from app.services.assembly_v3.jobs import JobStopped
    runner = pipeline.AssemblyPipeline(tmp_path)
    saved = requirements_for_scale("1:16")
    monkeypatch.setattr(pipeline, "requirements_for_scale", lambda _: saved)
    monkeypatch.setattr(pipeline, "load_profile", lambda *args: VehiclePhysicalProfile(make="Ferrari", model="F40", year=1990, sources=[{"status": "unavailable"}]))
    seen = []
    async def stop(self, state):
        seen.append(state["scale_requirements"]["max_step_parts"])
        runner.jobs.control("fixture", "pause")
        state["checkpoint_progress"]("references", 4)
        raise JobStopped("paused")
    monkeypatch.setattr(pipeline.ReferenceImageService, "generate", stop)
    await runner.generate("fixture", "Ferrari", "F40", 1990, "1:16")
    assert runner.jobs.get("fixture")["state"] == "paused"
    runner.jobs.control("fixture", "resume")
    saved["max_step_parts"] = 99
    await runner.generate("fixture", "Ferrari", "F40", 1990, "1:16")
    assert seen == [10, 10]
    assert runner.jobs.get("fixture")["data"]["calls"] == {"text": 0, "image": 0}
