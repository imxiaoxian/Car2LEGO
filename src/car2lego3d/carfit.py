"""Mesh-conditioned sports-car fitting with an explicit standard-parts design prior.

This is a constrained vehicle approximation, not arbitrary mesh-to-brick recovery.
"""
import csv
from collections import Counter
from dataclasses import asdict, dataclass, replace
from pathlib import Path

import numpy as np
import trimesh
from scipy.ndimage import gaussian_filter1d
from scipy.spatial import cKDTree

from .common import digest, stage, write_json
from .lego import PALETTE, color_visual, load_mesh, orient
from .requirements import RECIPE_LENGTH_RANGE, RECIPE_WIDTHS


IDENTITY = (1, 0, 0, 0, 1, 0, 0, 0, 1)
QUARTER = (0, 0, 1, 0, 1, 0, -1, 0, 0)
HALF = (-1, 0, 0, 0, 1, 0, 0, 0, -1)
BACK_QUARTER = (0, 0, -1, 0, 1, 0, 1, 0, 0)
BRICKS = {"3005": (1, 1), "3004": (2, 1), "3010": (4, 1), "3009": (6, 1),
          "3003": (2, 2), "3002": (3, 2), "3001": (4, 2)}
PLATES = {"3024": (1, 1), "3023": (2, 1), "3710": (4, 1), "3666": (6, 1),
          "3022": (2, 2), "3021": (3, 2), "3020": (4, 2), "3795": (6, 2)}
TILES = {"3070b": (1, 1), "3069b": (2, 1), "2431": (4, 1), "6636": (6, 1),
         "3068b": (2, 2), "87079": (4, 2)}


@dataclass(frozen=True)
class Placement:
    part: str
    color: int
    position: tuple
    rotation: tuple
    module: str
    step: int


