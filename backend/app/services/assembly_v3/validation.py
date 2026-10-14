"""Hard digital gates and separately recorded human acceptance."""

from itertools import combinations
import numpy as np
from scipy.spatial import cKDTree
from scipy.spatial.transform import Rotation

from app.services.assembly_geometry import _intersects, local_boxes
from app.services.assembly_preview import geometry_bounds
from .catalog import part_validity
from .connections import infer_connections, world_ports
from .scene import AssemblyScene
from .requirements import scene_requirements, mechanism_checks


def collisions(scene: AssemblyScene, limit: int = 100, moving_ids: set[str] | None = None) -> list[dict]:
    envelopes, boxes, known = [], [], []
    for part in scene.parts:
        matrix, origin = np.array(part.transform.rotation).reshape(3, 3), np.array(part.transform.position)
        try:
            group = []
            for center, axes, half in local_boxes(part.part_num):
                center, axes = origin + matrix @ center, matrix @ axes
                extent = np.abs(axes) @ half
                group.append((center, axes, half, center - extent, center + extent))
            low, high = np.min([b[3] for b in group], axis=0), np.max([b[4] for b in group], axis=0)
            boxes.append(group); envelopes.append((low, high)); known.append(part)
        except ValueError:
            continue
    if not known:
        return []
    centres = np.array([(low + high) / 2 for low, high in envelopes])
    radii = np.array([np.linalg.norm(high - low) / 2 for low, high in envelopes])
    tree = cKDTree(centres)
    connections = {frozenset((c.a, c.b)) for c in scene.connections if c.kind == "fixed:fixed"}
    issues = []
    # During a rigid sweep only pairs involving the moving module can change.
    # Query its parts against the complete car; do not rescan static/static pairs.
    indices = range(len(known)) if moving_ids is None else [i for i,p in enumerate(known) if p.id in moving_ids]
    seen = set()
    for i in indices:
        for j in sorted(tree.query_ball_point(centres[i], radii[i] + radii.max())):
            if j == i or (moving_ids is None and j >= i):
                continue
            index_pair = tuple(sorted((i, j)))
            if index_pair in seen:
                continue
            seen.add(index_pair)
            # Tyre-rim overlap is intrinsic to a proven fixed connector pairing.
            pair = frozenset((known[i].id, known[j].id))
            if pair in connections and {known[i].feature, known[j].feature} == {"tyre", "rim"}:
                continue
            low, high = envelopes[i]; low2, high2 = envelopes[j]
            if np.any(np.minimum(high, high2) - np.maximum(low, low2) <= .35):
                continue
            if any(_intersects(a, b) for a in boxes[i] for b in boxes[j]):
                issues.append({"kind": "collision", "parts": [known[j].id, known[i].id],
                               "modules": sorted({known[j].module, known[i].module})})
                if len(issues) >= limit:
                    return issues
    return issues


def move_joint(scene: AssemblyScene, joint, value: float) -> AssemblyScene:
    copy = scene.model_copy(deep=True)
    affected = {joint.child}
    pivot, axis = np.array(joint.pivot), np.array(joint.axis)
    matrix = Rotation.from_rotvec(axis * np.deg2rad(value)).as_matrix() if joint.kind == "revolute" else np.eye(3)
    for part in copy.parts:
        if part.module not in affected:
            continue
        pos = np.array(part.transform.position)
        part.transform.position = tuple(pivot + matrix @ (pos - pivot)) if joint.kind == "revolute" else tuple(pos + axis * value)
        part.transform.rotation = tuple((matrix @ np.array(part.transform.rotation).reshape(3, 3)).ravel())
    return copy


def motion_report(scene: AssemblyScene, progress=None) -> list[dict]:
    policy = scene_requirements(scene)
    reports = []
    missing_colliders = []
    for number in sorted({p.part_num for p in scene.parts}):
        try:
            local_boxes(number)
        except ValueError:
            missing_colliders.append(number)
    for joint in scene.joints:
        if progress:
            progress("validation:motion:" + joint.capability, 65)
        report = {"id": joint.id, "child": joint.child, "capability": joint.capability, "limits": joint.limits, "status": "unverified", "samples": []}
        if not joint.implemented or not joint.mounting_parts:
            report["reason"] = "Mechanism has no validated mounting and linkage recipe"
        elif missing_colliders:
            report["reason"] = "Motion interference coverage is incomplete: " + ", ".join(missing_colliders)
        else:
            mounts=set(joint.mounting_parts)
            kind="axle:axle" if joint.capability=="rolling_wheels" else "hinge:hinge"
            connected = any({c.a, c.b} == mounts and c.kind==kind for c in scene.connections)
            world,_=world_ports(scene,mounts)
            movable=[p for p in world if p[0] in mounts and p[1].kind==("axle" if kind=="axle:axle" else "hinge")]
            axis=np.asarray(joint.axis);pivot=np.asarray(joint.pivot)
            aligned=any(np.linalg.norm(np.cross(p[2]-pivot,axis))<.25 and abs(p[3]@axis)>.9999 for p in movable)
            if kind=="axle:axle":
                aligned=aligned and any(p[1].semantic in ("pin_socket","round_hole") for p in movable)
            if not connected or not aligned:
                report["reason"] = "Mounting connection and free motion axis were not confirmed"
                report["status"] = "failed"
            else:
                moving_ids={p.id for p in scene.parts if p.module==joint.child}
                initial=collisions(scene,1000,moving_ids=moving_ids)
                baseline = {frozenset(i["parts"]) for i in initial}
                baseline_interference=[i for i in initial if moving_ids.intersection(i["parts"])]
                for value in np.linspace(*joint.limits, policy["motion_sample_count"]):
                    moved = move_joint(scene, joint, float(value))
                    mounting_connections,_=infer_connections(moved,part_ids=mounts)
                    retained=any({c.a,c.b}==mounts and c.kind==kind for c in mounting_connections)
                    interference = [i for i in collisions(moved,1000,moving_ids=moving_ids) if frozenset(i["parts"]) not in baseline]
                    report["samples"].append({"value": float(value), "interferences": interference,"mount_retained":retained})
                report["baseline_interferences"]=baseline_interference
                report["status"] = "failed" if baseline_interference or any(s["interferences"] or not s["mount_retained"] for s in report["samples"]) else "passed"
                report["method"] = f"SciPy rigid joint sweep, {policy['motion_sample_count']} positions; physical load behaviour not tested"
        reports.append(report)
    return reports


