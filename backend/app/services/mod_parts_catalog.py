"""Real-world car modification parts catalog mapped to LEGO parts.

Each mod entry represents an actual car modification type (from real car culture:
JDM, Euro, American muscle, off-road, motorsport) with specific LEGO part
numbers and placement instructions for Claude to execute.

Categories follow real aftermarket part taxonomy.
"""

from dataclasses import dataclass, field


@dataclass
class ModPart:
    """A real-world car modification part with LEGO implementation."""
    id: str                     # Unique mod ID
    name: str                   # Display name
    category: str               # Category: aero / wheels / exhaust / body / interior / lighting / performance
    real_world_ref: str         # Real-world equivalent (e.g., "APR GTC-300 Wing")
    description: str            # What this mod does to the car
    difficulty: str             # easy / medium / hard
    estimated_parts: int        # Approximate additional LEGO parts needed
    # LEGO implementation guidance for Claude
    lego_parts: list[dict] = field(default_factory=list)
    # Each dict: {part_num, bricklink_id, name, typical_color, placement_guide, quantity_guide}
    placement_strategy: str = ""  # Where and how to place these parts
    visual_change: str = ""       # How this changes the car's appearance


# ═══════════════════════════════════════════════════════════════
# REAL-WORLD MODIFICATION PARTS CATALOG
# ═══════════════════════════════════════════════════════════════