def fit_mesh(mesh, length=None, up_axis="z", yaw=0, color=None, specifications=None, width=None,
             scale=None, requirements_plan=None):
    plan = None
    if specifications is not None:
        from .requirements import plan_design, validate_plan
        if requirements_plan is not None:
            grid = requirements_plan["grid"]
            validate_plan(requirements_plan, specifications, grid["length_studs"], grid["width_studs"], scale)
            if ((length is not None and length != grid["length_studs"])
                    or (width is not None and width != grid["width_studs"])):
                raise ValueError("Grid arguments conflict with the requirements snapshot.")
            plan = requirements_plan
        else:
            plan = plan_design(specifications, scale, length, width)
        if not plan["generation"]["draft_recipe_available"]:
            raise ValueError(" ".join(plan["generation"]["blockers"]))
        length, width = (plan["grid"][key] for key in ("length_studs", "width_studs"))
    elif scale is not None or requirements_plan is not None:
        raise ValueError("Scale requirements need sourced vehicle specifications.")
    length = 24 if length is None else length
    if (isinstance(length, bool) or not isinstance(length, int)
            or not RECIPE_LENGTH_RANGE[0] <= length <= RECIPE_LENGTH_RANGE[1]):
        raise ValueError(f"The sports-car part family currently supports {RECIPE_LENGTH_RANGE[0]}.."
                         f"{RECIPE_LENGTH_RANGE[1]} integer studs.")
    color_override = color is not None
    mesh, alignment = orient(mesh, up_axis, yaw)
    if mesh.extents[0] < 1e-8 or mesh.extents[2] < 1e-8:
        raise ValueError("Mesh is degenerate; a volumetric vehicle is required.")
    calibration = None
    if specifications is not None:
        from .vehicle import calibrate_mesh, validate_spec
        validate_spec(specifications)
        mesh, calibration = calibrate_mesh(mesh, specifications)
    if width is None:
        width = 8
    if width not in RECIPE_WIDTHS:
        raise ValueError("Supported body widths are 8, 10 and 12 studs.")
    points, _ = trimesh.sample.sample_surface(mesh, 16000, seed=0)
    points = (points - mesh.bounds[0]) * (length - 1) / mesh.extents[0]
    vertices = (mesh.vertices - mesh.bounds[0]) * (length - 1) / mesh.extents[0]
    rgb = color_visual(mesh).vertex_colors[:, :3].astype(float)
    colors = rgb[cKDTree(vertices).query(points)[1]]
    profile = np.full(length, np.nan)
    for x in range(length):
        group = points[(points[:, 0] >= x - .5) & (points[:, 0] < x + .5), 2]
        if len(group):
            profile[x] = np.quantile(group, .96)
    valid = np.flatnonzero(np.isfinite(profile))
    profile = gaussian_filter1d(np.interp(np.arange(length), valid, profile[valid]), .8)
    roof = np.flatnonzero(profile > profile.max() * .94)
    flipped = bool(roof.mean() < (length - 1) * .47)
    if flipped:
        points[:, 0] = length - 1 - points[:, 0]
        profile = profile[::-1]
        roof = np.flatnonzero(profile > profile.max() * .94)
    raw_roof = [int(roof.min()), int(roof.max())]
    roof_end = int(np.clip(round(roof.mean()+1), 12, length-9))
    roof_start = roof_end-1
    side = (points[:, 1] < vertices[:, 1].max() * .2) | (points[:, 1] > vertices[:, 1].max() * .8)
    low = points[:, 2] < vertices[:, 2].max() * .4
    neutral = (colors.max(axis=1) - colors.min(axis=1)) < 30
    dark = colors.mean(axis=1) < 65
    histogram = gaussian_filter1d(np.histogram(points[side & low & (neutral | dark), 0],
                                             np.arange(length + 1) - .5)[0].astype(float), .8)
    axles = []
    for lo, hi in ((int(length * .13), int(length * .38)), (int(length * .68), int(length * .87))):
        axles.append(float(lo + np.argmax(histogram[lo:hi]) + .5))
    mesh_axles = axles.copy()
    axle_source = "mesh wheel hypotheses"
    if specifications is not None:
        from .vehicle import constrained_axles
        axles, axle_source = constrained_axles(specifications, length, mesh_axles,
                                               plan["target_scale_denominator"])
    chroma = rgb.max(axis=1) - rgb.min(axis=1)
    paint = np.median(rgb[chroma > 35], axis=0) if np.any(chroma > 35) else rgb.mean(axis=0)
    if color is None:
        candidates = {key: value for key, value in PALETTE.items() if key in (1, 2, 4, 14, 15, 25, 71)}
        unit = paint / max(np.linalg.norm(paint), 1)
        color = min(candidates, key=lambda key: np.linalg.norm(
            np.array(candidates[key]) / np.linalg.norm(candidates[key]) - unit))
    if color not in PALETTE:
        raise ValueError("Unsupported body color.")
    fit = {"length_studs": length, "width_studs": width, "body_color": color,
            "body_color_source": "override" if color_override else "mesh chroma",
            "axles_studs": axles, "roof_start_stud": roof_start, "roof_end_stud": roof_end,
            "source_axles_studs": mesh_axles, "axle_position_source": axle_source,
            "source_roof_interval_studs": raw_roof,
            "source_extents_in_studs": vertices.max(axis=0).tolist(),
            "height_profile_studs": profile.tolist(), "wheel_evidence_histogram": histogram.tolist(),
            "principal_axis_alignment_degrees": alignment, "front_orientation_flipped": flipped,
            "design_prior": "8/10/12-stud sports car; 24mm tyre family; 6-stud native windscreen; symmetric body",
            "inferred_parameters": ["axle positions", "roof position"] +
                                   ([] if color_override else ["dominant chromatic body color"]),
            "fixed_parameters": ["native tyre and windscreen size", "body deck height",
                                 "two-stud roof on native six-stud integrated canopy"],
            "limitations": ["Low side dark regions are wheel hypotheses, not trained semantic segmentation.",
                            "Part-family dimensions constrain the mesh fit; no exact vehicle CAD recovery."]}
    if calibration is not None:
        from .vehicle import dimension_report
        fit["physical_calibration"] = calibration
        fit["target_scale_denominator"] = plan["target_scale_denominator"]
        fit["requirements_plan"] = plan
        fit["physical_constraints"] = dimension_report(specifications, fit)
        fit["inferred_parameters"].remove("axle positions")
    return fit


