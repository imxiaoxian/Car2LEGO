"""Use Studio's native oriented collision boxes for placed LEGO pieces."""

from functools import lru_cache
from pathlib import Path

import numpy as np

from app.services.io_validator import STUDIO_LDRAW_PARTS


@lru_cache(maxsize=256)
def local_boxes(part_num: str) -> tuple:
    path = STUDIO_LDRAW_PARTS.parent / "collider" / (Path(part_num).stem + ".col")
    if not path.is_file():
        raise ValueError(f"Studio collision geometry unavailable: {part_num}")
    boxes = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split()
        if len(fields) >= 17 and fields[0] == "9":
            axes = np.array(fields[2:11], dtype=float).reshape(3, 3)
            center = np.array(fields[11:14], dtype=float)
            half = np.array(fields[14:17], dtype=float)
            boxes.append((center, axes, half))
    if not boxes:
        raise ValueError(f"No supported Studio collision boxes: {part_num}")
    return tuple(boxes)


def expanded_placements(parts: list[dict]) -> list[dict]:
    expanded = []
    for index, part in enumerate(parts):
        matrix = np.array(str(part.get("rotation", "1 0 0 0 1 0 0 0 1")).split(), dtype=float).reshape(3, 3)
        origin = np.array([part["x"], -part["y"], part["z"]], dtype=float)
        expanded.append({"part": part, "index": index, "origin": origin, "matrix": matrix})
        if part.get("mirror", True) and part["x"] > .1:
            reflection = np.diag([-1., 1., 1.])
            expanded.append({"part": part, "index": index,
                             "origin": reflection @ origin, "matrix": reflection @ matrix})
    return expanded


def _world_boxes(placement: dict) -> list:
    rotation, origin = placement["matrix"], placement["origin"]
    result = []
    for center, axes, half in local_boxes(placement["part"]["part_num"]):
        center, axes = origin + rotation @ center, rotation @ axes
        extent = np.abs(axes) @ half
        result.append((center, axes, half, center - extent, center + extent))
    return result


def _intersects(first: tuple, second: tuple, tolerance: float = .35) -> bool:
    c1, axes1, half1, low1, high1 = first
    c2, axes2, half2, low2, high2 = second
    if np.any(np.minimum(high1, high2) - np.maximum(low1, low2) <= tolerance):
        return False
    # Separating axis theorem: both boxes' face normals and nine edge cross-products.
    candidates = [*axes1.T, *axes2.T]
    candidates.extend(np.cross(a, b) for a in axes1.T for b in axes2.T)
    delta = c2 - c1
    for axis in candidates:
        length = np.linalg.norm(axis)
        if length < 1e-8:
            continue
        axis = axis / length
        radius = np.abs(axes1.T @ axis) @ half1 + np.abs(axes2.T @ axis) @ half2
        if abs(delta @ axis) >= radius - tolerance:
            return False
    return True


def collision_issues(parts: list[dict], limit: int = 20) -> list[str]:
    placements = expanded_placements(parts)
    geometry = [_world_boxes(p) for p in placements]
    envelopes = [(np.min([b[3] for b in boxes], axis=0), np.max([b[4] for b in boxes], axis=0))
                 for boxes in geometry]
    issues = []
    for i, (low, high) in enumerate(envelopes):
        for j in range(i):
            low2, high2 = envelopes[j]
            if np.any(np.minimum(high, high2) - np.maximum(low, low2) <= .35):
                continue
            if any(_intersects(a, b) for a in geometry[i] for b in geometry[j]):
                first, second = placements[j], placements[i]
                issues.append(f"Collision: part_{first['index']} {first['part']['part_num']} at "
                              f"{first['origin'].tolist()} with part_{second['index']} "
                              f"{second['part']['part_num']} at {second['origin'].tolist()}")
                if len(issues) >= limit:
                    return issues
    return issues
