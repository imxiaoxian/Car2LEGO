"""Direct surface inspection inside Blender; no reference or rendered images used."""
import bpy
import json
import math
from collections import Counter
from pathlib import Path

from mathutils import Vector
from mathutils.bvhtree import BVHTree

directory = Path(OUTPUT_DIRECTORY)
scene = bpy.context.scene
depsgraph = bpy.context.evaluated_depsgraph_get()
geometry = {}
for obj in scene.objects:
    if obj.type not in {"MESH", "CURVE"} or obj.hide_render:
        continue
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    mesh.calc_loop_triangles()
    points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
    faces = [tuple(f.vertices) for f in mesh.polygons]
    evaluated.to_mesh_clear()
    if points and triangles:
        geometry[obj.name] = dict(obj=obj, points=points, triangles=triangles,
            tree=BVHTree.FromPolygons(points, faces))
body_trees = [g["tree"] for g in geometry.values() if g["obj"].get("car_role") == "body"]


def direction(obj, points):
    name, role = obj.name.lower(), obj.get("car_role", "")
    centre = sum(points, Vector()) / len(points)
    side = -1 if centre.y < 0 else 1
    if name.startswith(("pop up cover", "auxiliary lens", "auxiliary lamp recess", "engine cover black louver", "rear deck vent")):
        return Vector((0, 0, 1))
    if role in {"windscreen", "windshield"}:
        return Vector((-1, 0, 1)).normalized()
    if role == "rear_window":
        return Vector((1, 0, 1)).normalized()
    if role in {"side_window", "quarter_window", "a_pillar", "b_pillar", "cabin_buttress", "intake_housing"}:
        return Vector((0, side, .25)).normalized()
    if role in {"front_fascia", "rear_fascia"}:
        return Vector((-1 if role == "front_fascia" else 1, 0, 0))
    if role in {"front_fender", "rear_fender"}:
        return Vector((0, side, .7)).normalized()
    if role in {"cowl", "header", "roof", "engine_deck"}:
        return Vector((0, 0, 1))
    return None


details, issues = [], []
for name, data in geometry.items():
    obj, points, triangles = data["obj"], data["points"], data["triangles"]
    preferred = direction(obj, points)
    if preferred is None:
        continue
    candidates, area = [], 0.0
    degenerate = 0
    for ids in triangles:
        a, b, c = [points[i] for i in ids]
        normal = (b - a).cross(c - a)
        size = normal.length / 2
        if size <= 1e-12:
            degenerate += 1
            continue
        normal.normalize()
        if normal.dot(preferred) < .2:
            continue
        area += size
        candidates.append((area, a, b, c, normal))
    if not candidates:
        continue
    visible, blockers, buried, samples, local_cover = 0, Counter(), [], [], []
    cursor = 0
    for i in range(48):
        target = area * (i + .5) / 48
        while cursor < len(candidates) - 1 and candidates[cursor][0] < target:
            cursor += 1
        _, a, b, c, normal = candidates[cursor]
        u, v = (i * .61803398875 + .37) % 1, (i * .41421356237 + .19) % 1
        if u + v > 1:
            u, v = 1 - u, 1 - v
        point = a + (b - a) * u + (c - a) * v
        hit, position, _, _, hit_obj, _ = scene.ray_cast(depsgraph, point + normal * 4, -normal, distance=4.01)
        own_frame = bool(hit and obj.parent and hit_obj.parent == obj.parent and hit_obj.get("car_role") == "door_frame")
        clear = bool(hit and (hit_obj.name == name or own_frame))
        visible += clear
        row = dict(point_m=list(point), visible=clear, first_hit=hit_obj.name if hit else None,
                   occluder_distance_m=(position - point).length if hit and not clear else 0)
        local_hit, local_position, _, _, local_obj, _ = scene.ray_cast(
            depsgraph, point + normal * .04, -normal, distance=.05)
        covered = bool(local_hit and local_obj.name != name and (local_position - point).dot(normal) > .00075)
        row["local_cover"] = local_obj.name if covered else None
        if covered:
            local_cover.append(row)
        if not clear:
            blockers[row["first_hit"] or "no_hit"] += 1
        near = [tree.find_nearest(point) for tree in body_trees]
        near = [h for h in near if h[0] is not None]
        if near:
            surface, normal_body, _, distance = min(near, key=lambda h: h[3])
            signed = distance * (-1 if (point - surface).dot(normal_body) < 0 else 1)
            row["signed_body_distance_m"] = signed
            if signed < -.012:
                buried.append(row)
        samples.append(row)
    detail = dict(object=name, role=obj.get("car_role", ""), region=obj.get("car_connection_region", ""),
        visibility_fraction=visible / 48, first_hit_counts=dict(blockers), local_cover_fraction=len(local_cover) / 48,
        deeply_embedded_samples=len(buried), degenerate_triangles=degenerate,
        triangles=len(triangles), samples=samples)
    details.append(detail)
    # Long rays can hit a legitimate rear wing. Backing panels and hidden roof laps are intentional.
    exposed_detail = name.startswith(("Pop up cover", "Auxiliary lens", "Engine cover black louver", "Raised intake shoulder"))
    if exposed_detail and len(local_cover) >= 10:
        issue = dict(kind="locally_covered_exterior_detail", object=name, local_cover_fraction=len(local_cover) / 48,
                     blockers=dict(Counter(s["local_cover"] for s in local_cover)),
                     points_m=[s["point_m"] for s in local_cover[:3]])
        issues.append(issue)
    if len(buried) >= 5:
        issues.append(dict(kind="deeply_embedded_surface", object=name, samples=len(buried),
            max_depth_m=max(-s["signed_body_distance_m"] for s in buried), points_m=[s["point_m"] for s in buried[:3]]))
    if degenerate > max(3, len(triangles) * .01):
        issues.append(dict(kind="degenerate_faces", object=name, count=degenerate,
            points_m=[list(sum(points, Vector()) / len(points))]))