class Car:
    def __init__(self, fit):
        self.fit = fit
        self.parts = []
        self.cells = {}

    def place(self, part, color, x, y, height, module, step, rotation=IDENTITY):
        self.parts.append(Placement(part, color,
            ((x - (self.fit["length_studs"] - 1) / 2) * 20, -height * 8,
             (y - (self.fit["width_studs"] - 1) / 2) * 20),
            rotation, module, step))

    def fill(self, xs, ys, zs, color):
        for x in xs:
            for y in ys:
                for z in zs:
                    self.cells[x, y, z] = color

    def clear(self, xs, ys, zs):
        for x in xs:
            for y in ys:
                for z in zs:
                    self.cells.pop((x, y, z), None)

    def pack(self):
        candidates = [(part, w, d, h, rotate) for catalog, h in ((BRICKS, 3), (PLATES, 1))
                      for part, (w0, d0) in catalog.items()
                      for w, d, rotate in ([(w0, d0, False)] if w0 == d0 else
                                          [(w0, d0, False), (d0, w0, True)])]
        owners = {}
        for x, y, z in sorted(self.cells, key=lambda p: (p[2], p[1], p[0])):
            if (x, y, z) in owners:
                continue
            color = self.cells[x, y, z]
            choices = []
            for part, w, d, h, rotate in candidates:
                points = [(x+dx, y+dy, z+dz) for dx in range(w) for dy in range(d) for dz in range(h)]
                if all(p not in owners and self.cells.get(p) == color for p in points):
                    choices.append((w*d*h, w*d, part, w, d, h, rotate, points))
            _, _, part, w, d, h, rotate, points = max(choices)
            self.place(part, color, x+(w-1)/2, y+(d-1)/2, z+h, "body and chassis", z+1,
                       QUARTER if rotate else IDENTITY)
            for point in points:
                owners[point] = len(self.parts)-1
        if set(owners) != set(self.cells):
            raise ValueError("Body packing omitted occupied cells.")

    def tiles(self, xs, ys, height, color, module, step):
        remaining = {(x, y) for x in xs for y in ys}
        for x, y in sorted(remaining):
            if (x, y) not in remaining:
                continue
            choices = []
            for part, (w0, d0) in TILES.items():
                for w, d, rotate in ((w0, d0, False), (d0, w0, True)):
                    footprint = {(x+dx, y+dy) for dx in range(w) for dy in range(d)}
                    if footprint <= remaining:
                        choices.append((w*d, part, w, d, rotate, footprint))
            _, part, w, d, rotate, footprint = max(choices)
            self.place(part, color, x+(w-1)/2, y+(d-1)/2, height, module, step,
                       QUARTER if rotate else IDENTITY)
            remaining -= footprint


