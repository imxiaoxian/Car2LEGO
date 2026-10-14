"""Discrete F40 layout recipes. No part is scaled; each ratio solves its own grid."""

from collections import defaultdict
import numpy as np
from ortools.sat.python import cp_model

from .scene import AssemblyScene, BuildStep, Joint, Module, PartInstance, Transform, IDENTITY
from .specifications import CAPABILITIES, F40_SPEC, target_dimensions
from .requirements import requirements_for_scale

TURN = (0., 0., 1., 0., 1., 0., -1., 0., 0.)
REVERSE = (-1., 0., 0., 0., 1., 0., 0., 0., -1.)
FRONT_FACE = (1., 0., 0., 0., 0., -1., 0., 1., 0.)
REAR_FACE = (1., 0., 0., 0., 0., 1., 0., -1., 0.)
PROFILES = {"1:38": ("6014.dat", "6015.dat", 25., 14.),
            "1:24": ("18976.dat", "18977.dat", 30., 14.),
            "1:16": ("56145.dat", "44309.dat", 54., 27.),
            "1:12": ("41896.dat", "41897.dat", 70., 35.)}


def solve_grid(target: dict, scale: str = "1:24", requirements: dict | None = None) -> dict:
    policy = requirements or requirements_for_scale(scale)
    model = cp_model.CpModel()
    values = {}
    errors = []
    for key, unit in (("length", 20), ("width", 20), ("height", 8), ("wheelbase", 20)):
        value = model.NewIntVar(max(2, int(target[key] / unit) - 3), int(target[key] / unit) + 4, key)
        error = model.NewIntVar(0, 100000, key + "_error")
        model.AddAbsEquality(error, value * unit * 100 - round(target[key] * 100))
        tolerance = policy["dimension_tolerances_percent"][key]
        model.Add(error <= round(target[key] * tolerance))
        values[key] = value
        errors.append(error * (3 if key in ("length", "wheelbase") else 1))
    model.Add(values["wheelbase"] + 4 <= values["length"])
    # Bearings attach to the stud grid only if front/rear axle centres land on
    # full studs. Solving each dimension independently produced half-stud axles.
    overhang = model.NewIntVar(2, 10000, "overhang_studs")
    model.Add(values["length"] - values["wheelbase"] == overhang * 2)
    model.Minimize(sum(errors))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5
    solver.parameters.num_search_workers = 1
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise ValueError("No compatible discrete scale layout")
    return {key: solver.Value(value) * (8 if key == "height" else 20) for key, value in values.items()}


