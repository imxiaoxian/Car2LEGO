"""Curated LEGO parts catalog for LLM prompting.

Provides a carefully selected subset of LEGO parts organized by function,
with part numbers, descriptions, and typical usage in car models.

This catalog is injected into the Claude prompt so the LLM can reason
about which parts to use for specific car features.
"""

from dataclasses import dataclass


@dataclass
class PartInfo:
    part_num: str          # LDraw filename (e.g., "3024.dat")
    bricklink_id: str      # BrickLink part ID
    name: str              # Human-readable name
    category: str          # chassis / body / windows / wheels / details
    size: str              # e.g., "1x2", "2x4", "6L"
    usage: str             # How this part is used in car models


# ── Curated parts catalog (~80 parts optimized for car building) ──

CAR_PARTS_CATALOG: list[PartInfo] = [
    # ═══ CHASSIS / BASE ═══
    PartInfo("3020.dat", "3020", "Plate 2x4", "chassis", "2x4", "Base platform, chassis frame"),
    PartInfo("3021.dat", "3021", "Plate 2x3", "chassis", "2x3", "Chassis sections"),
    PartInfo("3022.dat", "3022", "Plate 2x2", "chassis", "2x2", "Chassis corner fill"),
    PartInfo("3023.dat", "3023", "Plate 1x2", "chassis", "1x2", "Chassis rails, narrow sections"),
    PartInfo("3024.dat", "3024", "Plate 1x1", "chassis", "1x1", "Fill gaps, detail"),
    PartInfo("3666.dat", "3666", "Plate 1x6", "chassis", "1x6", "Side rails, long chassis"),
    PartInfo("3460.dat", "3460", "Plate 1x8", "chassis", "1x8", "Long chassis beams"),
    PartInfo("3034.dat", "3034", "Plate 2x8", "chassis", "2x8", "Main chassis plate"),
    PartInfo("3035.dat", "3035", "Plate 4x8", "chassis", "4x8", "Wide base plate"),
    PartInfo("4282.dat", "4282", "Plate 2x16", "chassis", "2x16", "Full-length chassis beam"),
    PartInfo("3795.dat", "3795", "Plate 2x6", "chassis", "2x6", "Mid-length chassis"),

    # ═══ BRICKS (body structure) ═══
    PartInfo("3005.dat", "3005", "Brick 1x1", "body", "1x1", "Detail, pillars, fill"),
    PartInfo("3004.dat", "3004", "Brick 1x2", "body", "1x2", "Narrow body sections, pillars"),
    PartInfo("3622.dat", "3622", "Brick 1x3", "body", "1x3", "Body sides"),
    PartInfo("3010.dat", "3010", "Brick 1x4", "body", "1x4", "Side panels, roof rails"),
    PartInfo("3009.dat", "3009", "Brick 1x6", "body", "1x6", "Long body sides"),
    PartInfo("3008.dat", "3008", "Brick 1x8", "body", "1x8", "Long side sections"),
    PartInfo("3003.dat", "3003", "Brick 2x2", "body", "2x2", "Pillar bases, engine block"),
    PartInfo("3002.dat", "3002", "Brick 2x3", "body", "2x3", "Body panels"),
    PartInfo("3001.dat", "3001", "Brick 2x4", "body", "2x4", "Main body blocks, roof"),
    PartInfo("2456.dat", "2456", "Brick 2x6", "body", "2x6", "Roof panel, hood"),

    # ═══ SLOPES (angled bodywork) ═══
    PartInfo("4286.dat", "4286", "Slope 33° 3x1", "body", "3x1 slope", "Narrow angled panels"),
    PartInfo("4287.dat", "4287", "Slope 33° 3x1 Inverted", "body", "3x1 inv", "Under-body angles"),
    PartInfo("3298.dat", "3298", "Slope 33° 3x2", "body", "3x2 slope", "Hood angles, rear window"),
    PartInfo("3297.dat", "3297", "Slope 33° 3x4", "body", "3x4 slope", "Large angled panels, windshield base"),
    PartInfo("30363.dat", "30363", "Slope 18° 4x2", "body", "4x2 slope", "Smooth hood, roof slope"),
    PartInfo("3040.dat", "3040", "Slope 45° 2x1", "body", "2x1 slope", "Sharp angles, front lip"),
    PartInfo("3041.dat", "3041", "Slope 45° 2x2", "body", "2x2 slope", "Nose cone detail"),
    PartInfo("3665.dat", "3665", "Slope 45° 2x1 Inverted", "body", "2x1 inv", "Under-spoiler detail"),
    PartInfo("3039.dat", "3039", "Slope 45° 2x2 Double", "body", "2x2 roof", "Roof corners, peaked hood"),
    PartInfo("3043.dat", "3043", "Slope 45° 2x3", "body", "2x3 slope", "Front bumper slope"),
    PartInfo("60481.dat", "60481", "Slope 65° 2x1x2", "body", "2x1x2", "Steep front/rear fascia"),
    PartInfo("11477.dat", "11477", "Slope Curved 2x1", "body", "2x1 curved", "Wheel arch, curved body lines"),
    PartInfo("15068.dat", "15068", "Slope Curved 2x2", "body", "2x2 curved", "Smooth curved panels, modern cars"),
    PartInfo("50950.dat", "50950", "Slope Curved 3x1", "body", "3x1 curved", "Fender curve, side skirt"),

    # ═══ TILES (smooth surfaces) ═══
    PartInfo("3069b.dat", "3069b", "Tile 1x2", "body", "1x2", "Smooth trim, side details"),
    PartInfo("3070b.dat", "3070b", "Tile 1x1", "body", "1x1", "Headlight, small detail"),
    PartInfo("2431.dat", "2431", "Tile 1x4", "body", "1x4", "Side sill, stripe"),
    PartInfo("6636.dat", "6636", "Tile 1x6", "body", "1x6", "Long trim line"),
    PartInfo("3068b.dat", "3068b", "Tile 2x2", "body", "2x2", "Roof panel, hood insert"),
    PartInfo("87079.dat", "87079", "Tile 2x4", "body", "2x4", "Large flat surface, roof"),
    PartInfo("63864.dat", "63864", "Tile 1x3", "body", "1x3", "Trim detail"),

    # ═══ WHEELS & TIRES ═══
    PartInfo("4624.dat", "4624", "Wheel Center Small (8mm)", "wheels", "8mm rim", "Standard car wheel hub"),
    PartInfo("3641.dat", "3641", "Tire 15mm D. x 6mm", "wheels", "15mm tire", "Standard car tire"),
    PartInfo("6014.dat", "6014", "Wheel Center Large (11mm)", "wheels", "11mm rim", "Larger car/sports wheel hub"),
    PartInfo("6015.dat", "6015", "Tire 21mm D. x 12mm", "wheels", "21mm tire", "Large sports car tire"),
    PartInfo("55981.dat", "55981", "Wheel 18mm D. x 14mm", "wheels", "18mm", "Supercar wide rear wheel"),
    PartInfo("56904.dat", "56904", "Wheel 30mm D. x 14mm", "wheels", "30mm", "Large Technic-style wheel"),
    PartInfo("4600.dat", "4600", "Wheel Holder 2x2", "wheels", "2x2", "Wheel bearing / axle mount"),
    PartInfo("6157.dat", "6157", "Wheel Holder 2x2 with Axle", "wheels", "2x2 axle", "Rotating wheel mount"),

    # ═══ WINDOWS / WINDSHIELDS ═══
    PartInfo("3823.dat", "3823", "Windscreen 2x4x2", "windows", "2x4x2", "Mid-size windshield, sports car"),
    PartInfo("2437.dat", "2437", "Windscreen 3x4x1.3", "windows", "3x4x1.3", "Low-profile sport windshield"),
    PartInfo("4176.dat", "4176", "Windscreen 2x6x2", "windows", "2x6x2", "Wide windshield"),
    PartInfo("60601.dat", "60601", "Glass for Window 1x2x2", "windows", "1x2x2", "Side window"),
    PartInfo("87552.dat", "87552", "Panel 1x2x2 with Glass", "windows", "1x2x2", "Side window panel"),
    PartInfo("4865.dat", "4865", "Panel 1x2x1", "windows", "1x2x1", "Small side window"),
    PartInfo("59349.dat", "59349", "Panel 1x4x3 Wall Element", "windows", "1x4x3", "Large body panel / window frame"),

    # ═══ CAR DETAILS ═══
    PartInfo("4070.dat", "4070", "Brick 1x1 with Headlight", "details", "1x1 light", "Headlight housing"),
    PartInfo("4085.dat", "4085", "Plate 1x1 with Clip Vertical", "details", "1x1 clip", "Mirror mount, antenna base"),
    PartInfo("4599.dat", "4599", "Tap 1x1", "details", "1x1", "Exhaust tip, antenna"),
    PartInfo("6141.dat", "6141", "Plate 1x1 Round", "details", "1x1 round", "Headlight lens, fog light, tail light"),
    PartInfo("54200.dat", "54200", "Slope 30° 1x1x0.667", "details", "cheese", "Detail greebling, small angles"),
    PartInfo("49668.dat", "49668", "Plate 1x1 with Tooth", "details", "1x1 tooth", "Grille detail, front lip"),
    PartInfo("2412b.dat", "2412b", "Tile 1x2 Grille", "details", "1x2 grille", "Radiator grille"),
    PartInfo("30236.dat", "30236", "Brick 1x2 with Grille", "details", "1x2 grille", "Front grille section"),
    PartInfo("47755.dat", "47755", "Wedge 4x3 Cut Corner", "details", "4x3 wedge", "Front hood curve"),
    PartInfo("43723.dat", "43723", "Wedge 3x2 Left", "details", "3x2 left", "Angled front bumper left"),
    PartInfo("43722.dat", "43722", "Wedge 3x2 Right", "details", "3x2 right", "Angled front bumper right"),
    PartInfo("50943.dat", "50943", "Wedge 4x2 Left", "details", "4x2 left", "Front corner left"),
    PartInfo("50943.dat", "50944", "Wedge 4x2 Right", "details", "4x2 right", "Front corner right"),
    PartInfo("52031.dat", "52031", "Wedge 4x3 Curved", "details", "4x3 curve", "Smooth front bumper curve"),
    PartInfo("44675.dat", "44675", "Slope Curved 2x2 with Fin", "details", "2x2 fin", "Rear spoiler element"),
    PartInfo("43713.dat", "43713", "Wedge 4x2 Tri-Slope", "details", "4x2 tri", "Rear diffuser, front air dam"),
    PartInfo("99780.dat", "99780", "Bracket 1x2 - 1x2 Up", "details", "1x2 bracket", "Side mirror mount, spoiler mount"),
    PartInfo("99206.dat", "99206", "Plate 2x2 with Rotated 1x2", "details", "2x2 angle", "Angled detail mounting"),
    PartInfo("2555.dat", "2555", "Tile 1x1 with Clip", "details", "1x1 clip", "Wing mirror glass"),

    # ═══ UNDERBODY / MECHANICAL ═══
    PartInfo("3700.dat", "3700", "Technic Brick 1x2 with Hole", "mechanical", "1x2 hole", "Axle pass-through"),
    PartInfo("3701.dat", "3701", "Technic Brick 1x4 with Holes", "mechanical", "1x4 hole", "Structural axle beam"),
    PartInfo("32064.dat", "32064", "Technic Brick 1x2 with Cross Hole", "mechanical", "1x2 cross", "Wheel axle mount"),
    PartInfo("6536.dat", "6536", "Technic Axle and Pin Connector", "mechanical", "connector", "Wheel suspension link"),
    PartInfo("2780.dat", "2780", "Technic Pin with Friction", "mechanical", "pin", "Connector pin for chassis"),
    PartInfo("3673.dat", "3673", "Technic Pin without Friction", "mechanical", "smooth pin", "Free-spinning connection"),
    PartInfo("32062.dat", "32062", "Technic Axle 2 Notched", "mechanical", "2L axle", "Short axle for wheels"),
    PartInfo("4519.dat", "4519", "Technic Axle 3", "mechanical", "3L axle", "Wheel axle"),
]

# ── Common LEGO Colors (subset used in car models) ──

CAR_COLORS = {
    0:  ("Black", "#1B2A34"),
    1:  ("Blue", "#0051A8"),
    2:  ("Green", "#237841"),
    4:  ("Red", "#C91A09"),
    5:  ("Dark Pink", "#C870A0"),
    14: ("Yellow", "#F5CD2F"),
    15: ("White", "#FFFFFF"),
    25: ("Orange", "#FE8A18"),
    26: ("Magenta", "#923978"),
    71: ("Light Bluish Gray", "#A0A5A9"),
    72: ("Dark Bluish Gray", "#6C6E6C"),
    85: ("Dark Tan", "#958A73"),
    19: ("Tan", "#E4CD9E"),
    73: ("Medium Blue", "#5A91C3"),
    74: ("Medium Green", "#73DCA1"),
    88: ("Dark Red", "#720E0F"),
    89: ("Dark Blue", "#1B2A34"),
}