def design(fit, rear_wing=True):
    car = Car(fit)
    length, width, paint = fit["length_studs"], fit["width_studs"], fit["body_color"]
    center = (width-1)/2
    cabin_left = (width-6)//2
    cabin_sides = [cabin_left, cabin_left+5]
    cabin = range(cabin_left+1, cabin_left+5)
    middle = range(2, width-2)
    edges = [0, 1, width-2, width-1]
    shoulders = [.5, width-1.5]
    start, end = fit["roof_start_stud"], fit["roof_end_stud"]
    front_glass, rear_glass = end-5, end
    car.fill(range(1, length-1), middle, range(2, 4), 0)
    car.fill(range(length), range(width), range(4, 8), paint)
    for axle in fit["axles_studs"]:
        x0 = int(axle-.5)
        car.clear(range(x0-1, x0+3), edges, range(2, 10))
        car.fill(range(x0, x0+2), [2, width-3], range(6, 8), paint)
        # Axle mounting bricks replace packed material on the same stud grid.
        car.clear(range(x0, x0+2), [2, width-3], range(3, 6))
        for side in (-1, 1):
            car.place("3700", 0, axle, center+side*(center-2), 6, "axle mounting", 6)
            car.place("18974", paint, axle, center+side*(width/2-1), 10, "wheel arches", 12,
                      IDENTITY if side == -1 else HALF)
            car.place("18977", 0, axle, center+side*center, 4.75, "tyres", 18)
            car.place("18976", 71, axle, center+side*center, 4.75, "wheel rims", 18,
                      IDENTITY if side == 1 else HALF)
        car.place({8: "3707", 10: "3737", 12: "3708"}[width], 0, axle, center, 4.75, "axles", 7, QUARTER)
        car.clear(range(x0, x0+2), middle, [4])
    # The integrated canopy contains its side panes; only the dashboard and rear pillar support it.
    car.clear(range(front_glass+1, end+1), range(cabin_left, cabin_left+6), [7])
    car.clear(range(front_glass+1, end+1), cabin, [6])
    car.fill(range(front_glass+1, end+1), cabin, [5], 0)
    car.clear([front_glass+1], [cabin_left+1, cabin_left+2], [4, 5, 6])
    car.fill([front_glass], range(cabin_left, cabin_left+6), [8], 0)
    car.fill([end], cabin_sides, [7, 8], paint)
    car.fill([end+1], cabin_sides, range(8, 13), paint)
    car.fill(range(end+2, end+4), cabin_sides, [8, 9], paint)
    # Reserve the actual wedge volumes instead of burying slopes in solid bricks.
    car.clear(range(4), middle, [6, 7])
    car.clear(range(2), edges, range(5, 8))
    car.fill(range(4, front_glass), middle, [8], paint)
    car.fill([0, length-1], range(width), [4], 0)

    # Side studs give the door skins and recessed intakes real attachment points.
    door_x = end-3.5
    intake_x = end+1.5
    for side in (-1, 1):
        outside, inset = (0, 1) if side == -1 else (width-1, width-2)
        facing = IDENTITY if side == -1 else HALF
        panel_rotation = (1, 0, 0, 0, 0, side, 0, -side, 0)
        for x in (end-5, end-2):
            car.clear([x], [outside], range(5, 8))
            car.place("87087", paint, x, outside, 8, "door mounts", 9, facing)
        car.place("87079", paint, door_x, center+side*(center+.9), 6.75,
                  "door skin", 18, panel_rotation)
        car.clear(range(end, end+4), [outside], range(4, 8))
        car.fill(range(end, end+4), [inset], range(4, 8), 0)
        for x in (end, end+3):
            car.clear([x], [inset], range(5, 8))
            car.place("87087", 0, x, inset, 8, "intake mounts", 9, facing)
        car.place("87079", 0, intake_x, center+side*(center-.1), 6.75,
                  "recessed side intake", 18, panel_rotation)
        car.place("3666", paint, intake_x, outside, 9, "intake bridge", 13)
        car.place("6636", paint, intake_x, outside, 10, "intake lip", 14)
        car.clear([front_glass], [outside], [6, 7])
        car.place("4070", paint, front_glass, outside, 9, "mirror mounts", 13, facing)
        car.place("24246", paint, front_glass, center+side*(center+.7), 7.75,
                  "mirror faces", 18, panel_rotation)
        car.place("3070b", paint, front_glass, outside, 10, "mirror caps", 18)

    front_rotation = (0, 1, 0, 0, 0, 1, 1, 0, 0)
    rear_rotation = (0, -1, 0, 0, 0, -1, 1, 0, 0)
    for y in (2, width-3):
        car.clear([0], [y], range(3, 6))
        car.place("87087", 0, 0, y, 6, "grille mounts", 9, QUARTER)
        car.clear([length-1], [y], range(5, 8))
        car.place("87087", 0, length-1, y, 8, "rear panel mounts", 9, BACK_QUARTER)
    for y in np.arange(2.5, width-2, 2):
        car.place("2412b", 0, -.9, y, 4.75, "front grille", 18, front_rotation)
        car.place("2412b", 0, length-.1, y, 6.75, "rear grille", 18, rear_rotation)
    for y in edges:
        car.clear([length-1], [y], range(5, 8))
        car.place("87087", 0, length-1, y, 8, "tail light mounts", 9, BACK_QUARTER)
        car.place("98138", 36, length-.1, y, 6.75, "tail lights", 18, rear_rotation)

    engine_start, engine_end = end+1, length-3
    car.clear(range(engine_start, engine_end+1), middle, [7])
    for x in range(engine_start, engine_end+1):
        for y in (2, width-3):
            car.place("3024", 72, x, y, 8, "engine details", 15)
    if rear_wing:
        car.fill(range(length-3, length-1), edges, [8], paint)

    car.pack()
    for y in np.arange(2.5, width-2, 2):
        car.place("30363", paint, 3, y, 9, "sloped bonnet", 13, QUARTER)
    car.tiles([3], middle, 10, paint, "bonnet stud finish", 14)
    for y in shoulders:
        car.place("3022", 0, .5, y, 6, "headlamp bases", 13)
        car.place("3069b", 0, 0, y, 7, "headlamp recesses", 14, QUARTER)
        car.place("3069b", 47, 1, y, 7, "headlamps", 15, QUARTER)
        car.place("15068", paint, 2.5, y, 8, "front shoulder curves", 14, QUARTER)
    car.tiles(range(4, front_glass), middle, 10, paint, "bonnet finish", 14)
    for axle in fit["axles_studs"]:
        for side in (-1, 1):
            car.place("15068", paint, axle, center+side*(width/2-1), 10, "wheel arch caps", 14,
                      IDENTITY if side == -1 else HALF)
    for y in shoulders:
        car.place("15068", paint, 4.5, y, 8, "bonnet shoulders", 14,
                  IDENTITY if y == .5 else HALF)
    occupied_shoulders = {x for axle in fit["axles_studs"] for x in (int(axle-.5), int(axle+.5))}
    occupied_shoulders |= {4, 5} | set(range(end-1, end+5))
    for x in range(4, length):
        if x not in occupied_shoulders and (not rear_wing or x < length-3 or x == length-1):
            car.tiles([x], [0, width-1], 9, paint, "shoulder finish", 14)
    car.place("65633", 47, end, center, 13, "integrated windscreen", 16, QUARTER)
    car.tiles(range(start, end+1), cabin, 14, paint, "smooth roof", 18)
    car.place("6636", paint, end+1, center, 14, "rear roof strip", 18, QUARTER)
    for y in cabin_sides:
        car.place("4286", paint, end+1, y, 13, "rear roof buttresses", 16, BACK_QUARTER)
    car.place("57783", 47, end+1, center, 13, "rear window", 16, BACK_QUARTER)
    car.tiles(range(end+4, engine_end+1), range(1, width-1), 9, 47, "engine cover", 16)
    car.tiles(range(engine_end+1, length), middle, 9, paint, "rear deck", 14)
    # Interior is visible through the native transparent windscreen.
    for y in (center-1, center+1):
        car.place("4079", 0, end-2.5, y, 7, "seats", 15, QUARTER)
    car.place("3829c01", 0, front_glass+1, center-1, 5, "steering wheel", 15, QUARTER)
    if rear_wing:
        for y in shoulders:
            car.place("3003", paint, length-2.5, y, 12, "wing pylons", 19)
        for y in range(0, width, 4):
            span = min(4, width-y)
            car.place("3020" if span == 4 else "3022", paint, length-1.5, y+(span-1)/2,
                      13, "rear wing", 20, QUARTER)
        car.tiles([length-2, length-1], range(width), 14, paint, "rear wing surface", 21)
    return car


