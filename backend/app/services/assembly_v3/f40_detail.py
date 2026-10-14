"""F40 surface recipe: native slopes, mudguards, canopy and recessed details.

Each piece retains its native dimensions. Every landmark is derived from the
solved stud grid, so one module set serves 1:38, 1:24, 1:16 and 1:12. The
derivation is anchored on the 1:24 grid this recipe was designed against
(length 460, width 200, roof 120, wheel radius 30), where it reproduces the
tuned constants exactly and therefore leaves that scale unchanged.

This is a visual/structural draft; opening and steering mechanisms are not
inferred from a rendered silhouette.
"""
from collections import defaultdict
import math

import networkx as nx

from .f40 import cover, RIGHT_WHEEL
from .recipes import TURN, REVERSE, REAR_FACE, solve_grid, PROFILES
from .scene import AssemblyScene, PartInstance, Module, Joint, Transform, BuildStep, IDENTITY
from .specifications import F40_SPEC, target_dimensions, CAPABILITIES
from .requirements import requirements_for_scale

LEFT_PANEL = (0., 1., 0., 0., 0., 1., 1., 0., 0.)
RIGHT_PANEL = (0., -1., 0., 0., 0., 1., -1., 0., 0.)
TILES = {"3020.dat": "87079.dat", "3021.dat": "26603.dat", "3022.dat": "3068b.dat",
         "3023.dat": "3069b.dat", "3024.dat": "3070b.dat"}

REFERENCE = (460.0, 100.0, 120.0, 30.0)   # length, half width, roof, wheel radius
RECIPE = "f40-surface-5"


def _snap(value, unit):
    return round(value / unit) * unit


