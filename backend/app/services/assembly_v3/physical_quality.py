"""Check scale-specific source coverage and measurable native component sizes."""

from app.services.assembly_preview import geometry_bounds
from .requirements import OVERALL, scene_requirements


def physical_geometry_report(scene) -> dict:
    policy = scene_requirements(scene)
    profile = scene.specifications.get("physical_data", {})
    targets = profile.get("measurements", {})
    required = set(policy["required_measurements"])
    missing = sorted(n for n in required if not targets.get(n, {}).get("grounded"))
    checks, measured = [], {}
    wheels = [p for p in scene.parts if p.feature == "tyre"]
    placements = {p.id: placement for p, placement in zip(scene.parts, scene.placements())}
    if wheels:
        front_z = min(p.transform.position[2] for p in wheels)
        for axle, group in (("front", [p for p in wheels if abs(p.transform.position[2] - front_z) < 1]),
                            ("rear", [p for p in wheels if abs(p.transform.position[2] - front_z) >= 1])):
            bounds = geometry_bounds([placements[p.id] for p in group]) if group else []
            for suffix, dimension in (("tyre_diameter", "z"), ("tyre_width", "x")):
                # Check each tyre, since averaging can hide a mismatched pair.
                measured[f"{axle}_{suffix}"] = ([b[dimension][1] - b[dimension][0] for b in bounds],
                    [p.module for p in group], policy["component_tolerances_percent"][suffix])
            if len(group) >= 2:
                track = max(p.transform.position[0] for p in group) - min(p.transform.position[0] for p in group)
                measured[f"{axle}_track"] = ([track], [p.module for p in group], policy["dimension_tolerances_percent"]["width"])
    for name in sorted((required | set(targets)) - set(OVERALL)):
        target = targets.get(name, {})
        check = {"name": name, "required": name in required, "status": "unverified", "modules": [],
                 "reason": "No grounded source measurement"}
        if target.get("conflicted"):
            check.update(status="failed", reason="Conflicting source measurements")
        elif target.get("grounded") and name in measured and measured[name][0]:
            actual, modules, tolerance = measured[name]
            deviations = [abs(value / target["target_ldu"] - 1) * 100 for value in actual]
            check.update(status="passed" if max(deviations) <= tolerance else "failed", actual_ldu=actual,
                target_ldu=target["target_ldu"], deviation_percent=round(max(deviations), 3),
                tolerance_percent=tolerance, modules=modules, source_url=target.get("source_url"), reason=None)
        elif target.get("grounded"):
            check.update(reason="Requires a dedicated measured component surface or validated mechanism recipe; combined bounding boxes cannot establish this dimension",
                modules=["doors" if name.startswith("door") else "engine" if name.startswith("engine") else "cockpit"])
        checks.append(check)
    required_checks = [c for c in checks if c["required"]]
    conflicts = [c for c in profile.get("conflicts", []) if c["name"] in required]
    status = "failed" if conflicts or any(c["status"] == "failed" for c in required_checks) else (
        "unverified" if missing or any(c["status"] != "passed" for c in required_checks) else "passed")
    return {"status": status, "requirements_version": policy["version"], "checks": checks,
        "missing_required": missing, "missing": profile.get("missing", []), "conflicts": profile.get("conflicts", []),
        "optional_findings": [c for c in checks if not c["required"] and c["status"] != "passed"]}
