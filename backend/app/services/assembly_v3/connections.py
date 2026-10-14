"""Connector matching in world LDraw coordinates; unknown combinations fail closed."""

from collections import defaultdict
import networkx as nx
import numpy as np
from scipy.spatial import cKDTree

from .catalog import Port, ports
from .scene import AssemblyScene, Connection

# Explicit Studio axle compatibility subset; more types require dedicated fixtures.
AXLE_PAIRS = {frozenset(p) for p in (("pin_socket", "pin"), ("pin_socket", "pin_solid"),
    ("pin_socket", "axle"), ("pin_socket", "axle_guard"), ("round_hole", "pin"),
    ("round_hole", "pin_solid"), ("round_hole", "axle"), ("round_hole", "axle_guard"),
    ("axle_socket", "axle"), ("axle_socket", "axle_guard"), ("axle_socket", "bar"),
    ("axle_socket", "bar_socket"), ("pin", "bar"), ("pin", "bar_socket"),
    ("round_hole", "round_bar"), ("clip", "bar"), ("clip", "bar_socket"),
    ("small_pin_socket", "small_pin"), ("bar_socket", "small_pin"))}


def compatible(a: Port, b: Port) -> bool:
    if {a.kind, b.kind} == {"stud", "hole"}:
        stud, hole = (a, b) if a.kind == "stud" else (b, a)
        allowed = {-2: None, 10: {10, 20}, 20: {10, 20, 30}, 3: {20, 25},
                   40: {40}, 50: {50}, 60: {20}}
        return stud.area >= 4 and stud.altitude in allowed and (allowed[stud.altitude] is None or hole.altitude in allowed[stud.altitude])
    if a.kind == b.kind == "axle":
        return (not a.grabbing_required or b.grabbing) and (not b.grabbing_required or a.grabbing) and frozenset((a.semantic, b.semantic)) in AXLE_PAIRS
    if a.kind == b.kind and a.kind in ("fixed", "hinge"):
        return a.subtype // 2 == b.subtype // 2 and a.subtype % 2 != b.subtype % 2 and a.tag == b.tag
    return False


def axle_match(a, b, tolerance=.25) -> bool:
    """Studio shafts occupy position - direction * [0, length].

    Require collinear, overlapping insertion segments, respect end stops and
    guard collars, and align keyed axle profiles modulo 90 degrees. A touching
    endpoint alone is insufficient evidence of a retained connection.
    """
    _, pa, oa, da, fa = a
    _, pb, ob, db, fb = b
    dot = float(da @ db)
    if abs(dot) < .9999 or not compatible(pa, pb):
        return False
    delta = ob - oa
    offset = float(delta @ da)
    if np.linalg.norm(delta - offset * da) > tolerance:
        return False
    la = pa.length - (2 if pa.semantic == "axle_guard" and pb.semantic != "pin_socket" else 0)
    lb = pb.length - (2 if pb.semantic == "axle_guard" and pa.semantic != "pin_socket" else 0)
    if la <= 0 or lb <= 0:
        return False
    # Coordinates along da, including the opposing direction case.
    alo, ahi = -la, 0.
    blo, bhi = sorted((offset, offset - np.sign(dot) * lb))
    overlap = min(ahi, bhi) - max(alo, blo)
    if overlap < (4. - tolerance if "pin_socket" in (pa.semantic, pb.semantic) and "pin" not in (pa.semantic, pb.semantic) else tolerance):
        return False
    # A capped endpoint cannot sit inside the other insertion segment.
    for point, capped, low, high in ((0., pa.start_capped, blo, bhi),
            (-la, pa.end_capped or pa.semantic == "axle_guard", blo, bhi),
            (offset, pb.start_capped, alo, ahi),
            (offset - np.sign(dot) * lb, pb.end_capped or pb.semantic == "axle_guard", alo, ahi)):
        if capped and low + tolerance < point < high - tolerance:
            return False
    if pa.cross_type and pb.cross_type:
        cosine = abs(float(fa @ fb))
        if min(abs(cosine), abs(cosine - 1)) > 1e-4:
            return False
    return True