MOD_CATALOG: dict[str, list[ModPart]] = {
    # ── AERODYNAMICS ──────────────────────────────
    "aerodynamics": [
        ModPart(
            id="gt-wing-large",
            name="GT Wing (Large)",
            category="aerodynamics",
            real_world_ref="APR GTC-300 / Voltex Type 5",
            description="Large adjustable carbon fiber rear wing mounted on stands. Adds significant downforce. Common on time attack and track cars.",
            difficulty="medium",
            estimated_parts=12,
            lego_parts=[
                {"part_num": "44675.dat", "bricklink_id": "44675", "name": "Slope Curved 2x2 with Fin", "typical_color": 0, "placement_guide": "Wing endplates, 2x per side at wing tips", "quantity_guide": 4},
                {"part_num": "99780.dat", "bricklink_id": "99780", "name": "Bracket 1x2 - 1x2 Up", "typical_color": 0, "placement_guide": "Wing stands/mounts, attach to rear trunk at Z≈290", "quantity_guide": 2},
                {"part_num": "3020.dat", "bricklink_id": "3020", "name": "Plate 2x4", "typical_color": 0, "placement_guide": "Wing main element, horizontal across stands", "quantity_guide": 2},
                {"part_num": "3460.dat", "bricklink_id": "3460", "name": "Plate 1x8", "typical_color": 0, "placement_guide": "Wing blade, thin leading edge across top", "quantity_guide": 1},
            ],
            placement_strategy="Mount two bracket stands (99780) at rear of trunk (Z≈280-300, X=±30, Y≈100-120). Place 2x4 plates (3020) horizontally across stands as wing main plane. Add curved slope fins (44675) at each end as endplates (X=±40). Top with 1x8 plate as wing blade.",
            visual_change="Adds a prominent rear wing elevated ~2 bricks above the trunk, with visible endplates. Transforms the car's rear profile dramatically.",
        ),
        ModPart(
            id="ducktail-spoiler",
            name="Ducktail Spoiler",
            category="aerodynamics",
            real_world_ref="Porsche 911 Ducktail / Rocket Bunny Duckbill",
            description="Subtle upward-angled lip spoiler integrated into the trunk edge. Classic Porsche and JDM style.",
            difficulty="easy",
            estimated_parts=4,
            lego_parts=[
                {"part_num": "43723.dat", "bricklink_id": "43723", "name": "Wedge 3x2 Left", "typical_color": 0, "placement_guide": "Left side of trunk edge spoiler", "quantity_guide": 1},
                {"part_num": "43722.dat", "bricklink_id": "43722", "name": "Wedge 3x2 Right", "typical_color": 0, "placement_guide": "Right side of trunk edge spoiler", "quantity_guide": 1},
                {"part_num": "50950.dat", "bricklink_id": "50950", "name": "Slope Curved 3x1", "typical_color": 0, "placement_guide": "Center connecting curve", "quantity_guide": 2},
            ],
            placement_strategy="Place wedges (43723/43722) on trunk trailing edge (Z≈290, X=±25, Y≈72) angled upward. Connect with curved slopes (50950) in center. Use body color for integrated look or black for contrast.",
            visual_change="Adds a subtle kicked-up lip at the trunk edge. Understated but recognizable to car enthusiasts.",
        ),
        ModPart(
            id="front-splitter",
            name="Front Splitter",
            category="aerodynamics",
            real_world_ref="APR Front Wind Splitter / Racebred Splitter",
            description="Flat carbon fiber panel extending forward from the front bumper. Reduces lift by managing airflow under the car.",
            difficulty="easy",
            estimated_parts=5,
            lego_parts=[
                {"part_num": "3460.dat", "bricklink_id": "3460", "name": "Plate 1x8", "typical_color": 0, "placement_guide": "Splitter lip, extends forward from bumper", "quantity_guide": 1},
                {"part_num": "3023.dat", "bricklink_id": "3023", "name": "Plate 1x2", "typical_color": 0, "placement_guide": "Splitter mounts to bumper underside", "quantity_guide": 2},
                {"part_num": "43723.dat", "bricklink_id": "43723", "name": "Wedge 3x2 Left", "typical_color": 0, "placement_guide": "Left splitter canard", "quantity_guide": 1},
                {"part_num": "43722.dat", "bricklink_id": "43722", "name": "Wedge 3x2 Right", "typical_color": 0, "placement_guide": "Right splitter canard", "quantity_guide": 1},
            ],
            placement_strategy="Mount 1x8 plate (3460) at front bumper bottom edge (Z≈300, Y≈8-16), extending 1 stud forward. Add wedges (43723/43722) as corner canards. Use black (color 0) for carbon fiber look.",
            visual_change="Extends the front bumper lower with a flat blade. Gives the car a more aggressive, track-focused stance.",
        ),
        ModPart(
            id="rear-diffuser",
            name="Rear Diffuser",
            category="aerodynamics",
            real_world_ref="Voltex Rear Diffuser / Top Secret Diffuser",
            description="Multi-fin rear underbody panel that accelerates airflow, creating a low-pressure zone for downforce.",
            difficulty="medium",
            estimated_parts=8,
            lego_parts=[
                {"part_num": "2431.dat", "bricklink_id": "2431", "name": "Tile 1x4", "typical_color": 0, "placement_guide": "Diffuser fin, vertical vane", "quantity_guide": 5},
                {"part_num": "3022.dat", "bricklink_id": "3022", "name": "Plate 2x2", "typical_color": 0, "placement_guide": "Diffuser base plate", "quantity_guide": 2},
                {"part_num": "43713.dat", "bricklink_id": "43713", "name": "Wedge 4x2 Tri-Slope", "typical_color": 0, "placement_guide": "Diffuser angled exit", "quantity_guide": 1},
            ],
            placement_strategy="At rear underbody (Z≈0-60, Y≈8-24, X=-30 to 30). Stack 1x4 tiles (2431) vertically as diffuser fins spaced 1 stud apart. Use 2x2 plates (3022) as base. Add angled exit wedge (43713) at rear edge.",
            visual_change="Adds a technical-looking finned panel under the rear bumper. Visible from behind the car.",
        ),
        ModPart(
            id="canards",
            name="Front Canards (Dive Planes)",
            category="aerodynamics",
            real_world_ref="Voltex Canards / APR Dive Planes",
            description="Small winglets on the front bumper corners that generate front downforce and direct airflow around the wheels.",
            difficulty="easy",
            estimated_parts=4,
            lego_parts=[
                {"part_num": "54200.dat", "bricklink_id": "54200", "name": "Slope 30° 1x1x0.667", "typical_color": 0, "placement_guide": "Canard blade on each bumper corner", "quantity_guide": 4},
            ],
            placement_strategy="Place cheese slopes (54200) at front bumper corners (Z≈300, X=±50-60, Y≈40-56), angled outward and slightly forward. Black (0) or carbon-look. Small but effective detail.",
            visual_change="Adds small protruding fins at the front corners. Subtle but authentic motorsport detail.",
        ),
    ],

    # ── WHEELS & STANCE ───────────────────────────
    "wheels_stance": [
        ModPart(
            id="deep-dish-wheels",
            name="Deep Dish Wheels",
            category="wheels_stance",
            real_world_ref="Work Meister S1 / BBS LM / Volk TE37",
            description="Wider wheels with deep lip/concave face. Classic JDM and Euro style. Often paired with stretched tires.",
            difficulty="medium",
            estimated_parts=8,
            lego_parts=[
                {"part_num": "6014c00.dat", "bricklink_id": "6014c00", "name": "Wheel 11mm + Tire Assembly", "typical_color": 72, "placement_guide": "Deep dish rear wheels, wider offset", "quantity_guide": 2},
                {"part_num": "4624c00.dat", "bricklink_id": "4624c00", "name": "Wheel 8mm + Tire Assembly", "typical_color": 72, "placement_guide": "Front wheels, narrower", "quantity_guide": 2},
                {"part_num": "3024.dat", "bricklink_id": "3024", "name": "Plate 1x1", "typical_color": 71, "placement_guide": "Wheel spacer for wider track", "quantity_guide": 4},
            ],
            placement_strategy="Replace existing wheels. Use wider 11mm wheels (6014c00) at rear, 8mm (4624c00) at front. Add 1x1 plate spacers (3024) between wheel and chassis at rear for +1 stud wider track. Staggered fitment.",
            visual_change="Wider rear wheels with deep concave look. More aggressive stance. Staggered fitment like real sports cars.",
        ),
        ModPart(
            id="offroad-wheels",
            name="Off-Road / Rally Wheels",
            category="wheels_stance",
            real_world_ref="Method Race Wheels / Enkei RPF1 (gravel spec)",
            description="Chunky tires with aggressive tread pattern. Raised ride height. Common on rally and overland builds.",
            difficulty="medium",
            estimated_parts=10,
            lego_parts=[
                {"part_num": "56904c00.dat", "bricklink_id": "56904c00", "name": "Wheel 30mm + Tire 43mm Assembly", "typical_color": 0, "placement_guide": "Large off-road wheels, all 4 corners", "quantity_guide": 4},
                {"part_num": "3020.dat", "bricklink_id": "3020", "name": "Plate 2x4", "typical_color": 71, "placement_guide": "Lift kit spacers under chassis", "quantity_guide": 2},
            ],
            placement_strategy="Replace all 4 wheels with 30mm off-road assemblies (56904c00). Add 2x4 plate spacers above wheel mounts to raise ride height by 1 plate (8 LDU = +0.4 studs). Adjust fender clearance accordingly.",
            visual_change="Much larger diameter wheels with chunky tread. Noticeably lifted ride height. Rally/mud terrain stance.",
        ),
        ModPart(
            id="camber-adjustment",
            name="Negative Camber (Stanced)",
            category="wheels_stance",
            real_world_ref="Oni-kyan / Stance Nation camber arms",
            description="Wheels tilted inward at the top (negative camber). Extreme version is 'stanced' look popular in JDM and VIP scenes.",
            difficulty="hard",
            estimated_parts=4,
            lego_parts=[
                {"part_num": "99206.dat", "bricklink_id": "99206", "name": "Plate 2x2 Rotated 1x2", "typical_color": 71, "placement_guide": "Angled wheel mount for camber", "quantity_guide": 4},
            ],
            placement_strategy="Mount wheels on rotated plates (99206) to tilt the wheel assembly slightly. The 1x2 rotated connector naturally angles ~15° which creates visible camber. Place between wheel hub and chassis mount.",
            visual_change="Wheels visibly tilted inward. Very distinctive 'stanced' look. Fans will recognize this immediately.",
        ),
        ModPart(
            id="wheel-spacers",
            name="Wheel Spacers (Wider Track)",
            category="wheels_stance",
            real_world_ref="H&R TRAK+ / Eibach Pro-Spacer",
            description="Pushes wheels outward for a wider stance and flush fitment with fenders.",
            difficulty="easy",
            estimated_parts=4,
            lego_parts=[
                {"part_num": "3024.dat", "bricklink_id": "3024", "name": "Plate 1x1", "typical_color": 71, "placement_guide": "Spacer between wheel and mount", "quantity_guide": 8},
            ],
            placement_strategy="Stack 2x 1x1 plates (3024) between each wheel holder and chassis. This pushes each wheel outward by 10 LDU (0.5 stud). Adjust X coordinates: rear wheels from ±40 to ±45, front from ±40 to ±45.",
            visual_change="Wheels sit more flush with fenders. Subtle but important for car stance.",
        ),
    ],

    # ── EXHAUST ────────────────────────────────────
    "exhaust": [
        ModPart(
            id="titanium-exhaust",
            name="Titanium Burnt-Tip Exhaust",
            category="exhaust",
            real_world_ref="HKS Hi-Power / GReddy Ti-C / Tomei Expreme",
            description="Large diameter single or dual exhaust with signature blue/purple burnt titanium tip. Iconic JDM look.",
            difficulty="easy",
            estimated_parts=4,
            lego_parts=[
                {"part_num": "6141.dat", "bricklink_id": "6141", "name": "Plate 1x1 Round", "typical_color": 73, "placement_guide": "Exhaust tip (blue=burnt titanium)", "quantity_guide": 2},
                {"part_num": "4599.dat", "bricklink_id": "4599", "name": "Tap 1x1", "typical_color": 71, "placement_guide": "Exhaust pipe body", "quantity_guide": 1},
                {"part_num": "4070.dat", "bricklink_id": "4070", "name": "Brick 1x1 with Headlight", "typical_color": 0, "placement_guide": "Exhaust housing/bezel", "quantity_guide": 1},
            ],
            placement_strategy="Place exhaust housing (4070) at rear bumper (Z≈0-20, Y≈16-32, X=0 or ±20 for dual). Insert tap (4599) as pipe, add round plate (6141) in medium blue (73) as burnt titanium tip. For dual exhaust, mirror at X=±20.",
            visual_change="Large circular exhaust tip with distinctive blue/purple coloring at the tip. Classic JDM rear view.",
        ),
        ModPart(
            id="center-exit-exhaust",
            name="Center-Exit Exhaust",
            category="exhaust",
            real_world_ref="Porsche 911 GT3 center exhaust / Lotus Evora",
            description="Exhaust exits through the center of the rear diffuser instead of corners. Race-derived layout.",
            difficulty="easy",
            estimated_parts=3,
            lego_parts=[
                {"part_num": "6141.dat", "bricklink_id": "6141", "name": "Plate 1x1 Round", "typical_color": 71, "placement_guide": "Dual center pipes", "quantity_guide": 2},
                {"part_num": "3024.dat", "bricklink_id": "3024", "name": "Plate 1x1", "typical_color": 0, "placement_guide": "Center exhaust housing", "quantity_guide": 1},
            ],
            placement_strategy="Place two round plates (6141) centered at rear bumper (Z≈0, Y≈24, X=±10). Mount on 1x1 plate base (3024) in black. Integrate with rear diffuser if present.",
            visual_change="Exhaust moves from corners to center. Clean, modern rear appearance. Motorsport-derived look.",
        ),
        ModPart(
            id="side-exit-exhaust",
            name="Side-Exit Exhaust",
            category="exhaust",
            real_world_ref="RWB side exhaust / Dodge Viper ACR",
            description="Exhaust exits from the side of the car, usually just behind the front wheel or before the rear wheel.",
            difficulty="medium",
            estimated_parts=4,
            lego_parts=[
                {"part_num": "4599.dat", "bricklink_id": "4599", "name": "Tap 1x1", "typical_color": 71, "placement_guide": "Side pipe body", "quantity_guide": 2},
                {"part_num": "6141.dat", "bricklink_id": "6141", "name": "Plate 1x1 Round", "typical_color": 0, "placement_guide": "Side exit tip", "quantity_guide": 2},
            ],
            placement_strategy="Mount exhaust pipes on side of car body (X=±70-80, Y≈24, Z≈120-160). Attach tap (4599) horizontally pointing outward, capped with round plate (6141). Black for stealth or metallic for contrast.",
            visual_change="Exhaust visible on the side of the car. Very aggressive, race-car look. Unmistakable to enthusiasts.",
        ),
    ],

    # ── BODY KITS ──────────────────────────────────
    "body_kits": [
        ModPart(
            id="widebody-overfenders",
            name="Wide Body / Overfenders",
            category="body_kits",
            real_world_ref="Rocket Bunny / Liberty Walk / RWB",
            description="Bolt-on flared fenders extending beyond the stock body width. Exposed rivets/bolts. The defining look of the 'widebody' movement.",
            difficulty="hard",
            estimated_parts=20,
            lego_parts=[
                {"part_num": "11477.dat", "bricklink_id": "11477", "name": "Slope Curved 2x1", "typical_color": 0, "placement_guide": "Fender flare curve, 3-4 per wheel arch", "quantity_guide": 12},
                {"part_num": "50950.dat", "bricklink_id": "50950", "name": "Slope Curved 3x1", "typical_color": 0, "placement_guide": "Wider flare sections at rear", "quantity_guide": 4},
                {"part_num": "3070b.dat", "bricklink_id": "3070b", "name": "Tile 1x1", "typical_color": 71, "placement_guide": "Rivet detail on flare edge", "quantity_guide": 8},
                {"part_num": "3023.dat", "bricklink_id": "3023", "name": "Plate 1x2", "typical_color": 0, "placement_guide": "Flare mounting base", "quantity_guide": 8},
            ],
            placement_strategy="At each wheel arch (front: Z≈240-270, rear: Z≈40-70), add curved slopes (11477) stacked 2-high extending 1-2 studs outward from body (increase X from ±40 to ±60). Use 1x2 plates (3023) as base. Place 1x1 tiles (3070b) on outer edge as exposed rivets. Blend with body color or contrast (black overfenders on colored body).",
            visual_change="Dramatically wider fenders with visible bolt/rivet detail. Significantly changes the car's side profile and stance. The signature 'widebody' look.",
        ),
        ModPart(
            id="front-bumper-canards",
            name="Aggressive Front Bumper",
            category="body_kits",
            real_world_ref="Varis / INGS+ / Veilside front bumper",
            description="Large-mouth front bumper with integrated splitter, larger air intakes, and more aggressive angles.",
            difficulty="medium",
            estimated_parts=10,
            lego_parts=[
                {"part_num": "52031.dat", "bricklink_id": "52031", "name": "Wedge 4x3 Curved", "typical_color": 0, "placement_guide": "Bumper main curve", "quantity_guide": 2},
                {"part_num": "43723.dat", "bricklink_id": "43723", "name": "Wedge 3x2 Left", "typical_color": 0, "placement_guide": "Bumper corner left", "quantity_guide": 1},
                {"part_num": "43722.dat", "bricklink_id": "43722", "name": "Wedge 3x2 Right", "typical_color": 0, "placement_guide": "Bumper corner right", "quantity_guide": 1},
                {"part_num": "30236.dat", "bricklink_id": "30236", "name": "Brick 1x2 with Grille", "typical_color": 0, "placement_guide": "Large grille mesh insert", "quantity_guide": 4},
                {"part_num": "3069b.dat", "bricklink_id": "3069b", "name": "Tile 1x2", "typical_color": 0, "placement_guide": "Bumper surface detail", "quantity_guide": 4},
            ],
            placement_strategy="At front (Z≈280-310, Y≈8-72), replace existing front bumper parts with curved wedges (52031) as main lower section. Use left/right wedges (43723/43722) for corners. Add grille bricks (30236) for large central intake. Tile over (3069b) for smooth surface. Lower the bumper by 1 plate compared to original.",
            visual_change="Larger, more aggressive front end with bigger air intakes. Lower front lip. Transforms the car's 'face'.",
        ),
        ModPart(
            id="side-skirts",
            name="Side Skirts",
            category="body_kits",
            real_world_ref="Chargespeed / STI side under-spoilers",
            description="Extended lower panels running along the sides between front and rear wheels. Visually lowers the car.",
            difficulty="easy",
            estimated_parts=6,
            lego_parts=[
                {"part_num": "2431.dat", "bricklink_id": "2431", "name": "Tile 1x4", "typical_color": 0, "placement_guide": "Side skirt main blade", "quantity_guide": 4},
                {"part_num": "3023.dat", "bricklink_id": "3023", "name": "Plate 1x2", "typical_color": 0, "placement_guide": "Skirt mounting bracket", "quantity_guide": 4},
            ],
            placement_strategy="Along both sides between wheels (X=±60-70, Y≈8-16, Z≈80-220). Place 1x4 tiles (2431) vertically (rotated) as skirt blades. Mount with 1x2 plates (3023) as brackets connecting to chassis. Black (0) or body color.",
            visual_change="Clean line running along the lower body sides. Makes the car look lower and more planted.",
        ),
    ],

    # ── INTERIOR / RACE CONVERSION ─────────────────
    "interior": [
        ModPart(
            id="roll-cage",
            name="Roll Cage (6-Point)",
            category="interior",
            real_world_ref="Cusco Safety 21 / FIA-spec roll cage",
            description="Full welded roll cage visible through windows. Required for serious track cars.",
            difficulty="medium",
            estimated_parts=10,
            lego_parts=[
                {"part_num": "4085.dat", "bricklink_id": "4085", "name": "Plate 1x1 with Clip Vertical", "typical_color": 15, "placement_guide": "Cage junction nodes at A/B/C pillars", "quantity_guide": 6},
                {"part_num": "4599.dat", "bricklink_id": "4599", "name": "Tap 1x1", "typical_color": 15, "placement_guide": "Cage bar segments (horizontal/vertical)", "quantity_guide": 8},
            ],
            placement_strategy="Inside cabin area (Z≈120-240, Y≈48-96, X=±30). Use clip plates (4085) as cage nodes at A-pillar, B-pillar, and C-pillar positions. Connect nodes with tap sticks (4599) as cage bars. White (15) or bright color for visibility through windows.",
            visual_change="Visible safety cage structure through the windows. Instantly recognizable as a track/race car interior.",
        ),
        ModPart(
            id="bucket-seats",
            name="Racing Bucket Seats",
            category="interior",
            real_world_ref="Bride Zeta III / Recaro SPG / Sparco Evo",
            description="Deep bolstered fixed-back racing seats with harness holes. Replace stock seats.",
            difficulty="easy",
            estimated_parts=5,
            lego_parts=[
                {"part_num": "3041.dat", "bricklink_id": "3041", "name": "Slope 45° 2x2", "typical_color": 4, "placement_guide": "Seat back bolster (angled)", "quantity_guide": 2},
                {"part_num": "3022.dat", "bricklink_id": "3022", "name": "Plate 2x2", "typical_color": 0, "placement_guide": "Seat base", "quantity_guide": 2},
                {"part_num": "3070b.dat", "bricklink_id": "3070b", "name": "Tile 1x1", "typical_color": 71, "placement_guide": "Harness hole detail", "quantity_guide": 2},
            ],
            placement_strategy="Inside cabin (Z≈160-200, Y≈8, X=±20). Place 2x2 plates (3022) as seat bases. Stack slope 45° (3041) behind as high backrest. Add 1x1 tile (3070b) as harness pass-through detail. Red (4) or black (0) for authentic racing seat look.",
            visual_change="Visible racing seats through windows. Distinctive reclined bucket shape.",
        ),
    ],

    # ── LIGHTING ───────────────────────────────────
    "lighting": [
        ModPart(
            id="led-daytime-lights",
            name="LED Daytime Running Lights",
            category="lighting",
            real_world_ref="Audi-style LED DRL / Morimoto XSB switchback",
            description="Bright LED light strips in the front bumper or headlights. Modern premium car signature.",
            difficulty="easy",
            estimated_parts=3,
            lego_parts=[
                {"part_num": "3070b.dat", "bricklink_id": "3070b", "name": "Tile 1x1", "typical_color": 15, "placement_guide": "Individual LED points in strip", "quantity_guide": 6},
            ],
            placement_strategy="Line up 1x1 white tiles (3070b) in a row along lower front bumper edge (Z≈295, Y≈32, X=-40 to 40, spaced every 10 LDU). White color (15) on dark background creates the LED look. Can be L-shaped following modern DRL designs.",
            visual_change="Distinctive bright LED signature in front bumper. Modernizes the car's face significantly.",
        ),
        ModPart(
            id="smoked-taillights",
            name="Smoked/Tinted Taillights",
            category="lighting",
            real_world_ref="Smoked taillight film / OEM blackline taillights",
            description="Darkened rear light housings. Popular on black/white/gray build themes.",
            difficulty="easy",
            estimated_parts=2,
            lego_parts=[
                {"part_num": "3024.dat", "bricklink_id": "3024", "name": "Plate 1x1", "typical_color": 0, "placement_guide": "Tinted cover overlay on taillights", "quantity_guide": 2},
            ],
            placement_strategy="Replace existing taillight parts with same part in transparent-black or overlay with 1x1 black plates (3024). Keep red edge for legal look. Trans-black or dark gray color.",
            visual_change="Darker, more menacing rear lights. Subtle but effective for dark-themed builds.",
        ),
    ],

    # ── PERFORMANCE / ENGINE ───────────────────────
    "performance": [
        ModPart(
            id="engine-bay-show",
            name="Show Engine Bay (Visible)",
            category="performance",
            real_world_ref="Shaved/tucked engine bay / HKS turbo kit",
            description="Detailed engine visible through transparent hood or open engine cover. Polished intake, turbo piping, strut bar.",
            difficulty="hard",
            estimated_parts=12,
            lego_parts=[
                {"part_num": "3003.dat", "bricklink_id": "3003", "name": "Brick 2x2", "typical_color": 71, "placement_guide": "Engine block", "quantity_guide": 2},
                {"part_num": "4599.dat", "bricklink_id": "4599", "name": "Tap 1x1", "typical_color": 0, "placement_guide": "Turbo/intercooler piping", "quantity_guide": 3},
                {"part_num": "6141.dat", "bricklink_id": "6141", "name": "Plate 1x1 Round", "typical_color": 4, "placement_guide": "Valve cover / oil cap detail", "quantity_guide": 4},
                {"part_num": "3024.dat", "bricklink_id": "3024", "name": "Plate 1x1", "typical_color": 0, "placement_guide": "Strut bar across engine bay", "quantity_guide": 2},
                {"part_num": "3068b.dat", "bricklink_id": "3068b", "name": "Tile 2x2", "typical_color": 0, "placement_guide": "Radiator / intercooler top", "quantity_guide": 1},
            ],
            placement_strategy="Create engine detail under rear hood/engine cover (rear-engine cars: Z≈120-220, Y≈24-72, mid: X=±20). Build 2x2 brick engine block (3003) with round plate details (6141). Add tap piping (4599) for turbo plumbing. Span strut bar (3024) across bay. Cover with tile as radiator.",
            visual_change="Detailed engine visible through transparent or open rear deck. Adds mechanical authenticity.",
        ),
        ModPart(
            id="intercooler-front",
            name="Front-Mount Intercooler (FMIC)",
            category="performance",
            real_world_ref="HKS Type-R / GReddy Spec-LS intercooler",
            description="Large silver intercooler visible through the front bumper grille. Signature turbo car look.",
            difficulty="easy",
            estimated_parts=4,
            lego_parts=[
                {"part_num": "30236.dat", "bricklink_id": "30236", "name": "Brick 1x2 with Grille", "typical_color": 71, "placement_guide": "Intercooler core behind front grille", "quantity_guide": 2},
                {"part_num": "3069b.dat", "bricklink_id": "3069b", "name": "Tile 1x2", "typical_color": 71, "placement_guide": "Intercooler end tanks", "quantity_guide": 2},
                {"part_num": "6141.dat", "bricklink_id": "6141", "name": "Plate 1x1 Round", "typical_color": 0, "placement_guide": "Intercooler piping ends", "quantity_guide": 2},
            ],
            placement_strategy="Behind front grille opening (Z≈280, Y≈32-56, X=-24 to 24). Place grille bricks (30236) in light bluish gray (71) as intercooler core. Add tile end tanks (3069b) at sides. Round plates (6141) at bottom corners as charge pipe connections.",
            visual_change="Large silver cooling core visible through front grille. Instantly says 'turbocharged'.",
        ),
    ],

    # ── PAINT & FINISH ─────────────────────────────
    "paint_finish": [
        ModPart(
            id="racing-stripes",
            name="Racing Stripes (GT/Le Mans style)",
            category="paint_finish",
            real_world_ref="Ford GT Heritage / Viper ACR stripes",
            description="Bold center racing stripes running the full length of the car. Classic motorsport livery element.",
            difficulty="easy",
            estimated_parts=10,
            lego_parts=[
                {"part_num": "3069b.dat", "bricklink_id": "3069b", "name": "Tile 1x2", "typical_color": 15, "placement_guide": "Stripe centerline tiles", "quantity_guide": 8},
                {"part_num": "3070b.dat", "bricklink_id": "3070b", "name": "Tile 1x1", "typical_color": 15, "placement_guide": "Stripe end caps", "quantity_guide": 4},
            ],
            placement_strategy="Run 1x2 tiles (3069b) in a contrasting color from hood (Z≈280) across roof (Z≈180) to trunk (Z≈60), centered at X=0. Two parallel lines 2 studs apart. Complete with 1x1 end caps (3070b). White on blue, black on white, silver on red — classic combos.",
            visual_change="Bold racing stripes running nose-to-tail. Converts any car into a GT/racing look.",
        ),
        ModPart(
            id="carbon-fiber-accents",
            name="Carbon Fiber Accents",
            category="paint_finish",
            real_world_ref="Carbon fiber hood / trunk / mirror caps",
            description="Replace body panels with dark gray/black parts to simulate carbon fiber weave. Hood, trunk, roof, mirror caps.",
            difficulty="easy",
            estimated_parts=6,
            lego_parts=[
                {"part_num": "3068b.dat", "bricklink_id": "3068b", "name": "Tile 2x2", "typical_color": 72, "placement_guide": "Carbon hood panel", "quantity_guide": 4},
                {"part_num": "3070b.dat", "bricklink_id": "3070b", "name": "Tile 1x1", "typical_color": 72, "placement_guide": "Carbon mirror cap detail", "quantity_guide": 2},
            ],
            placement_strategy="On hood (Z≈240-280, Y≈72-96), replace body-color tiles with dark bluish gray (72) tiles for carbon look. Same for trunk lid (Z≈40-100). Add 1x1 dark gray tiles on mirror housings. Contrast with body color.",
            visual_change="Dark gray/black hood and panels contrasting with body color. The universal tuner look.",
        ),
        ModPart(
            id="two-tone-paint",
            name="Two-Tone Paint (Roof Contrast)",
            category="paint_finish",
            real_world_ref="MINI Cooper roof / Toyota C-HR / Rolls-Royce two-tone",
            description="Roof and pillars painted in contrasting color. Classic on MINI Coopers, modern on SUVs.",
            difficulty="easy",
            estimated_parts=8,
            lego_parts=[],
            placement_strategy="No new parts needed — recolor all roof-level parts (Y>96) to contrasting color (e.g., white body → black roof, or silver body → red roof). Include A/B/C pillar parts. The change is purely in color_id assignments.",
            visual_change="Contrasting roof color. Elegant or sporty depending on color combo.",
        ),
    ],
}