def validate_scene(scene: AssemblyScene, color_evidence: dict | None = None, progress=None) -> dict:
    from .delivery import delivery_requirements
    from .physical_quality import physical_geometry_report
    AssemblyScene.model_validate(scene.model_dump())
    policy = scene_requirements(scene)
    if progress:progress("validation:connections",60)
    validity = {number: part_validity(number) for number in sorted({p.part_num for p in scene.parts})}
    connections, connectivity = infer_connections(scene)
    scene.connections = connections
    if progress:progress("validation:collisions",62)
    collision = collisions(scene)
    missing_colliders = [number for number, result in validity.items() if not result.get("collider")]
    bounds = geometry_bounds(scene.placements())
    actual = {"length": max(b["z"][1] for b in bounds) - min(b["z"][0] for b in bounds),
              "width": max(b["x"][1] for b in bounds) - min(b["x"][0] for b in bounds),
              "height": max(b["height"][1] for b in bounds) - min(b["height"][0] for b in bounds)}
    wheels = [p for p in scene.parts if p.feature == "tyre"]
    actual["wheelbase"] = max(p.transform.position[2] for p in wheels) - min(p.transform.position[2] for p in wheels) if wheels else 0
    deviations = {key: round(abs(value / scene.target_ldu[key] - 1) * 100, 3) for key, value in actual.items()}
    mechanisms = motion_report(scene,progress)
    colors = color_evidence or {}
    unknown_colors = sorted({f"{p.part_num}:{p.color_id}" for p in scene.parts} - {k for k, v in colors.items() if v})
    gates = {
        "parts": "passed" if all(all(v.get(k) for k in ("geometry", "collider", "connections")) for v in validity.values()) else "failed",
        "transforms": "passed", "connections": connectivity["status"],
        "collisions": "failed" if collision else "unverified" if missing_colliders else "passed",
        "dimensions": "passed" if all(deviations[k] <= policy["dimension_tolerances_percent"][k] for k in deviations) and not scene.specifications.get("estimated", True) else "failed",
        "mechanisms": "passed" if all(c["status"] == "passed" for c in mechanism_checks(policy, mechanisms)) else "failed",
        "colors": "unverified" if unknown_colors else "passed",
        "appearance": "unverified", "insertion_paths": "unverified", "reference_consistency": "unverified",
        "assembly_steps": "passed" if all(len(step.parts) <= policy["max_step_parts"] for step in scene.steps) else "failed",
    }
    physical_geometry = physical_geometry_report(scene)
    gates["physical_geometry"] = physical_geometry["status"]
    issues = collision + [{"kind": "disconnected", "parts": [p], "modules": [next(i.module for i in scene.parts if i.id == p)]} for p in connectivity["disconnected_parts"]]
    if physical_geometry:
        issues.extend({"kind": "physical_dimension:" + check["name"], "parts": [], "modules": check["modules"]}
                      for check in physical_geometry["checks"] if check["status"] == "failed" and check["required"])
    return {"version": "assembly_v3", "scene_hash": scene.digest(), "digital_status": "passed" if all(v == "passed" for v in gates.values()) else "failed",
            "gates": gates, "part_validity": validity, "connectivity": connectivity, "collisions": collision,
            "collision_coverage": {"status": "complete" if not missing_colliders else "incomplete",
                                   "missing_part_numbers": missing_colliders},
            "collision_list_truncated": len(collision) >= 100, "actual_ldu": actual,
            "actual_mm": {k: round(v * .4, 2) for k, v in actual.items()}, "scale_deviation_percent": deviations,
            "mechanisms": mechanisms, "unknown_part_colors": unknown_colors, "issues": issues,
            "scale_requirements": policy, "requirements_applied": "scale_requirements" in scene.planning,
            "dimension_tolerances_percent": policy["dimension_tolerances_percent"],
            "studio": {"status": "unverified", "evidence": None}, "physical": {"status": "unverified", "evidence": None},
            "appearance": {"status": "unverified", "features": sorted({p.feature for p in scene.parts if p.feature})},
            "physical_specifications": scene.specifications.get("physical_data", {}), "physical_geometry": physical_geometry,
            "delivery_standard": delivery_requirements(scene, mechanisms), "precision_verified": False}