def world_ports(scene: AssemblyScene, part_ids: set[str] | None = None):
    world, unknown = [], []
    for part in scene.parts:
        if part_ids is not None and part.id not in part_ids:
            continue
        matrix = np.array(part.transform.rotation).reshape(3, 3)
        origin = np.array(part.transform.position)
        try:
            for port in ports(part.part_num):
                if port.kind in ("stud", "hole") and (port.altitude in (0, -1) or port.area < 4):
                    continue
                world.append((part.id, port, origin + matrix @ port.position,
                              matrix @ port.direction, matrix @ port.forward))
        except ValueError as exc:
            unknown.append({"part": part.id, "reason": str(exc)})
    return world, unknown


def infer_connections(scene: AssemblyScene, part_ids: set[str] | None = None) -> tuple[list[Connection], dict]:
    """Infer full connectivity, or a stated subset for a local mounting check."""
    world, unknown = world_ports(scene, part_ids)
    edges = {}
    if world:
        tree = cKDTree(np.array([p[2] for p in world]))
        for i, j in sorted(tree.query_pairs(.25)):
            a, b = world[i], world[j]
            if a[1].kind == b[1].kind == "axle":
                continue  # Shaft matching uses insertion segments, not endpoint proximity.
            if a[0] == b[0] or not compatible(a[1], b[1]):
                continue
            dot = float(a[3] @ b[3])
            if (a[1].kind in ("stud", "hole", "fixed") and dot < .9999) or abs(dot) < .9999:
                continue
            key = tuple(sorted((a[0], b[0])))
            edges.setdefault(key, Connection(a=a[0], b=b[0], port_a=a[1].id, port_b=b[1].id,
                                              kind=f"{a[1].kind}:{b[1].kind}", evidence="Studio .conn world port match <=0.25 LDU"))
        shafts = [p for p in world if p[1].kind == "axle"]
        if shafts:
            centres = np.array([p[2] - p[3] * p[1].length / 2 for p in shafts])
            radii = np.array([p[1].length / 2 for p in shafts])
            shaft_tree = cKDTree(centres)
            for i, a in enumerate(shafts):
                for j in sorted(shaft_tree.query_ball_point(centres[i], radii[i] + radii.max() + .25)):
                    if j <= i or a[0] == shafts[j][0] or not axle_match(a, shafts[j]):
                        continue
                    b = shafts[j]
                    key = tuple(sorted((a[0], b[0])))
                    edges.setdefault(key, Connection(a=a[0], b=b[0], port_a=a[1].id, port_b=b[1].id,
                        kind="axle:axle", evidence="Studio .conn collinear insertion overlap, cap and keyed-profile checks"))
    graph = nx.Graph()
    graph.add_nodes_from(p.id for p in scene.parts if part_ids is None or p.id in part_ids)
    graph.add_edges_from(edges)
    structural = {m.id for m in scene.modules if m.structural}
    anchors = [p.id for p in scene.parts if p.module in structural and p.id in graph]
    # One real component must contain all load bearing pieces, not just any anchor.
    components = list(nx.connected_components(graph))
    main = max((c for c in components if set(anchors) & c), key=lambda c: (len(set(anchors) & c), len(c)), default=set())
    root = next((p for p in anchors if p in main), None)
    reached = nx.node_connected_component(graph, root) if root else set()
    disconnected = sorted(set(graph) - reached)
    return list(edges.values()), {"root": root, "edges": len(edges), "components": nx.number_connected_components(graph),
                                 "disconnected_parts": disconnected, "unknown_connections": unknown,
                                 "status": "passed" if root and not disconnected and not unknown else "failed"}


def attachment_candidates(parent, child_num: str, rotation: tuple) -> list[tuple]:
    """Legal candidate origins, used by local repair instead of free coordinate edits."""
    pm = np.array(parent.transform.rotation).reshape(3, 3)
    cm = np.array(rotation).reshape(3, 3)
    candidates = []
    for a in ports(parent.part_num):
        for b in ports(child_num):
            if compatible(a, b) and float((pm @ a.direction) @ (cm @ b.direction)) > .9999:
                origin = np.array(parent.transform.position) + pm @ a.position - cm @ b.position
                candidates.append(tuple(float(x) for x in origin))
    return list(dict.fromkeys(candidates))