def landmarks(length, width, roof, wheelbase, radius, tyre_half):
    """Derive every landmark from the solved grid.

    Longitudinal values are scaled from the reference length and snapped in the
    same unit as the reference value, so a landmark that sat on the stud lattice
    at 1:24 stays on it, and one deliberately placed at a half cell keeps its
    half-cell offset. Heights are offsets from the plate floor and the deck. X is
    a fraction of the half width: the bodywork that sets the measured width sits
    just outside the structural body, which is what puts the width inside the
    tolerance gate at every scale.
    """
    half = width / 2.0
    ratio = length / REFERENCE[0]

    def z_at(reference):
        unit = 20 if reference % 20 == 0 else 10
        return int(_snap(reference * ratio, unit))

    floor = int(max(8, _snap(radius - 14, 8)))
    # The bearing hangs off the plate floor: its attachment holes sit 14 LDU
    # below the axle and its upper studs enter the arch above, so the axle has to
    # stand 14 LDU over a plate surface or the holes meet nothing and the wheel
    # floats free of the chassis with its arch. Plate surfaces are the floor plus
    # whole plates, so the axis is the first value at or above the tyre radius
    # that shares the floor's lattice - the smallest one that both holds the
    # tread off the ground plane and lands the bearing on its mount. On 1:24,
    # 1:16 and 1:12 the radius already sits on that lattice; the small 1:38 tyre
    # does not, and the three LDU it was out is what detached every wheel, axle
    # and curved arch at that scale.
    base = max(radius, floor + 14.0)
    axis = base + (floor + 14 - base) % 8
    # The deck has to clear the tyre, or the mudguard is cut through by it.
    deck = int(max(_snap(roof * .5333, 8), _snap(axis + radius, 8)))
    front, rear = (length - wheelbase) / 2.0, (length + wheelbase) / 2.0
    # Half-width stations are placed against the stud columns, not as a fraction
    # of the half width. Columns run at 20 LDU intervals and the outermost one is
    # at half - 10 whatever the solved width, so a station is an offset from that
    # column. A piece an odd number of studs wide centres on a column; one an even
    # number wide centres midway between two, which is where its own studs land on
    # the pair either side. At the reference half width of 100 this reproduces the
    # tuned stations exactly: rails 40, bearing 50, arch 60, pillar 70, nose 80
    # and side-stud mounts 90. A fraction of the half width does not: at 1:38 it
    # yields 12/24/36/48, and every part placed on one of those floats.
    outer = half - 10
    phase = int((half - 10) % 20)

    def x_at(reference, even=False):
        offset = 10 if even else 0
        target = min(reference * half / 100.0, outer)
        return int(round((target - phase - offset) / 20) * 20 + phase + offset)

    # The door panel hangs four LDU clear of the structural body and is meant to
    # be the widest point of the car, so it is what the width gate measures.
    # Every other piece is a fixed size in LDU, and on a narrow grid one of them
    # can reach past the panel and measure the width by itself. A piece that
    # would is stepped inboard a whole column at a time, which keeps it on the
    # lattice. At the reference half width of 100 nothing overhangs the panel
    # and the step is never taken.
    panel = half + 4

    def fit(station, over):
        while station > 0 and station + over > panel + .5:
            station -= 20
        return station

    bearing = x_at(50)
    arch = x_at(60, even=True)
    rail_lo = x_at(40, even=True)
    bridge = x_at(40, even=True)
    seat = x_at(30)
    cross = x_at(20, even=True)
    pillar = x_at(70)
    nose = x_at(80, even=True)
    snot = x_at(90)
    haunch_in = x_at(70)
    # A six-stud body has three columns a side where the reference has five, so
    # the two rear haunch slopes round onto the same one. build_scene collapses
    # the pair rather than placing the same slope twice in the same volume.
    haunch_out = max(x_at(90), min(haunch_in + 20, outer))
    # The mudguard spans 48.86 LDU across the car, near half the body at 1:38,
    # and the recessed headlight is a two-stud tile on its mount. Each reaches
    # past its own station, so each is fitted against the panel separately. The
    # arch station itself is not moved: the arch support rails are the strip
    # between rail_lo and arch, and stepping it in would empty them.
    mudguard = fit(arch, 28.86)
    lamp = fit(haunch_in, 20)
    # The axle station and the bearing's station are two different things. The
    # axle has to reach the wheel centre, so it stays where the shaft ladder
    # expects it and its span is chosen against that station. The bearing brick
    # is a plate lying alongside the tyre - it is only 17 LDU across the car
    # once turned, but it is mounted by a hole on its underside, so it has to
    # stand on a chassis plate, and that plate has to survive the tyre
    # exclusion. On a six-stud car the tyre reaches inboard past the axle
    # station's cell, so the brick steps inboard a whole column to the strip
    # the tyre leaves open; at the reference and both large scales it already
    # clears the tyre there and never moves.
    bearing_mount = bearing
    while bearing_mount > 0 and bearing_mount + 8.5 > half - 2*tyre_half + .5:
        bearing_mount -= 20
    # The bonnet wedge runs 70 LDU from its origin to its tip. On a short grid
    # the longitudinal snap puts the origin nearer the front plane than that and
    # the tip overhangs the chassis on its own, so the bonnet starts behind it.
    wedge_z = max(z_at(90), 70)
    bonnet_z0 = max(z_at(100), wedge_z + 10)
    # The engine bay is the gap the rear arch and the rear wheel leave between
    # them, and the arch is what closes it: the molded arch is asymmetric along
    # its axis, so its inboard face lands a fixed offset inside its own station.
    # A bank is placed only when it stands inboard of that face. At the
    # reference half width the arch keeps its station, the two-stud bank at the
    # cross-member station clears the face by a plate, and the tuned stack and
    # its ribs are reproduced exactly. Where the arch has been fitted inboard to
    # hold the width gate the bay is gone, and the banks are left out rather
    # than laid inside the mudguard - that scale carries no engine cover in its
    # capability set, so nothing that shows is lost.
    engine_in = mudguard - 18.5
    engine_fits = cross + 20 <= engine_in + .5
    bank_over, bank = (20, cross) if engine_fits else (None, None)
    bank_part, rib_part = "3022.dat", "2412b.dat"
    engine_layers = (floor+16, floor+24, floor+32) if engine_fits else ()
    rib_h = floor+40 if engine_fits else None
    # Parts that bridge the width are chosen from what the half width leaves. A
    # 2x8 plate is 160 LDU long and a 4L axle reaches 40 LDU past its bearing;
    # on a six-stud car either one would set the measured width by itself.
    beam = next((number for studs, number in ((8, "3034.dat"), (6, "3795.dat"), (4, "3020.dat"), (2, "3022.dat"))
                 if studs * 10 <= half + .5), "3022.dat")
    shaft = next((number for span, number in ((80, "3705.dat"), (60, "4519.dat"), (40, "32062.dat"))
                  if bearing + span / 2 <= half + .5 and span / 2 <= bearing + .5), "32062.dat")
    return {
        "length": length, "width": width, "half": half, "roof": roof,
        "floor": floor, "axis": axis, "deck": deck,
        "radius": radius, "tyre_half": tyre_half, "front": front, "rear": rear,
        # Longitudinal landmarks, in reference LDU.
        "cabin_front": z_at(160), "cabin_rear": z_at(280), "mid": z_at(220),
        "nose_len": z_at(40), "beam_z0": z_at(20), "beam_z1": z_at(60),
        "bonnet_z0": bonnet_z0, "engine_z": z_at(320), "engine_z2": z_at(400),
        "door_z0": z_at(210), "door_z1": z_at(270), "panel_z": z_at(240),
        "intake_z": z_at(300), "haunch_z": z_at(410), "bridge_z0": z_at(340),
        "bridge_z1": z_at(380), "fender_z0": z_at(30), "fender_z1": z_at(170),
        "wedge_z": wedge_z,
        "crossmembers": tuple(z_at(z) for z in (40, 180, 260, 300, 420, 440)),
        # Parts that span the model, chosen from the half width they have to fit
        # in. A single fixed number for every scale is what let the nose beam and
        # the wheel axle measure the width by themselves: on a six-stud car an
        # eight-stud plate reaches 80 LDU and a 4L axle 70, against a 64.8 half.
        "beam": beam, "shaft": shaft,
        # Half-width landmarks, on the stud lattice. At the reference half width
        # of 100 these are the tuned values: rails 40, bearing 50, arch 60,
        # pillar 70, nose 80 and side-stud mounts 90. The door panel hangs four
        # LDU clear of the body, which is 104 at the reference half width and
        # keeps that same clearance where the body is narrower or wider.
        "bearing": bearing, "arch": arch, "rail_lo": rail_lo,
        "bridge": bridge, "seat": seat, "cross": cross,
        "pillar": pillar, "nose": nose, "snot": snot,
        "haunch_in": haunch_in, "haunch_out": haunch_out, "panel": panel,
        # The mudguard and the recessed lamp are the two pieces whose own width
        # is large enough to measure the car, so they mount on their fitted
        # stations rather than on the station their landmark came from.
        "mudguard": mudguard, "lamp": lamp,
        # Where the bearing brick stands, which is not where the axle sits. The
        # brick is held by the tube on its underside, so it needs a chassis plate
        # directly beneath it, and on the smallest grid the tyre reaches inboard
        # past the axle station's cell and the brick has to step in to a column
        # the tyre leaves open. The axle keeps the station the shaft ladder sized
        # its span against, so the shaft still reaches the wheel.
        "bearing_mount": bearing_mount,
        # The engine ladder: where a bank stands and which piece it is, which
        # layers the stack keeps under the arch, and the slot the intake ribs
        # take above them.
        "bank": bank, "bank_part": bank_part, "rib_part": rib_part,
        "engine_layers": engine_layers, "rib_h": rib_h,
    }