# ── Helper functions ──────────────────────────────────

def get_mod_by_id(mod_id: str) -> ModPart | None:
    """Find a specific mod part by ID across all categories."""
    for category_mods in MOD_CATALOG.values():
        for mod in category_mods:
            if mod.id == mod_id:
                return mod
    return None


def get_all_mods() -> list[ModPart]:
    """Get flat list of all mod parts."""
    all_mods = []
    for category_mods in MOD_CATALOG.values():
        all_mods.extend(category_mods)
    return all_mods


def get_mods_by_category(category: str) -> list[ModPart]:
    """Get all mods in a specific category."""
    return MOD_CATALOG.get(category, [])


def format_mods_for_llm(mod_ids: list[str]) -> str:
    """Build a detailed prompt section for Claude describing selected mods.

    Includes part numbers, placement coordinates, and visual guidance.
    """
    selected_mods = []
    for mid in mod_ids:
        mod = get_mod_by_id(mid)
        if mod:
            selected_mods.append(mod)

    if not selected_mods:
        return ""

    sections = []
    for mod in selected_mods:
        part_lines = []
        for p in mod.lego_parts:
            part_lines.append(
                f"    - {p['part_num']} (BL:{p['bricklink_id']}) | {p['name']} | "
                f"Color: {p['typical_color']} | {p['placement_guide']} | Qty: ~{p['quantity_guide']}"
            )

        sections.append(f"""### {mod.name} [{mod.real_world_ref}]
**Category**: {mod.category} | **Difficulty**: {mod.difficulty} | **~{mod.estimated_parts} additional parts

**What it is**: {mod.description}

**LEGO Parts to use**:
{chr(10).join(part_lines)}

**Placement Strategy**: {mod.placement_strategy}

**Visual Result**: {mod.visual_change}""")

    return "\n\n".join(sections)