def _initial_recipe(design_id: str, scale: str, intent: dict | None = None, vehicle: dict | None = None,
              spec: dict | None = None) -> AssemblyScene:
    intent = intent or {}
    spec = spec or dict(F40_SPEC)
    target = target_dimensions(spec, scale)
    policy = requirements_for_scale(scale)
    grid = solve_grid(target, scale, policy)
    length, width, height, wheelbase = (grid[k] for k in ("length", "width", "height", "wheelbase"))
    rim, tyre, radius, tyre_half = PROFILES[scale]
    color, trim = intent.get("body_color_id", 4), intent.get("accent_color_id", 0)
    parts, joints = [], []
    modules = [Module(id="chassis", structural=True), Module(id="wheel_mounts", depends_on=["chassis"]),
               Module(id="cockpit", depends_on=["chassis"]), Module(id="engine", depends_on=["chassis"]),
               Module(id="body_frame", depends_on=["wheel_mounts", "cockpit", "engine"]),
               Module(id="front_hood", depends_on=["body_frame"]), Module(id="engine_cover", depends_on=["body_frame"]),
               Module(id="doors", depends_on=["body_frame"]), Module(id="details", depends_on=["front_hood", "engine_cover", "doors"])]
    rear_axle, front_axle = (length - wheelbase) / 2, (length + wheelbase) / 2
    deck = round((radius + 24) / 8) * 8
    roof = height - 8
    nose_end, cabin_end = round(length * .35 / 20) * 20, round(length * .60 / 20) * 20
    # Front at Z=0, rear at Z=length. Wheel sweep volumes are locked before body placement.
    def add(module, number, c, x, h, z, rotation=IDENTITY, feature=""):
        p = PartInstance(id=f"{module}_{len(parts):04d}", part_num=number, color_id=int(c), module=module,
                         transform=Transform(position=(float(x), float(-h), float(z)), rotation=rotation), feature=feature)
        parts.append(p)
        return p

    def strip(module, x, z0, z1, h, c, feature=""):
        # 1x2 plates overlap seams between layers and use real 20 LDU pitches.
        for z in range(int(z0) + 20, int(z1) - 19, 40):
            add(module, "3023.dat", c, x, h, z, TURN, feature)
        if (int(z1) - int(z0)) % 40:
            add(module, "3024.dat", c, x, h, int(z1) - 10, feature=feature)

    for x in (-10, 10):
        strip("chassis", x, 0, length, 24, trim, "load_bearing_spine")
    for z in range(40, int(length), 40):
        add("chassis", "3022.dat", trim, 0, 32, z, feature="spine_bridge")
    for z in range(10, int(length), 20):
        if min(abs(z - rear_axle), abs(z - front_axle)) < radius + 12:
            continue
        for x in range(-int(width / 2) + 10, int(width / 2), 20):
            if abs(x) > 20:
                add("chassis", "3024.dat", trim, x, 24, z, feature="floor")
    for z in range(20, int(length), 40):
        if min(abs(z - rear_axle), abs(z - front_axle)) < radius + 32:
            continue
        for x in range(-int(width / 2) + 40, int(width / 2) - 39, 80):
            add("chassis", "3020.dat", trim, x, 32, z, feature="floor_bridge")
    for side in (-1, 1):
        for axle_index, z in enumerate((rear_axle, front_axle)):
            mid = side * (width / 2 - tyre_half)
            module = f"wheel_{side + 1}_{axle_index}"
            modules.append(Module(id=module, depends_on=["wheel_mounts"]))
            # Exact tyre-rim origin offset comes from their native fixed ports.
            add(module, rim, 71, mid + (6 if rim in ("6014.dat", "18976.dat") else 0), radius, z, TURN, "rim")
            add(module, tyre, 0, mid, radius, z, TURN, "tyre")
            mount = add("wheel_mounts", "3700.dat", trim, side * 30, radius, z, TURN, "axle_bearing")
            add("wheel_mounts", "3705.dat", trim, 0, radius - 10, z, TURN, "axle")
            joints.append(Joint(id=module + "_spin", parent="wheel_mounts", child=module, pivot=(mid, -radius, z),
                                axis=(1., 0., 0.), limits=(0., 360.), capability="rolling_wheels", implemented=False))
        sill_x = side * (width / 2 - 10)
        strip("body_frame", sill_x, nose_end, cabin_end, deck - 16, color, "side_sill")
        strip("body_frame", sill_x, nose_end, cabin_end, deck - 8, trim, "body_seam")
        for z in (nose_end + 10, cabin_end - 10):
            for h in range(int(deck), int(roof), 24):
                add("body_frame", "3005.dat", color, side * (width / 2 - 30), h, z, feature="cabin_pillar")
        for z in range(10, int(length), 20):
            distance = min(abs(z - rear_axle), abs(z - front_axle))
            if distance < radius:
                h = max(deck, radius + np.sqrt(max(0, radius ** 2 - distance ** 2)) + 12)
                h = round(h / 8) * 8
                add("body_frame", "11477.dat", color, sill_x, h, z, REVERSE if z < length / 2 else IDENTITY, "wheel_arch")
    for x in (-30, 30):
        add("cockpit", "4079.dat", 0, x, deck, (nose_end + cabin_end) / 2, REVERSE, "seat")
    add("cockpit", "3829c01.dat", 0, -30, deck + 24, nose_end + 20, feature="steering_wheel")
    for x in range(-int(width / 2) + 30, int(width / 2) - 20, 20):
        add("cockpit", "3069b.dat", 0, x, deck + 8, nose_end + 10, feature="dashboard")
    for z in range(int(cabin_end) + 20, int(length) - 60, 40):
        add("engine", "3022.dat", 72, 0, deck, z, feature="engine_block")
        for side in (-1, 1):
            add("engine", "6141.dat", 71, side * 20, deck + 8, z, feature="engine_cylinder")

    for module, z0, z1, h, capability in (("front_hood", 0, nose_end, deck + 8, "front_hood"),
                                         ("engine_cover", cabin_end, length, deck + 16, "engine_cover")):
        pivot_z = z1 - 20 if module == "front_hood" else z0 + 20
        for x in (-30, 30):
            base = add("body_frame", "3937.dat", trim, x, h - 16, pivot_z, feature="hinge_base")
            leaf = add(module, "3938.dat", color, x, h - 16, pivot_z, feature="hinge_leaf")
        for x in range(-int(width / 2) + 30, int(width / 2) - 20, 40):
            for z in range(int(z0) + 30, int(z1) - 20, 80):
                add(module, "30363.dat" if module == "front_hood" else "87079.dat",
                    color if module == "front_hood" else 47, x, h, z,
                    REVERSE if module == "front_hood" else TURN, "wedge_nose" if module == "front_hood" else "transparent_engine_cover")
        joints.append(Joint(id=capability, parent="body_frame", child=module, pivot=(0., -h + 6, pivot_z),
                            axis=(1., 0., 0.), limits=(0., 65.), capability=capability,
                            mounting_parts=(base.id, leaf.id), implemented=scale != "1:38"))
    # Modular glazing, fitted independently to the selected stud width.
    for x in range(-int(width / 2) + 30, int(width / 2) - 20, 40):
        add("cockpit", "3039.dat", 47, x, roof - 8, nose_end + 30, REVERSE, "windshield")
        for z in range(int(nose_end) + 70, int(cabin_end), 40):
            add("cockpit", "3068b.dat", color, x, roof, z, feature="roof")
    for side in (-1, 1):
        for z in range(int(nose_end) + 30, int(cabin_end) - 20, 40):
            add("doors", "3069b.dat", color, side * (width / 2 - 10), deck, z, TURN, "door")
            add("doors", "2412b.dat", trim, side * (width / 2 - 10), deck + 8, cabin_end - 10, TURN, "side_intake") if z == nose_end + 30 else None
        if scale in ("1:16", "1:12"):
            joints.append(Joint(id=f"door_{side + 1}", parent="body_frame", child="doors", pivot=(side * (width / 2 - 10), -deck, nose_end),
                                axis=(0., 1., 0.), limits=(0., 60.), capability="doors", implemented=False))
        add("details", "3005.dat", color, side * (width / 2 - 30), deck + 40, length - 30, feature="wing_support")
        for x in (side * 30, side * 50):
            add("details", "6141.dat", 36 if abs(x) == 30 else 46, x, deck, length + 4, REAR_FACE, "taillight")
            add("details", "3069b.dat", 47, x, deck, 10, feature="headlight")
    for x in range(-int(width / 2) + 40, int(width / 2) - 20, 80):
        add("details", "87079.dat", color, x, deck + 48, length - 30, feature="rear_wing")
    for z in range(int(cabin_end) + 40, int(length) - 30, 20):
        for x in (-30, 30):
            add("engine_cover", "2412b.dat", trim, x, deck + 24, z, feature="engine_louvres")
    if scale in ("1:16", "1:12"):
        joints.append(Joint(id="front_steering", parent="chassis", child="wheel_mounts", pivot=(0., -radius, front_axle),
                            axis=(0., 1., 0.), limits=(-25., 25.), capability="steering", implemented=False))
    if scale == "1:12":
        joints.append(Joint(id="suspension", kind="prismatic", parent="chassis", child="wheel_mounts", pivot=(0., -radius, front_axle),
                            axis=(0., 1., 0.), limits=(-8., 8.), capability="independent_suspension", implemented=False))
    steps = []
    for module in modules:
        group = [p.id for p in parts if p.module == module.id]
        for offset in range(0, len(group), policy["max_step_parts"]):
            steps.append(BuildStep(index=len(steps) + 1, module=module.id, parts=group[offset:offset + policy["max_step_parts"]]))
    return AssemblyScene(design_id=design_id, vehicle=vehicle or {"make": "Ferrari", "model": "F40", "year": 1990},
                         scale=scale, specifications=spec, target_ldu=target, parts=parts, modules=modules, joints=joints, steps=steps,
                         planning={"solver": "OR-Tools CP-SAT", "grid": grid, "required_capabilities": CAPABILITIES[scale], "scale_requirements": policy,
                                   "wheel_centres_z": [rear_axle, front_axle], "recipe": "f40-experimental-1",
                                   "intent": intent, "recipe_verified": False})


def build_f40(design_id: str, scale: str, intent: dict | None = None, vehicle: dict | None = None,
              spec: dict | None = None, requirements: dict | None = None) -> AssemblyScene:
    f40 = vehicle is None or (vehicle.get("make", "").lower() == "ferrari" and
                             vehicle.get("model", "").lower().replace(" ", "") == "f40")
    if f40:
        # The surface recipe derives every landmark from the solved grid, so it
        # serves all four scales. f40.py remains as a routable fallback for
        # non-F40 vehicles and for comparing recipes during development.
        from .f40_detail import build_scene
    else:
        from .f40 import build_scene
    return build_scene(design_id, scale, intent, vehicle, spec, requirements=requirements)