def build_scene(design_id, scale, intent=None, vehicle=None, spec=None, requirements=None):
    intent = intent or {}
    spec = spec or dict(F40_SPEC)
    target = target_dimensions(spec, scale)
    policy = requirements or requirements_for_scale(scale)
    grid = solve_grid(target, scale, policy)
    length, width, roof, wb = (grid[k] for k in ("length", "width", "height", "wheelbase"))
    rim, tyre, radius, tyre_half = PROFILES[scale]
    L = landmarks(length, width, roof, wb, radius, tyre_half)
    half, floor, deck, axis, roof = L["half"], L["floor"], L["deck"], L["axis"], L["roof"]
    front, rear = L["front"], L["rear"]
    cabin_front, cabin_rear = L["cabin_front"], L["cabin_rear"]
    red, black = int(intent.get("body_color_id", 4)), int(intent.get("accent_color_id", 0))
    parts, modules, joints = [], [], []
    layers = {}
    dependencies = {
        "chassis": [], "wheel_mounts": ["chassis"], "cockpit": ["chassis"], "engine": ["chassis"],
        "body_frame": ["wheel_mounts", "cockpit", "engine"], "front_hood": ["body_frame"],
        "engine_cover": ["body_frame"], "doors": ["body_frame"],
        "details": ["front_hood", "engine_cover", "doors"],
    }

    def add(module, number, color, x, h, z, rotation=IDENTITY, feature=""):
        part = PartInstance(id=f"{module}_{len(parts):05d}", part_num=number, color_id=color,
            module=module, transform=Transform(position=(float(x), float(-h), float(z)), rotation=rotation), feature=feature)
        parts.append(part)
        return part

    def plate_layer(module, h, cells, color, tiles=False, feature=""):
        # Several modules share rails and fascia supports. Occupancy belongs to
        # the complete car: never place duplicate plates in overlapping strips.
        for cell in cells:
            layers[h, cell] = (module, color, tiles, feature)

    def emit_layer(module, h, cells, color, tiles=False, feature=""):
        for x, z, w, d, number in cover(cells, (h//8)%2 == 0):
            rotation = TURN if (number == "3020.dat" and w == 2) or (number == "3021.dat" and w == 2) or (number == "3023.dat" and w == 1) else IDENTITY
            add(module, TILES[number] if tiles else number, color, (x+w/2)*20-width/2, h,
                (z+d/2)*20, rotation, feature)

    def cells(x0, x1, z0, z1):
        # A cell belongs to a strip when its centre falls in it, not when its
        # left edge does. Selecting by left edge rounded the two sides of a
        # mirror pair differently as soon as the half width stopped being a
        # whole number of studs: on the six-stud grid the left arch rail strip
        # -36..-24 came out empty and the right one partially filled, which is
        # what left the arches and sills floating. Cell centres are symmetric
        # about X = 0 whenever the solved width is a multiple of 40, so this
        # also makes every strip its own mirror image by construction.
        return {(x, z) for x in range(math.ceil((x0 + half)/20 - .5), math.ceil((x1 + half)/20 - .5))
                for z in range(math.ceil(z0/20 - .5), math.ceil(z1/20 - .5))}

    # Two staggered, load-bearing layers. Leave wheel volumes and bearing feet
    # open before adding bodywork; don't hide shafts inside solid voxel plates.
    base = cells(-half, half, 0, length)
    for h in (floor, floor+8):
        layer = set()
        for xi, zi in base:
            x, z = (xi+.5)*20-half, (zi+.5)*20
            # A wheel owns its volume. The tyre is seated so its tread faces along
            # X, which makes its world X half extent its tyre_half and puts its
            # inner face twice that in from the half width. A cell belongs to the
            # wheel when its footprint crosses that face, not when its centre
            # passes the arch station: on a six-stud chassis the cell just inboard
            # of the tyre has its centre at half the arch station and was left in
            # place, which is what put the chassis plate through the rear tyre.
            if abs(x) + 10 > half - 2*tyre_half and min(abs(z-front), abs(z-rear)) < 40:
                continue
            if h > floor and abs(abs(x)-L["bearing"]) < 1 and min(abs(z-front), abs(z-rear)) < 21:
                continue
            layer.add((xi, zi))
        plate_layer("chassis", h, layer, black, feature="staggered_chassis")

    for axle_z, axle_name in ((front, "front"), (rear, "rear")):
        for side, label in ((-1, "left"), (1, "right")):
            name = f"wheel_{label}_{axle_name}"
            dependencies[name] = ["wheel_mounts"]
            centre = side*(half-tyre_half)
            rotation = TURN if side < 0 else RIGHT_WHEEL
            add(name, rim, 71, centre-side*6, axis, axle_z, rotation, "rim")
            add(name, tyre, 0, centre, axis, axle_z, rotation, "tyre")
            shaft = add(name, L["shaft"], black, side*L["bearing"], axis, axle_z, IDENTITY, "axle")
            # The bearing brick carries the axle but is not on the axle's station:
            # it mounts by the tube on its underside, and the tyre reaches inboard
            # past the axle station's cell on the smallest grid. It stands on the
            # strip the tyre leaves open, which is where the axle passes through
            # its hole.
            bearing = add("wheel_mounts", "3700.dat", black, side*L["bearing_mount"], axis+10, axle_z, TURN, "axle_bearing")
            joints.append(Joint(id=name+"_spin", parent="wheel_mounts", child=name,
                pivot=(centre, -axis, axle_z), axis=(1., 0., 0.), limits=(0., 360.), capability="rolling_wheels",
                implemented=True, mounting_parts=(bearing.id, shaft.id)))
            # The single molded arch mounts on the inner strip, with a clear
            # tire cavity. Opposite sides use rotations, never reflection.
            add("body_frame", "98282.dat", red, side*L["mudguard"], deck, axle_z,
                TURN if side < 0 else RIGHT_WHEEL, "curved_wheel_arch")
    dependencies["body_frame"] += [name for name in dependencies if name.startswith("wheel_") and name != "wheel_mounts"]

    # Inner rails support the arch attachment studs and avoid the tire.
    rails = cells(-L["arch"], -L["rail_lo"], 0, length) | cells(L["rail_lo"], L["arch"], 0, length)
    for h in (floor+16, floor+24):
        rail_layer = {(x, z) for x, z in rails if min(abs((z+.5)*20-front), abs((z+.5)*20-rear)) >= 21}
        plate_layer("body_frame", h, rail_layer, red, feature="arch_support_rail")
    # Nose, sills and rear fascia stay low. Large empty volumes are preserved.
    sill = (cells(-half, -L["nose"], cabin_front-20, cabin_rear+40)
            | cells(L["nose"], half, cabin_front-20, cabin_rear+40))
    ends = cells(-half, half, 0, 20) | cells(-half, half, length-20, length)
    lamp_feet = cells(-L["nose"], -L["arch"], 0, 20) | cells(L["arch"], L["nose"], 0, 20)
    for h in (floor+16, floor+24):
        plate_layer("body_frame", h, (sill | ends)-lamp_feet, black if h == floor+16 else red, feature="body_seam")
    for cell in lamp_feet:
        layers.pop((floor+8, cell), None)
    front_bed = cells(-L["bridge"], L["bridge"], L["beam_z0"], cabin_front)
    for h in (floor+16, floor+24):
        bed = {(x, z) for x, z in front_bed if min(abs((z+.5)*20-front), abs((z+.5)*20-rear)) >= 21}
        plate_layer("body_frame", h, bed, red, feature="hood_support")

    # Low, continuous 18 degree bonnet. Smooth tiles cover the remaining rear
    # section, rather than a staircase of stacked 1x1 plates.
    for x in (-L["cross"], L["cross"]):
        add("front_hood", "30363.dat", red, x, deck, L["wedge_z"], feature="wedge_bonnet")
    for h in (floor+32, floor+40, deck, deck+8):
        plate_layer("front_hood", h, cells(-L["bridge"], L["bridge"], L["bonnet_z0"], cabin_front), red,
                    tiles=h == deck+8, feature="smooth_bonnet")
    # Fender shoulders over the clear wheel-arch studs.
    for side in (-1, 1):
        add("front_hood", "15068.dat", red, side*L["arch"], deck, front,
            TURN if side < 0 else RIGHT_WHEEL, "front_fender_cap")
        for z in (L["fender_z0"], L["fender_z1"]):
            for h in (floor+16, floor+24, floor+32, floor+40):
                plate_layer("body_frame", h, cells(side*L["nose"]-20, side*L["nose"]+20, z-10, z+10), red, feature="fender_end")
            add("front_hood", "15068.dat", red, side*L["nose"], floor+40, z+10, feature="curved_nose_corner")

    # Native six-stud canopy contains continuous sloped glass and side panes.
    # Its bottom sockets sit on the dashboard below the roof line.
    for h in range(floor+16, deck+17, 8):
        plate_layer("cockpit", h, cells(-L["bridge"], L["bridge"], cabin_front, cabin_front+20),
                    black if h >= deck else red, feature="dashboard_support")
    add("cockpit", "65633.dat", 47, 0, roof-8, cabin_rear-10, feature="raked_windshield")
    add("cockpit", "87079.dat", red, 0, roof, cabin_rear-20, feature="smooth_roof")
    for side in (-1, 1):
        for h in range(floor+16, roof-7, 8):
            plate_layer("body_frame", h, cells(side*L["pillar"]-10, side*L["pillar"]+10, cabin_rear-20, cabin_rear), red, feature="rear_cabin_pillar")
        add("cockpit", "3068b.dat", red, side*L["arch"], roof, cabin_rear-20, feature="roof_border")
        add("cockpit", "3794b.dat", red, side*L["seat"], floor+16, L["mid"], TURN, "seat_mount")
        add("cockpit", "4079.dat", red, side*L["seat"], floor+24, L["mid"], REVERSE, "bucket_seat")
    add("cockpit", "87580.dat", black, 0, floor+16, L["mid"], feature="console_mount")
    add("cockpit", "3069b.dat", black, 0, floor+24, L["mid"], TURN, "centre_console")

    # Doors use side-facing stud mounts and tiled panels. The intake is an
    # actual recess behind each door; it isn't a decal or a generated texture.
    for side in (-1, 1):
        for z in (L["door_z0"], L["door_z1"]):
            add("doors", "4070.dat", red, side*L["snot"], deck, z, TURN if side < 0 else RIGHT_WHEEL, "door_snot_mount")
        add("doors", "87079.dat", red, side*L["panel"], deck, L["panel_z"],
            LEFT_PANEL if side < 0 else RIGHT_PANEL, "smooth_door_panel")
        for h in (floor+24, floor+32, floor+40, deck):
            plate_layer("body_frame", h, cells(side*L["pillar"]-10, side*L["pillar"]+10, cabin_rear, cabin_rear+40), black, feature="recessed_side_intake")
        add("body_frame", "15068.dat", red, side*L["nose"], deck, L["intake_z"], feature="intake_upper_lip")

    # V8 appearance is visible through the central clear engine-cover panels.
    # Both banks are the same piece on the same station either side of the
    # centre, and the ribs sit above the stack. Where the rear arch has been
    # fitted inboard to hold the width gate there is no bay left to stand the
    # banks in, and the ladder yields nothing rather than burying them in the
    # mudguard; that scale declares no engine_cover capability, so no verified
    # feature is lost.
    if L["bank"] is not None:
        for x in (-L["bank"], L["bank"]):
            for z in (L["engine_z"], L["engine_z2"]):
                for h in L["engine_layers"]:
                    add("engine", L["bank_part"], 72, x, h, z, feature="v8_engine_block")
                if L["rib_h"] is not None:
                    add("engine", L["rib_part"], 71, x, L["rib_h"], z+10, feature="v8_intake_ribs")
    rear_rails = (cells(-L["arch"], -L["rail_lo"], cabin_rear, cabin_rear+40)
                  | cells(L["rail_lo"], L["arch"], cabin_rear, cabin_rear+40)
                  | cells(-L["arch"], -L["rail_lo"], L["engine_z2"], L["engine_z2"]+40)
                  | cells(L["rail_lo"], L["arch"], L["engine_z2"], L["engine_z2"]+40))
    for h in (floor+32, floor+40, deck, deck+8):
        plate_layer("body_frame", h, rear_rails, red, feature="engine_bay_rail")
    # The deck is set by the tyre radius, so on a short model the two plates of
    # cover this stack wants to stand on would rise past the roof and measure
    # the car. The cover is the top surface of the rear deck, not an appendage
    # above it: it is capped at the roof line, and the vents hang off whatever
    # cover height that leaves. At the reference scale the stack clears the roof
    # on its own and neither cap bites.
    cover_h = int(min(deck + 24, roof))
    vent_h = int(min(deck + 16, cover_h - 8))
    for z in (L["engine_z"], L["engine_z2"]):
        add("engine_cover", "3032.dat", 47, 0, vent_h, z, feature="transparent_engine_cover")
    plate_layer("engine_cover", cover_h, cells(-L["arch"], L["arch"], cabin_rear, length-20), 47,
                tiles=True, feature="transparent_engine_cover")
    for side in (-1, 1):
        # 3x1 slopes have native collision definitions; the 3x2 library entry
        # has none. Use two independent pieces instead of skipping its checks.
        for x in (side*L["haunch_in"], side*L["haunch_out"]):
            add("engine_cover", "50950.dat", red, x, cover_h, L["haunch_z"], feature="rear_haunch_curve")
        for h in range(floor+16, deck+1, 8):
            plate_layer("body_frame", h, cells(side*L["nose"]-20, side*L["nose"]+20, L["haunch_z"]-10, L["haunch_z"]+10), red, feature="rear_haunch_support")
        plate_layer("body_frame", deck+8, cells(side*L["arch"]-20, side*L["arch"]+20, L["bridge_z0"], L["bridge_z1"]), red, feature="rear_fender_bridge")

    # Tail and wing carry real structural underlayers; top tiles conceal studs.
    for h in range(floor+32, deck+17, 8):
        tail = cells(-half, half, length-20, length)
        if h <= deck:
            tail -= cells(-half, -L["arch"], length-20, length) | cells(L["arch"], half, length-20, length)
            tail -= cells(-L["cross"], L["cross"], length-20, length)
        plate_layer("body_frame", h, tail, red, feature="rear_fascia")
    for x in (-10, 10):
        add("details", "4070.dat", black, x, deck, length-10, REVERSE, "rear_vent_mount")
    add("details", "2412b.dat", black, 0, deck-10, length+4, REAR_FACE, "rear_louvres")
    for side in (-1, 1):
        # Three plate heights make the upright at the reference scale. On a
        # short model the roof line clamps them together, and stacking one
        # footprint on the same plate three times is a collision, not a
        # structure, so the clamped set is deduplicated.
        for h in sorted({min(deck+offset, roof-8) for offset in (24, 32, 40)}):
            plate_layer("details", h,
                        cells(side*L["pillar"]-10, side*L["pillar"]+10, length-20, length), red, feature="wing_upright")
    add("details", L["beam"], red, 0, roof-8, length-20, feature="wing_crossbeam")
    plate_layer("details", roof, cells(-half, half, length-40, length), red, tiles=True, feature="full_width_rear_wing")
    for side in (-1, 1):
        # Front lamps are recessed below the bonnet, with a separate lid. They
        # sit on their fitted station: a two-stud tile on the body edge is the
        # widest piece at the nose and would otherwise measure the car.
        add("details", "4070.dat", black, side*L["lamp"], floor+24, 10, IDENTITY, "front_light_mount")
        add("details", "3069b.dat", 47, side*L["lamp"], floor+32, 10, feature="recessed_headlight")
        for x in (side*L["haunch_in"], side*L["haunch_out"]):
            add("details", "4070.dat", black, x, deck, length-10, REVERSE, "taillight_mount")
            add("details", "98138.dat", 36, x, deck-10, length+4, REAR_FACE, "round_taillight")

    # Broad native plates bridge the longitudinal floor seams. Sharing cells
    # without overlapping studs does not connect two rigid strips.
    for z in L["crossmembers"]:
        plate_layer("chassis", floor+16, cells(-half, half, z-20, z+20), black, feature="load_bearing_crossmember")
    # A single long beam crosses both floor seams; repeated short strips left
    # the right-hand headlight/fender island detached despite touching faces.
    for cell in cells(-half, half, L["beam_z0"], L["beam_z1"]):
        layers.pop((floor+24, cell), None)
    add("body_frame", L["beam"], red, 0, floor+24, L["nose_len"], feature="nose_crossmember")
    for side in (-1, 1):
        add("body_frame", "3023.dat", red, side*L["snot"], floor+24, L["nose_len"], TURN, "nose_crossmember")
        for h in (floor+16, floor+24):
            for cell in cells(side*L["bearing"]-10, side*L["bearing"]+10, L["mid"]-20, L["mid"]+20):
                layers.pop((h, cell), None)  # the wider bucket-seat base owns this volume
    for z in (L["engine_z"], L["engine_z2"]):
        for cell in cells(-L["bridge"], L["bridge"], z-20, z+20):
            layers.pop((floor+16, cell), None)  # occupied by the engine's native plates

    groups_by_layer = defaultdict(set)
    for (h, cell), definition in layers.items():
        groups_by_layer[h, *definition].add(cell)
    for (h, module, color, tiles, feature), footprint in sorted(groups_by_layer.items()):
        emit_layer(module, h, footprint, color, tiles, feature)

    # Opening mounts require a separate validated mechanism recipe.
    for name, z in (("front_hood", cabin_front-20), ("engine_cover", cabin_rear+20)):
        joints.append(Joint(id=name, parent="body_frame", child=name, pivot=(0., -deck, z),
                            axis=(1., 0., 0.), limits=(0., 65.), capability=name))
    for name, deps in dependencies.items():
        modules.append(Module(id=name, depends_on=deps, structural=name == "chassis", recipe_version=RECIPE))
    graph = nx.DiGraph()
    graph.add_nodes_from(dependencies)
    graph.add_edges_from((dep, name) for name, deps in dependencies.items() for dep in deps)
    groups = defaultdict(list)
    for part in parts:
        groups[part.module].append(part)
    steps = []
    for name in nx.topological_sort(graph):
        group = sorted(groups[name], key=lambda p: (-p.transform.position[1], p.transform.position[2], p.transform.position[0]))
        for offset in range(0, len(group), policy["max_step_parts"]):
            steps.append(BuildStep(index=len(steps)+1, module=name, parts=[p.id for p in group[offset:offset+policy["max_step_parts"]]]))
    return AssemblyScene(design_id=design_id, vehicle=vehicle or dict(make="Ferrari", model="F40", year=1990),
        scale=scale, specifications=spec, target_ldu=target, parts=parts, modules=modules, joints=joints, steps=steps,
        planning={"solver": "OR-Tools CP-SAT", "grid": grid, "required_capabilities": [m["id"] for m in policy["mechanisms"]], "scale_requirements": policy,
                  "wheel_centres_z": [front, rear], "recipe": RECIPE, "recipe_verified": False,
                  "intent": intent, "appearance_target": "continuous wedge nose, curved arches, raked glass, side recess and tiled wing"})