markers = bpy.data.collections.new("Detail Inspection - flagged locations")
scene.collection.children.link(markers)
for i, issue in enumerate(issues, 1):
    issue["id"] = "detail-%03d" % i
    for j, position in enumerate(issue["points_m"]):
        marker = bpy.data.objects.new(issue["id"] + " " + issue["object"] + " %d" % j, None)
        markers.objects.link(marker)
        marker.empty_display_type = "SPHERE"
        marker.empty_display_size = .025
        marker.location = position
        marker.show_in_front = True
        marker.hide_render = True
        marker.color = (1, .08, .02, 1)
        marker["issue"] = issue["kind"]
        marker["source_object"] = issue["object"]
        marker["report_id"] = issue["id"]
bpy.ops.object.select_all(action="DESELECT")
for obj in markers.objects:
    obj.select_set(True)
if markers.objects:
    bpy.context.view_layer.objects.active = list(markers.objects)[0]
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type != "VIEW_3D":
            continue
        space = area.spaces.active
        space.clip_start, space.clip_end = .001, 1000
        space.shading.type = "SOLID"
        space.shading.color_type = "MATERIAL"
        space.overlay.show_overlays = True
        space.region_3d.view_location = (2.07, 0, .55)
        space.region_3d.view_distance = 5.5
        space.region_3d.view_rotation = Vector((-1, -1, .55)).to_track_quat("Z", "Y")
report = dict(schema_version=1, source_blend=SOURCE_BLEND, source_sha256=SOURCE_SHA256,
    method="evaluated 3D meshes, area-stratified triangle samples, global/local outward ray casts and signed nearest body surfaces",
    sampled_objects=len(details), issues=issues, details=details, appearance_accepted=False,
    limitations=["Flags are inspection candidates, not automatic physical or visual rejection.",
                 "Signed nearest-surface distances assume an outward closed body and are local penetration estimates.",
                 "Exterior visibility tests use 48 samples per selected object; small defects may be missed.",
                 "Local cover flags concern exposed details within 40 mm; distant wing overhang and deliberate backing layers are excluded.",
                 "Coplanar intentional overlaps and trim can cause flags; complete self-intersection certification is not performed."])
(directory / "detail-inspection.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
bpy.ops.wm.save_as_mainfile(filepath=str(directory / "inspected.blend"))
print(json.dumps(dict(sampled_objects=len(details), issues=len(issues), issue_kinds=dict(Counter(i["kind"] for i in issues)))))
