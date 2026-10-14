"""Stud-aligned assembly recipes; AI chooses appearance, code owns placement."""

IDENTITY = "1 0 0 0 1 0 0 0 1"
TURN = "0 0 1 0 1 0 -1 0 0"
REVERSE = "-1 0 0 0 1 0 0 0 -1"
FRONT_FACE = "1 0 0 0 0 -1 0 1 0"
REAR_FACE = "1 0 0 0 0 1 0 -1 0"


def build_assembly(plan: dict) -> dict[str, list[dict]]:
    sections = {name: [] for name in ("chassis", "front", "body", "rear", "wheels")}
    body = plan.get("body_color_id", 4)
    trim = plan.get("accent_color_id", 0)
    profile = plan.get("assembly_profile", "low_coupe")
    roof_height = 104 if profile == "low_coupe" else 144

    def add(section, part, color, x, height, z, rotation=IDENTITY, label="", mirror=True):
        sections[section].append(dict(part_num=part, color_id=color, x=x, y=height, z=z,
                                      rotation=rotation, quantity=1, semantic_label=label or section,
                                      mirror=mirror, section=section))

    # The central spine is two studs wide. Open wheel wells leave tyre clearance.
    for z in (40, 120, 200, 280):
        add("chassis", "3020.dat", 0, 0, 32, z, TURN)
    for z in (80, 160, 240):
        add("chassis", "3020.dat", 0, 0, 24, z, TURN, "spine_bridge")
    for z in (60, 260):
        add("chassis", "3023.dat", 0, 10, 40, z, TURN)
    for z in (60, 260):
        add("chassis", "4600.dat", 0, 40, 40, z, label="axle_mount")
    for z in (10, 110, 210, 310):
        add("chassis", "3023.dat", 0, 60, 32, z)
        add("chassis", "3710.dat", 0, 40, 40, z)
    for z in (140, 180):
        add("chassis", "3022.dat", 0, 60, 32, z)
        add("chassis", "3020.dat", 0, 40, 40, z)
    # Side sills connect the cabin to the lower chassis, without blocking tyres.
    for z in (140, 180):
        for height in (48, 56, 64):
            add("body", "3023.dat", trim if height == 64 else body, 70, height, z, TURN,
                "body_seam" if height == 64 else "side_panel")
    for z in (10, 110, 210, 310):
        add("front" if z >= 210 else "body", "3005.dat", trim if z == 110 else body, 70, 64, z, label="side_intake" if z == 110 else "fender_support")
    for z in (60, 260):
        add("front" if z == 260 else "body", "3666.dat", body, 70, 72, z, TURN, "fender_bridge")
    add("body", "15068.dat", body, 60, 72, 60, label="rear_haunch")
    add("body", "11477.dat", body, 70, 72, 100, label="rear_haunch")

    # Front hood slopes are oriented noseward. Origins of slopes are at their high studs.
    for x in (20,):
        add("front", "30363.dat", body, x, 80, 250, REVERSE, "hood")
    add("front", "3020.dat", 0, 0, 48, 300, label="nose_support")
    add("front", "3020.dat", body, 0, 56, 300, label="nose_support")
    add("front", "3023.dat", 0, 10, 24, 320, TURN, "intake_support")
    add("front", "3020.dat", 0, 40, 32, 340, label="front_lip")
    for x in (10, 30):
        add("front", "4070.dat", 0, x, 56, 330, REVERSE, "intake_mount")
    add("front", "2412b.dat", 0, 20, 46, 344, FRONT_FACE, "grille")
    add("front", "3004.dat", body, 60, 56, 330, label="front_fascia")
    add("front", "2431.dat", body, 40, 64, 330, label="front_fascia")
    for z in (250, 270):
        add("front", "3005.dat", body, 50, 64, z, label="hood_shoulder")
    add("front", "3004.dat", body, 50, 64, 300, TURN, "hood_shoulder")
    for z in (250, 270, 290):
        add("front", "3024.dat", body, 50, 72, z, label="hood_shoulder")
    add("front", "3024.dat", body, 50, 72, 310, label="lamp_support")
    for z in (250, 270, 290):
        add("front", "3069b.dat", body, 60, 80, z, label="headlamp_cover")
    add("front", "3069b.dat", 15, 60, 80, 310, label="headlight")

    # Cabin: one centered six-wide windscreen, never mirrored into a second screen.
    for z in (140, 180, 220):
        add("body", "3020.dat", body, 0, 48, z, label="cabin_support")
        add("body", "3020.dat", body, 0, 56, z, label="cabin_floor")
        for height in (48, 56):
            add("body", "3023.dat", body, 50, height, z, TURN, "cabin_shoulder")
    for z in (140, 180):
        add("body", "3023.dat", trim, 50, 64, z, TURN, "body_seam")
        add("body", "3004.dat", 47, 50, 88, z, TURN, "side_glass")
        for height in range(96, roof_height - 8, 8):
            add("body", "3023.dat", body, 50, height, z, TURN, "cabin_pillar")
    add("body", "4176.dat", 47, 0, roof_height, 210, REVERSE, "windshield")
    add("body", "4176.dat", 47, 0, roof_height, 110, IDENTITY, "rear_glass")
    for z in (140, 180):
        add("body", "3021.dat", body, 30, roof_height - 8, z, label="roof_base")
        for x in (0, 40):
            add("body", "3068b.dat", body, x, roof_height, z, label="roof")

    for z in (20, 60, 100):
        if z != 60:
            add("rear", "3020.dat", body, 0, 48, z, TURN if z == 20 else IDENTITY, "engine_support")
        add("rear", "3020.dat", body, 0, 56, z, label="engine_support")
        if z != 100:
            add("rear", "3020.dat", body, 0, 64, z, label="engine_support")
    add("rear", "3020.dat", 47, 0, 72, 60, label="engine_cover")
    add("rear", "2412b.dat", trim, 20, 80, 50, label="engine_vent")
    add("rear", "2412b.dat", trim, 20, 80, 70, label="engine_vent")
    for z in (20, 60):
        if z == 20:
            add("rear", "3020.dat", body, 0, 72, z, label="rear_deck")
    add("rear", "3020.dat", trim, 40, 80, 20, label="rear_fascia")
    add("rear", "3710.dat", trim, 40, 56, -10, label="rear_fascia_base")
    for x in (10, 30, 50):
        add("rear", "4070.dat", trim, x, 80, -10, label="rear_fascia_mount")
        add("rear", "3070b.dat", trim, x, 88, -10, label="rear_fascia_cap")
    add("rear", "2412b.dat", trim, 0, 70, -24, REAR_FACE, "rear_grille")
    for x in (30, 50):
        add("rear", "6141.dat", 36 if x == 30 else 46, x, 70, -24, REAR_FACE, "taillight")
    if plan.get("rear_wing", False):
        add("rear", "3005.dat", body, 70, 104, 30, label="wing_support")
        add("rear", "3020.dat", body, 40, 112, 40, label="rear_wing")
        add("rear", "87079.dat", body, 40, 120, 40, label="rear_wing")
    for z in (60, 260):
        # Both parts' native axis is Z. TURN rotates that axis onto the lateral X axis.
        add("wheels", "6014.dat", 71, 74, 35, z, TURN, "rim")
        add("wheels", "6015.dat", 0, 74, 35, z, TURN, "tyre")
    return sections
