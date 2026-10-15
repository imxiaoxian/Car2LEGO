"""Common export and camera rig; executed by Blender MCP after model creation."""
import bpy
import json
import math
from pathlib import Path
from mathutils import Vector

directory = Path(OUTPUT_DIRECTORY)
scene = bpy.context.scene
scene.unit_settings.system = "METRIC"
scene.unit_settings.scale_length = 1
for obj in list(scene.objects):
    if obj.type in {"LIGHT", "CAMERA"}:
        bpy.data.objects.remove(obj, do_unlink=True)
objects = [o for o in scene.objects if o.type in {"MESH", "CURVE", "SURFACE", "FONT"} and not o.hide_render]
if not objects:
    raise ValueError("Model contains no geometry")
bpy.context.view_layer.update()
depsgraph = bpy.context.evaluated_depsgraph_get()
points, object_bounds = [], []
for obj in objects:
    evaluated = obj.evaluated_get(depsgraph)
    mesh = evaluated.to_mesh()
    vertices = [evaluated.matrix_world @ v.co for v in mesh.vertices]
    evaluated.to_mesh_clear()
    if not vertices:
        continue
    points.extend(vertices)
    obj_low = [min(p[i] for p in vertices) for i in range(3)]
    obj_high = [max(p[i] for p in vertices) for i in range(3)]
    object_bounds.append(dict(name=obj.name, bounds_m=[obj_low, obj_high]))
low = Vector([min(p[i] for p in points) for i in range(3)])
high = Vector([max(p[i] for p in points) for i in range(3)])
centre, size = (low + high) / 2, high - low
if EXPORT:
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.export_scene.gltf(filepath=str(directory / "calibrated.glb"), export_format="GLB",
        use_selection=True, export_yup=False, export_apply=True)
    # OBJ uses full-size mm with the same X-long / Z-up frame.
    bpy.ops.wm.obj_export(filepath=str(directory / "calibrated-mm.obj"), export_selected_objects=True,
        forward_axis="Y", up_axis="Z", global_scale=1000)
metadata = {"bounds_m": [list(low), list(high)], "dimensions_mm": list(size * 1000),
    "objects": object_bounds, "blender_version": bpy.app.version_string,
    "measurement": "evaluated world-space vertices; mirrors and trim included"}
(directory / "scene-metrics.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
scene.render.engine = "CYCLES"
scene.cycles.samples = 12
scene.cycles.use_denoising = True
try:
    preferences = bpy.context.preferences.addons["cycles"].preferences
    preferences.compute_device_type = "CUDA"
    preferences.get_devices()
    for device in preferences.devices:
        device.use = device.type == "CUDA"
    if any(device.use for device in preferences.devices):
        scene.cycles.device = "GPU"
except (TypeError, RuntimeError):
    pass
scene.render.resolution_x = 1000
scene.render.resolution_y = 700
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = "PNG"
scene.render.image_settings.color_mode = "RGBA"
scene.render.film_transparent = True
scene.world.use_nodes = True
scene.world.node_tree.nodes["Background"].inputs["Color"].default_value = (.7, .7, .7, 1)
scene.world.node_tree.nodes["Background"].inputs["Strength"].default_value = .6
scene.view_settings.view_transform = "AgX"
for name, position, energy, scale in [("Key", (-2,-4,6), 2200, 5), ("Fill", (2,4,4), 1800, 5), ("Rim", (5,-2,5), 2400, 4)]:
    bpy.ops.object.light_add(type="AREA", location=centre + Vector(position))
    light = bpy.context.object
    light.name = name
    light.data.energy = energy
    light.data.shape = "DISK"
    light.data.size = scale
    light.rotation_euler = (centre - light.location).to_track_quat("-Z", "Y").to_euler()
bpy.ops.object.camera_add()
camera = bpy.context.object
scene.camera = camera
camera.data.type = "ORTHO"
directions = {"front": (-1,0,0), "back": (1,0,0), "left": (0,-1,0), "right": (0,1,0),
              "three-quarter": (-1,-1,.55), "rear-quarter": (1,1,.55)}
for name, direction in directions.items():
    camera.location = centre + Vector(direction).normalized() * 12
    camera.rotation_euler = (centre - camera.location).to_track_quat("-Z", "Y").to_euler()
    rotation = camera.rotation_euler.to_matrix().transposed()
    projected = [rotation @ (p - centre) for p in points]
    width = max(p.x for p in projected) - min(p.x for p in projected)
    height = max(p.y for p in projected) - min(p.y for p in projected)
    camera.data.ortho_scale = max(width, height * 1000/700) * 1.15
    scene.render.filepath = str(directory / f"render-{name}.png")
    bpy.ops.render.render(write_still=True)
if EXPORT:
    bpy.ops.wm.save_as_mainfile(filepath=str(directory / "model.blend"))
print("Export/render complete", list(size))