def export(car, directory):
    lines = ["0 Car2LEGO_3D mesh-conditioned sports car", "0 Author: imxiaoxian",
             "0 // Constrained part-family fit; physical buildability unverified."]
    for step in sorted({p.step for p in car.parts}):
        for part in car.parts:
            if part.step == step:
                numbers = " ".join(f"{n:g}" for n in (*part.position, *part.rotation))
                lines.append(f"1 {part.color} {numbers} {part.part}.dat")
        lines.append("0 STEP")
    (directory / "model.ldr").write_text("\n".join(lines)+"\n", encoding="ascii")
    with (directory / "inventory.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["part", "ldraw_color", "quantity"])
        writer.writerows((part, color, count) for (part, color), count in
                        sorted(Counter((p.part, p.color) for p in car.parts).items()))
    write_json(directory / "assembly.json", {"units": "LDraw LDU", "parts": [asdict(p) for p in car.parts]})


def split_steps(car, limit):
    parts, new_step = [], 0
    for old_step in sorted({part.step for part in car.parts}):
        group = [part for part in car.parts if part.step == old_step]
        for offset in range(0, len(group), limit):
            new_step += 1
            parts.extend(replace(part, step=new_step) for part in group[offset:offset+limit])
    car.parts = parts


def convert_car(source, directory, length_studs=None, up_axis="z", yaw=0, color=None, rear_wing=True,
                vehicle_spec=None, width_studs=None, scale=None, requirements_plan=None):
    source, directory = Path(source), Path(directory)
    with stage(directory, "lego", {"mesh": source.name, "sha256": digest(source), "strategy": "car",
                                   "length_studs": length_studs, "rear_wing": rear_wing,
                                   "scale": scale, "width_studs": width_studs}) as record:
        mesh = load_mesh(source)
        specifications = None
        if vehicle_spec is not None:
            from .vehicle import load_spec, spec_record
            specifications = load_spec(vehicle_spec)
            record["vehicle_spec"] = spec_record(vehicle_spec)
        fit = fit_mesh(mesh, length_studs, up_axis, yaw, color, specifications, width_studs, scale, requirements_plan)
        car = design(fit, rear_wing)
        requirements_report = None
        if specifications is not None:
            from .requirements import assess_requirements
            plan = fit["requirements_plan"]
            split_steps(car, plan["policy"]["max_parts_per_step"])
            requirements_report = assess_requirements(plan, fit["physical_constraints"],
                                                      list(Counter(p.step for p in car.parts).values()))
            write_json(directory / "requirements.json", plan)
            write_json(directory / "requirements-report.json", requirements_report)
        export(car, directory)
        write_json(directory / "fit.json", fit)
        report = {"strategy": "car", "part_count": len(car.parts), "body_color": fit["body_color"],
                  "tyre_count": 4, "native_wheel_count": 4, "native_windscreens": 1,
                  "standard_part_scaling": False, "body_cells_exact": True,
                  "buildability": "unverified", "studio_verified": False, "physical_verified": False,
                  "appearance_accepted": False,
                  "scale_requirements_status": "draft" if requirements_report else "not_evaluated_missing_vehicle_specs",
                  "delivery_accepted": False,
                  "limitations": ["Vehicle part-family prior approximates mesh; exact coverage is not a goal.",
                                  "No native collision, clutch or physical assembly verification.",
                                  "No decals, working doors, steering or verified Ferrari details."]}
        write_json(directory / "validation.json", report)
        if specifications is not None:
            write_json(directory / "dimensions.json", fit["physical_constraints"])
        record.update(**report, outputs={name: digest(directory/name) for name in
                                       ("model.ldr", "inventory.csv", "assembly.json", "fit.json")})
        if specifications is not None:
            record["outputs"]["dimensions.json"] = digest(directory / "dimensions.json")
            record["outputs"].update({name: digest(directory / name) for name in
                                      ("requirements.json", "requirements-report.json")})
        from .preview import render
        render(orient(mesh, up_axis, yaw)[0], directory / "mesh-preview.png")
    return directory / "model.ldr"
