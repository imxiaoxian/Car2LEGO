"""Semantic scene contract shared by reconstruction, fitting and diagnostics."""
import json
from pathlib import Path

import numpy as np


SCHEMA = "car2lego3d.semantic-scene.v1"


def validate_scene(scene):
    if scene.get("schema") != SCHEMA or scene.get("units") != "metres":
        raise ValueError("Unsupported semantic scene or units")
    nodes = scene.get("nodes", [])
    named = {n["id"]: n for n in nodes}
    if not named or len(named) != len(nodes):
        raise ValueError("Semantic nodes require unique identities")
    visited, active = set(), set()

    def visit(name):
        if name not in named:
            raise ValueError("Missing semantic parent: " + name)
        if name in active:
            raise ValueError("Cyclic semantic hierarchy")
        if name in visited:
            return
        active.add(name)
        node = named[name]
        local, world = [np.asarray(node[k], dtype=float) for k in ("local_transform", "world_transform")]
        if any(m.shape != (4, 4) or not np.isfinite(m).all() or not np.allclose(m[3], [0, 0, 0, 1]) for m in (local, world)):
            raise ValueError("Invalid semantic transform: " + name)
        if any(abs(np.linalg.det(m[:3, :3])) < 1e-12 for m in (local, world)):
            raise ValueError("Singular semantic transform: " + name)
        parent = node.get("parent")
        if parent:
            visit(parent)
        expected = np.asarray(named[parent]["world_transform"]) @ local if parent else local
        if not np.allclose(world, expected, atol=1e-6):
            raise ValueError("Inconsistent local/world transform: " + name)
        mesh = node.get("geometry")
        if mesh:
            vertices = np.asarray(mesh["vertices_m"], dtype=float)
            faces = np.asarray(mesh["triangles"], dtype=int)
            if (vertices.ndim != 2 or vertices.shape[1] != 3 or not np.isfinite(vertices).all()
                    or faces.ndim != 2 or faces.shape[1] != 3 or not len(faces)
                    or faces.min() < 0 or faces.max() >= len(vertices)):
                raise ValueError("Invalid semantic mesh: " + name)
            indices = mesh.get("material_indices", [])
            if len(indices) != len(faces) or any(type(i) is not int or i < 0 or i >= max(1, len(node.get("materials", []))) for i in indices):
                raise ValueError("Invalid semantic face materials: " + name)
        joint = node.get("joint")
        if joint:
            if joint.get("type") not in {"revolute", "prismatic"}:
                raise ValueError("Unsupported joint: " + name)
            axis = np.asarray(joint["axis"], dtype=float)
            origin = np.asarray(joint["origin_m"], dtype=float)
            limits = np.asarray(joint["limits"], dtype=float)
            if (axis.shape != (3,) or not np.isfinite(axis).all() or not np.isclose(np.linalg.norm(axis), 1)
                    or origin.shape != (3,) or not np.isfinite(origin).all()
                    or limits.shape != (2,) or not np.isfinite(limits).all() or limits[0] >= limits[1]):
                raise ValueError("Invalid joint axis, origin or limits: " + name)
            if joint.get("frame") != "parent":
                raise ValueError("Joint origin/axis must use the parent coordinate frame")
        port_ids = set()
        for port in node.get('ports', []):
            position, axis = (np.asarray(port.get(k), dtype=float) for k in ('position_m', 'axis'))
            if (not port.get('id') or port['id'] in port_ids or not port.get('kind')
                    or not port.get('provenance') or position.shape != (3,) or not np.isfinite(position).all()
                    or axis.shape != (3,) or not np.isfinite(axis).all() or not np.isclose(np.linalg.norm(axis), 1)):
                raise ValueError('Invalid semantic connection port: ' + name)
            port_ids.add(port['id'])
        for boundary in node.get('boundaries', {}).values():
            points = np.asarray(boundary.get('points_m'), dtype=float)
            if boundary.get('frame') != 'object' or points.ndim != 2 or points.shape[1] != 3 or not np.isfinite(points).all():
                raise ValueError('Invalid semantic boundary coordinates: ' + name)
        active.remove(name)
        visited.add(name)

    for name in named:
        visit(name)
    return named


def load_scene(path):
    scene = json.loads(Path(path).read_text(encoding="utf-8"))
    validate_scene(scene)
    return scene


def world_vertices(node):
    vertices = np.asarray(node["geometry"]["vertices_m"])
    matrix = np.asarray(node["world_transform"])
    return vertices @ matrix[:3, :3].T + matrix[:3, 3]


def ownership_report(scene):
    named = validate_scene(scene)
    checks = []
    for node in named.values():
        if node["role"] != "side_window":
            continue
        ancestors, parent = [], node.get("parent")
        while parent:
            ancestors.append(named[parent])
            parent = named[parent].get("parent")
        door = next((n for n in ancestors if n["role"] == "door_assembly"), None)
        checks.append(dict(window=node["id"], door=door["id"] if door else None,
                           passed=bool(door and door.get("joint"))))
    return dict(checks=checks, applicable=bool(checks), passed=all(c["passed"] for c in checks),
                contact_verified=False)
