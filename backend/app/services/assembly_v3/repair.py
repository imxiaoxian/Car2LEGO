"""Choose local connector-generated module moves without degrading the best draft."""

import numpy as np
from ortools.sat.python import cp_model
from scipy.spatial import cKDTree

from .connections import attachment_candidates, infer_connections
from .validation import collisions


def score(scene) -> int:
    edges, connectivity = infer_connections(scene)
    scene.connections = edges
    return len(connectivity["disconnected_parts"]) * 10 + len(collisions(scene, 1000)) * 20 + len(connectivity["unknown_connections"]) * 100


def repair_module(scene, module: str):
    affected = scene.dependency_closure(module)
    anchors = [p for p in scene.parts if p.module not in affected]
    children = [p for p in scene.parts if p.module == module]
    if not anchors or not children:
        return scene, {"module": module, "status": "no_candidates"}
    tree = cKDTree(np.array([p.transform.position for p in anchors]))
    offsets = {(0., 0., 0.)}
    for child in children[:12]:
        _, indices = tree.query(child.transform.position, k=min(4, len(anchors)))
        for index in np.atleast_1d(indices):
            try:
                candidates = attachment_candidates(anchors[int(index)], child.part_num, child.transform.rotation)
            except ValueError:
                continue
            for origin in candidates:
                offset = np.array(origin) - child.transform.position
                if np.linalg.norm(offset) <= 20:
                    offsets.add(tuple(np.round(offset, 5)))
    alternatives = []
    for offset in sorted(offsets, key=lambda x: np.linalg.norm(x))[:8]:
        candidate = scene.model_copy(deep=True)
        for part in candidate.parts:
            if part.module in affected:
                part.transform.position = tuple(np.array(part.transform.position) + offset)
        for joint in candidate.joints:
            if joint.parent in affected and joint.child in affected:
                joint.pivot = tuple(np.array(joint.pivot) + offset)
        alternatives.append((score(candidate), offset, candidate))
    model = cp_model.CpModel()
    options = [model.NewBoolVar(f"candidate_{i}") for i in range(len(alternatives))]
    model.AddExactlyOne(options)
    model.Minimize(sum(option * (cost * 1000 + round(np.linalg.norm(offset) * 10))
                       for option, (cost, offset, _) in zip(options, alternatives)))
    solver = cp_model.CpSolver(); solver.parameters.max_time_in_seconds = 5; solver.parameters.num_search_workers = 1
    if solver.Solve(model) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return scene, {"module": module, "status": "infeasible"}
    cost, offset, chosen = alternatives[next(i for i, option in enumerate(options) if solver.Value(option))]
    return chosen, {"module": module, "status": "improved" if offset != (0., 0., 0.) else "best_preserved",
                    "affected_modules": sorted(affected), "offset_ldu": offset, "constraint_score": cost, "candidates": len(alternatives)}
