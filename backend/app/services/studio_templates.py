"""Pre-built BrickLink Studio .io file templates for car body styles.

Each template is a minimal but recognizable LEGO car chassis for a specific
body style category. These are the 'base cars' that modifications are applied to.

Templates follow Studio 2.26.6 format with:
  - Proper 0 FILE structure
  - 0 STEP separators for build instructions
  - Speed Champions 6-wide scale (default)
  - Common color: Red (4) body, Black (0) details, Light Gray (7) chassis

Multi-scale support: templates are defined at Speed Champions (8-wide) scale
and scaled proportionally for other sizes via LEGO_SCALES dimension profiles.
"""

# ═══════════════════════════════════════════════════════════════
# SCALE SPECS — simple ratio → dimensions mapping
# ═══════════════════════════════════════════════════════════════

SCALE_SPECS: dict[str, dict] = {
    "1:38": {
        "length_ldu": (280, 360),
        "width_ldu": (120, 160),
        "height_ldu": (96, 144),
        "wheel": "4624c00.dat",
        "total_pieces": (200, 350),
        "unique_parts": (20, 40),
        "ref_sets": "76919(245) 76920(344) 77242(275) 76934(318)",
        "note": "Speed Champions 8-wide — key body lines, grille, headlights, rear wing",
        "ai_supported": True,
    },
    "1:12": {
        "length_ldu": (520, 640),
        "width_ldu": (240, 280),
        "height_ldu": (192, 288),
        "wheel": "4624c00.dat",
        "total_pieces": (900, 2400),
        "unique_parts": (80, 150),
        "ref_sets": "10295(1458) 10337(1506) 10304(1456) 10357(1241) 10321(1210)",
        "note": "Icons / Creator Expert — parts import only (no AI generation)",
        "ai_supported": False,
    },
    "1:10": {
        "length_ldu": (720, 800),
        "width_ldu": (300, 360),
        "height_ldu": (216, 288),
        "wheel": "4624c00.dat",
        "total_pieces": (800, 1800),
        "unique_parts": (100, 180),
        "ref_sets": "42154(1466) 42156(1775) 42171(1642) 42206(1639) 42207(1361)",
        "note": "Technic 1:10 mid — parts import only (no AI generation)",
        "ai_supported": False,
    },
    "1:8": {
        "length_ldu": (1120, 1200),
        "width_ldu": (480, 560),
        "height_ldu": (336, 432),
        "wheel": "4624c00.dat",
        "total_pieces": (2700, 4100),
        "unique_parts": (150, 300),
        "ref_sets": "42056(2704) 42083(3599) 42115(3696) 42143(3778) 42172(3893) 42232(4104)",
        "note": "Technic 1:8 supercar — parts import only (no AI generation)",
        "ai_supported": False,
    },
}

SUPPORTED_SCALES = list(SCALE_SPECS.keys())
DEFAULT_SCALE = "1:38"

# ═══════════════════════════════════════════════════════════════
# BASE CAR TEMPLATES
# ═══════════════════════════════════════════════════════════════

# Each template defines a COMPLETE Speed Champions 6-wide car chassis.
# Dimensions: ~16 studs long (Z: 0-320 LDU), 6-8 wide (X: -60 to 60), 5 bricks tall (Y: 0-120)
# Coordinates in LDU (LDraw Units): 1 stud = 20 LDU, 1 brick = 24 LDU, 1 plate = 8 LDU

TEMPLATE_SPORTS_CAR = """0 // ===== SPORTS CAR TEMPLATE (Speed Champions 8-wide) =====
0 // Low-slung, mid-engine proportions. Base for: Ferrari, Lamborghini, McLaren, Porsche
0 // Dimensions: 16 studs long (Z:0-320), 8 wide (X:0-80 right half), 5 bricks tall (Y:0-120)
0 // Right-half only — auto-mirrored by _build_ldraw()

0 // ── Chassis Base ──
0 STEP
1 7 20 8 80 1 0 0 0 1 0 0 0 1 3034.dat
1 7 20 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 80 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 40 8 160 1 0 0 0 1 0 0 0 1 3020.dat
1 7 40 8 20 1 0 0 0 1 0 0 0 1 3021.dat
1 7 40 8 300 1 0 0 0 1 0 0 0 1 3021.dat
1 7 20 8 160 1 0 0 0 1 0 0 0 1 3020.dat

0 // ── Chassis Frame ──
0 STEP
1 7 60 24 80 1 0 0 0 1 0 0 0 1 3460.dat
1 7 60 24 240 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 80 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 240 1 0 0 0 1 0 0 0 1 3460.dat

0 // ── Body Side ──
0 STEP
1 4 60 48 100 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 48 180 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 72 100 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 72 180 1 0 0 0 1 0 0 0 1 3010.dat
1 4 70 48 40 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 48 280 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 72 40 1 0 0 0 1 0 0 0 1 15068.dat
1 4 70 72 280 1 0 0 0 1 0 0 0 1 15068.dat
1 4 60 48 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 48 280 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 72 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 72 280 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Hood ──
0 STEP
1 4 40 80 280 1 0 0 0 1 0 0 0 1 3297.dat
1 4 40 80 240 1 0 0 0 1 0 0 0 1 87079.dat
1 0 40 80 300 1 0 0 0 1 0 0 0 1 30236.dat
1 4 40 88 260 1 0 0 0 1 0 0 0 1 3069b.dat
1 4 40 88 220 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Windshield ──
0 STEP
1 72 40 88 200 1 0 0 0 1 0 0 0 1 4176.dat
1 72 60 88 200 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Roof ──
0 STEP
1 4 40 104 180 1 0 0 0 1 0 0 0 1 30363.dat
1 4 40 104 140 1 0 0 0 1 0 0 0 1 3068b.dat
1 4 40 104 100 1 0 0 0 1 0 0 0 1 30363.dat
1 4 40 104 60 1 0 0 0 1 0 0 0 1 3298.dat

0 // ── Rear Body ──
0 STEP
1 4 40 80 40 1 0 0 0 1 0 0 0 1 3298.dat
1 4 40 80 20 1 0 0 0 1 0 0 0 1 15068.dat
1 4 40 56 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 40 56 20 1 0 0 0 1 0 0 0 1 3004.dat
1 4 40 80 60 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Headlight ──
0 STEP
1 14 60 56 310 1 0 0 0 1 0 0 0 1 4070.dat
1 14 60 64 310 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 48 310 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Taillight ──
0 STEP
1 4 60 56 10 1 0 0 0 1 0 0 0 1 4070.dat
1 4 60 64 10 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 48 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Bumper ──
0 STEP
1 0 40 40 310 1 0 0 0 1 0 0 0 1 3043.dat
1 0 40 40 10 1 0 0 0 1 0 0 0 1 3043.dat
1 0 60 32 310 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 32 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Wheel Arch ──
0 STEP
1 0 60 24 60 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 60 24 260 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 70 24 80 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 70 24 240 0 0 1 0 1 0 -1 0 0 11477.dat

0 // ── Wheel ──
0 STEP
1 0 60 8 60 1 0 0 0 1 0 0 0 1 4624c00.dat
1 0 60 8 260 1 0 0 0 1 0 0 0 1 4624c00.dat

0 // ── Diffuser ──
0 STEP
1 0 40 16 10 1 0 0 0 1 0 0 0 1 3023.dat
1 0 40 24 10 1 0 0 0 1 0 0 0 1 60481.dat
1 0 60 16 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Detail ──
0 STEP
1 0 60 56 160 1 0 0 0 1 0 0 0 1 4085.dat
1 0 60 64 160 1 0 0 0 1 0 0 0 1 2555.dat
1 0 40 24 20 1 0 0 0 1 0 0 0 1 4599.dat
1 0 40 80 160 1 0 0 0 1 0 0 0 1 2431.dat
1 0 40 88 120 1 0 0 0 1 0 0 0 1 2431.dat
"""

TEMPLATE_SUV = """0 // ===== SUV/OFF-ROAD TEMPLATE (Speed Champions 8-wide) =====
0 // Taller, boxier proportions. Base for: Land Rover, Jeep, G-Wagon
0 // Dimensions: 16 studs long (Z:0-320), 8 wide (X:0-80 right half), 7 bricks tall (Y:0-168)
0 // Right-half only — auto-mirrored by _build_ldraw()

0 // ── Chassis Base ──
0 STEP
1 7 20 8 80 1 0 0 0 1 0 0 0 1 3034.dat
1 7 20 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 80 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 40 8 160 1 0 0 0 1 0 0 0 1 3020.dat
1 7 40 8 20 1 0 0 0 1 0 0 0 1 3021.dat
1 7 40 8 300 1 0 0 0 1 0 0 0 1 3021.dat

0 // ── Chassis Frame ──
0 STEP
1 7 60 24 80 1 0 0 0 1 0 0 0 1 3460.dat
1 7 60 24 240 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 80 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 240 1 0 0 0 1 0 0 0 1 3460.dat

0 // ── Body Side ──
0 STEP
1 4 60 48 100 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 48 180 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 96 100 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 96 180 1 0 0 0 1 3009.dat
1 4 70 48 40 1 0 0 0 1 0 0 0 1 3039.dat
1 4 70 48 280 1 0 0 0 1 0 0 0 1 3039.dat
1 4 70 96 40 1 0 0 0 1 0 0 0 1 15068.dat
1 4 70 96 280 1 0 0 0 1 0 0 0 1 15068.dat
1 4 60 48 40 1 0 0 0 1 0 0 0 1 3008.dat
1 4 60 48 280 1 0 0 0 1 0 0 0 1 3008.dat
1 4 60 96 40 1 0 0 0 1 0 0 0 1 3008.dat
1 4 60 96 280 1 0 0 0 1 0 0 0 1 3008.dat

0 // ── Hood ──
0 STEP
1 4 40 120 280 1 0 0 0 1 0 0 0 1 3297.dat
1 4 40 120 240 1 0 0 0 1 0 0 0 1 87079.dat
1 0 40 120 300 1 0 0 0 1 0 0 0 1 30236.dat
1 4 40 128 260 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Windshield ──
0 STEP
1 72 40 128 220 1 0 0 0 1 0 0 0 1 4176.dat
1 72 60 128 220 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Roof ──
0 STEP
1 4 40 152 180 1 0 0 0 1 0 0 0 1 87079.dat
1 4 40 152 140 1 0 0 0 1 0 0 0 1 87079.dat
1 4 40 152 100 1 0 0 0 1 0 0 0 1 30363.dat

0 // ── Rear Body ──
0 STEP
1 4 40 120 40 1 0 0 0 1 0 0 0 1 3039.dat
1 4 40 120 20 1 0 0 0 1 0 0 0 1 15068.dat
1 4 40 96 40 1 0 0 0 1 0 0 0 1 3008.dat
1 4 40 120 60 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Headlight ──
0 STEP
1 14 60 96 310 1 0 0 0 1 0 0 0 1 4070.dat
1 14 60 104 310 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 88 310 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Taillight ──
0 STEP
1 4 60 96 10 1 0 0 0 1 0 0 0 1 4070.dat
1 4 60 104 10 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 88 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Bumper ──
0 STEP
1 0 40 80 310 1 0 0 0 1 0 0 0 1 3043.dat
1 0 40 80 10 1 0 0 0 1 0 0 0 1 3043.dat
1 0 60 72 310 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 72 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Wheel Arch ──
0 STEP
1 0 60 24 60 0 0 1 0 1 0 -1 0 0 50950.dat
1 0 60 24 260 0 0 1 0 1 0 -1 0 0 50950.dat
1 0 70 24 80 0 0 1 0 1 0 -1 0 0 50950.dat
1 0 70 24 240 0 0 1 0 1 0 -1 0 0 50950.dat

0 // ── Wheel ──
0 STEP
1 0 60 8 60 1 0 0 0 1 0 0 0 1 56904c00.dat
1 0 60 8 260 1 0 0 0 1 0 0 0 1 56904c00.dat

0 // ── Detail ──
0 STEP
1 0 60 96 160 1 0 0 0 1 0 0 0 1 4085.dat
1 0 60 104 160 1 0 0 0 1 0 0 0 1 2555.dat
1 0 40 24 20 1 0 0 0 1 0 0 0 1 4599.dat
1 0 40 120 160 1 0 0 0 1 0 0 0 1 2431.dat
1 0 40 128 120 1 0 0 0 1 0 0 0 1 2431.dat
"""

TEMPLATE_SEDAN = """0 // ===== SEDAN TEMPLATE (Speed Champions 8-wide) =====
0 // 4-door proportions. Base for: BMW, Mercedes, Toyota, Honda
0 // Dimensions: 16 studs long (Z:0-320), 8 wide (X:0-80 right half), 6 bricks tall (Y:0-144)
0 // Right-half only — auto-mirrored by _build_ldraw()

0 // ── Chassis Base ──
0 STEP
1 7 20 8 60 1 0 0 0 1 0 0 0 1 3034.dat
1 7 20 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 60 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 40 8 160 1 0 0 0 1 0 0 0 1 3020.dat
1 7 40 8 20 1 0 0 0 1 0 0 0 1 3021.dat
1 7 40 8 300 1 0 0 0 1 0 0 0 1 3021.dat

0 // ── Chassis Frame ──
0 STEP
1 7 60 24 60 1 0 0 0 1 0 0 0 1 3460.dat
1 7 60 24 240 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 60 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 240 1 0 0 0 1 0 0 0 1 3460.dat

0 // ── Body Side ──
0 STEP
1 4 60 48 100 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 48 180 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 72 100 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 72 180 1 0 0 0 1 0 0 0 1 3010.dat
1 4 70 48 40 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 48 280 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 72 40 1 0 0 0 1 0 0 0 1 15068.dat
1 4 70 72 280 1 0 0 0 1 0 0 0 1 15068.dat
1 4 60 48 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 48 280 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 72 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 72 280 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Hood ──
0 STEP
1 4 40 80 280 1 0 0 0 1 0 0 0 1 3297.dat
1 4 40 80 240 1 0 0 0 1 0 0 0 1 87079.dat
1 0 40 80 300 1 0 0 0 1 0 0 0 1 30236.dat
1 4 40 88 260 1 0 0 0 1 0 0 0 1 3069b.dat
1 4 40 88 220 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Windshield ──
0 STEP
1 72 40 88 200 1 0 0 0 1 0 0 0 1 4176.dat
1 72 60 88 200 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Roof ──
0 STEP
1 4 40 104 180 1 0 0 0 1 0 0 0 1 87079.dat
1 4 40 104 140 1 0 0 0 1 0 0 0 1 87079.dat
1 4 40 104 100 1 0 0 0 1 0 0 0 1 30363.dat
1 4 40 104 60 1 0 0 0 1 0 0 0 1 3298.dat

0 // ── Rear Body ──
0 STEP
1 4 40 80 40 1 0 0 0 1 0 0 0 1 3298.dat
1 4 40 80 20 1 0 0 0 1 0 0 0 1 15068.dat
1 4 40 56 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 40 80 60 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Headlight ──
0 STEP
1 14 60 56 310 1 0 0 0 1 0 0 0 1 4070.dat
1 14 60 64 310 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 48 310 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Taillight ──
0 STEP
1 4 60 56 10 1 0 0 0 1 0 0 0 1 4070.dat
1 4 60 64 10 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 48 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Bumper ──
0 STEP
1 0 40 40 310 1 0 0 0 1 0 0 0 1 3043.dat
1 0 40 40 10 1 0 0 0 1 0 0 0 1 3043.dat
1 0 60 32 310 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 32 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Wheel Arch ──
0 STEP
1 0 60 24 60 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 60 24 260 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 70 24 80 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 70 24 240 0 0 1 0 1 0 -1 0 0 11477.dat

0 // ── Wheel ──
0 STEP
1 0 60 8 60 1 0 0 0 1 0 0 0 1 4624c00.dat
1 0 60 8 260 1 0 0 0 1 0 0 0 1 4624c00.dat

0 // ── Detail ──
0 STEP
1 0 60 56 160 1 0 0 0 1 0 0 0 1 4085.dat
1 0 60 64 160 1 0 0 0 1 0 0 0 1 2555.dat
1 0 40 24 20 1 0 0 0 1 0 0 0 1 4599.dat
1 0 40 88 160 1 0 0 0 1 0 0 0 1 2431.dat
1 0 40 96 120 1 0 0 0 1 0 0 0 1 2431.dat
"""

TEMPLATE_PICKUP = """0 // ===== PICKUP TRUCK TEMPLATE (Speed Champions 8-wide) =====
0 // Cab + open bed. Base for: Ford F-150, Toyota Hilux, Ram
0 // Dimensions: 16 studs long (Z:0-320), 8 wide (X:0-80 right half), 6 bricks tall (Y:0-144)
0 // Right-half only — auto-mirrored by _build_ldraw()

0 // ── Chassis Base ──
0 STEP
1 7 20 8 60 1 0 0 0 1 0 0 0 1 3034.dat
1 7 20 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 60 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 240 1 0 0 0 1 0 0 0 1 3034.dat
1 7 40 8 160 1 0 0 0 1 0 0 0 1 3020.dat
1 7 40 8 20 1 0 0 0 1 0 0 0 1 3021.dat
1 7 40 8 300 1 0 0 0 1 0 0 0 1 3021.dat

0 // ── Chassis Frame ──
0 STEP
1 7 60 24 60 1 0 0 0 1 0 0 0 1 3460.dat
1 7 60 24 240 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 60 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 240 1 0 0 0 1 0 0 0 1 3460.dat

0 // ── Body Side ──
0 STEP
1 4 60 48 100 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 48 180 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 72 100 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 72 180 1 0 0 0 1 0 0 0 1 3009.dat
1 4 70 48 40 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 48 280 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 72 40 1 0 0 0 1 0 0 0 1 15068.dat
1 4 70 72 280 1 0 0 0 1 0 0 0 1 15068.dat
1 4 60 48 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 72 40 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Cabin ──
0 STEP
1 4 60 96 120 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 120 120 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 96 180 1 0 0 0 1 0 0 0 1 3009.dat
1 4 60 120 180 1 0 0 0 1 0 0 0 1 3009.dat

0 // ── Windshield ──
0 STEP
1 72 40 128 190 1 0 0 0 1 0 0 0 1 4176.dat
1 72 60 128 190 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Roof ──
0 STEP
1 4 40 152 150 1 0 0 0 1 0 0 0 1 87079.dat
1 4 40 152 120 1 0 0 0 1 0 0 0 1 30363.dat

0 // ── Cargo Bed ──
0 STEP
1 4 40 80 40 1 0 0 0 1 0 0 0 1 3034.dat
1 0 60 72 40 1 0 0 0 1 0 0 0 1 3004.dat
1 0 60 96 40 1 0 0 0 1 0 0 0 1 3004.dat
1 0 40 80 20 1 0 0 0 1 0 0 0 1 3023.dat
1 0 40 96 20 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Hood ──
0 STEP
1 4 40 128 280 1 0 0 0 1 0 0 0 1 3297.dat
1 4 40 128 240 1 0 0 0 1 0 0 0 1 87079.dat
1 0 40 128 300 1 0 0 0 1 0 0 0 1 30236.dat

0 // ── Headlight ──
0 STEP
1 14 60 104 310 1 0 0 0 1 0 0 0 1 4070.dat
1 14 60 112 310 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 96 310 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Taillight ──
0 STEP
1 4 60 72 10 1 0 0 0 1 0 0 0 1 4070.dat
1 4 60 80 10 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 64 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Bumper ──
0 STEP
1 0 40 56 310 1 0 0 0 1 0 0 0 1 3043.dat
1 0 40 56 10 1 0 0 0 1 0 0 0 1 3043.dat

0 // ── Wheel Arch ──
0 STEP
1 0 60 24 60 0 0 1 0 1 0 -1 0 0 50950.dat
1 0 60 24 260 0 0 1 0 1 0 -1 0 0 50950.dat
1 0 70 24 80 0 0 1 0 1 0 -1 0 0 50950.dat
1 0 70 24 240 0 0 1 0 1 0 -1 0 0 50950.dat

0 // ── Wheel ──
0 STEP
1 0 60 8 60 1 0 0 0 1 0 0 0 1 56904c00.dat
1 0 60 8 260 1 0 0 0 1 0 0 0 1 56904c00.dat

0 // ── Detail ──
0 STEP
1 0 60 104 160 1 0 0 0 1 0 0 0 1 4085.dat
1 0 60 112 160 1 0 0 0 1 0 0 0 1 2555.dat
1 0 40 24 20 1 0 0 0 1 0 0 0 1 4599.dat
1 0 40 88 220 1 0 0 0 1 0 0 0 1 2431.dat
"""

TEMPLATE_HATCHBACK = """0 // ===== HATCHBACK TEMPLATE (Speed Champions 8-wide) =====
0 // Short rear overhang, steep rear window. Base for: Golf GTI, Mini Cooper, Civic Type R
0 // Dimensions: 14 studs long (Z:0-280), 8 wide (X:0-80 right half), 5 bricks tall (Y:0-120)
0 // Right-half only — auto-mirrored by _build_ldraw()

0 // ── Chassis Base ──
0 STEP
1 7 20 8 60 1 0 0 0 1 0 0 0 1 3034.dat
1 7 20 8 220 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 60 1 0 0 0 1 0 0 0 1 3034.dat
1 7 60 8 220 1 0 0 0 1 0 0 0 1 3034.dat
1 7 40 8 140 1 0 0 0 1 0 0 0 1 3020.dat
1 7 40 8 20 1 0 0 0 1 0 0 0 1 3021.dat
1 7 40 8 260 1 0 0 0 1 0 0 0 1 3021.dat

0 // ── Chassis Frame ──
0 STEP
1 7 60 24 60 1 0 0 0 1 0 0 0 1 3460.dat
1 7 60 24 220 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 60 1 0 0 0 1 0 0 0 1 3460.dat
1 7 20 24 220 1 0 0 0 1 0 0 0 1 3460.dat

0 // ── Body Side ──
0 STEP
1 4 60 48 80 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 48 160 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 72 80 1 0 0 0 1 0 0 0 1 3010.dat
1 4 60 72 160 1 0 0 0 1 0 0 0 1 3010.dat
1 4 70 48 40 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 48 240 1 0 0 0 1 0 0 0 1 3043.dat
1 4 70 72 40 1 0 0 0 1 0 0 0 1 15068.dat
1 4 70 72 240 1 0 0 0 1 0 0 0 1 15068.dat
1 4 60 48 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 48 240 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 72 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 72 240 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Hood ──
0 STEP
1 4 40 80 240 1 0 0 0 1 0 0 0 1 3297.dat
1 4 40 80 200 1 0 0 0 1 0 0 0 1 87079.dat
1 0 40 80 260 1 0 0 0 1 0 0 0 1 30236.dat
1 4 40 88 220 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Windshield ──
0 STEP
1 72 40 88 180 1 0 0 0 1 0 0 0 1 4176.dat
1 72 60 88 180 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Roof ──
0 STEP
1 4 40 104 140 1 0 0 0 1 0 0 0 1 30363.dat
1 4 40 104 100 1 0 0 0 1 0 0 0 1 3068b.dat

0 // ── Rear Body ──
0 STEP
1 4 40 80 40 1 0 0 0 1 0 0 0 1 3043.dat
1 4 40 80 20 1 0 0 0 1 0 0 0 1 15068.dat
1 4 40 56 40 1 0 0 0 1 0 0 0 1 3004.dat
1 4 40 80 60 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Headlight ──
0 STEP
1 14 60 56 270 1 0 0 0 1 0 0 0 1 4070.dat
1 14 60 64 270 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 48 270 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Taillight ──
0 STEP
1 4 60 56 10 1 0 0 0 1 0 0 0 1 4070.dat
1 4 60 64 10 1 0 0 0 1 0 0 0 1 6141.dat
1 0 60 48 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Bumper ──
0 STEP
1 0 40 40 270 1 0 0 0 1 0 0 0 1 3043.dat
1 0 40 40 10 1 0 0 0 1 0 0 0 1 3043.dat
1 0 60 32 270 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 32 10 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Wheel Arch ──
0 STEP
1 0 60 24 60 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 60 24 220 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 70 24 80 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 70 24 200 0 0 1 0 1 0 -1 0 0 11477.dat

0 // ── Wheel ──
0 STEP
1 0 60 8 60 1 0 0 0 1 0 0 0 1 4624c00.dat
1 0 60 8 220 1 0 0 0 1 0 0 0 1 4624c00.dat

0 // ── Detail ──
0 STEP
1 0 60 56 140 1 0 0 0 1 0 0 0 1 4085.dat
1 0 60 64 140 1 0 0 0 1 0 0 0 1 2555.dat
1 0 40 24 20 1 0 0 0 1 0 0 0 1 4599.dat
1 0 40 88 140 1 0 0 0 1 0 0 0 1 2431.dat
"""

TEMPLATE_F1_RACE = """0 // ===== F1 / OPEN-WHEEL RACE CAR TEMPLATE (Speed Champions 8-wide) =====
0 // Low, wide, open-wheel with rear wing. Base for: F1, Formula E, IndyCar
0 // Dimensions: 16 studs long (Z:0-320), 8 wide (X:0-80 right half), 4 bricks tall (Y:0-96)
0 // Right-half only — auto-mirrored by _build_ldraw()

0 // ── Chassis Base ──
0 STEP
1 7 20 8 40 1 0 0 0 1 0 0 0 1 3020.dat
1 7 20 8 140 1 0 0 0 1 0 0 0 1 3020.dat
1 7 20 8 240 1 0 0 0 1 0 0 0 1 3020.dat
1 7 60 8 40 1 0 0 0 1 0 0 0 1 3020.dat
1 7 60 8 140 1 0 0 0 1 0 0 0 1 3020.dat
1 7 60 8 240 1 0 0 0 1 0 0 0 1 3020.dat
1 7 40 8 80 1 0 0 0 1 0 0 0 1 3021.dat
1 7 40 8 200 1 0 0 0 1 0 0 0 1 3021.dat

0 // ── Nose Cone ──
0 STEP
1 4 40 16 300 1 0 0 0 1 0 0 0 1 3297.dat
1 4 40 24 280 1 0 0 0 1 0 0 0 1 3297.dat
1 4 40 32 260 1 0 0 0 1 0 0 0 1 15068.dat
1 4 40 24 270 1 0 0 0 1 0 0 0 1 3069b.dat

0 // ── Front Wing ──
0 STEP
1 0 40 16 310 1 0 0 0 1 0 0 0 1 3023.dat
1 0 40 8 310 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 16 310 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 8 310 1 0 0 0 1 0 0 0 1 3023.dat
1 0 40 16 316 0 0 1 0 1 0 -1 0 0 3665.dat
1 0 60 16 316 0 0 1 0 1 0 -1 0 0 3665.dat

0 // ── Sidepod ──
0 STEP
1 4 60 32 120 1 0 0 0 1 0 0 0 1 3298.dat
1 4 60 32 180 1 0 0 0 1 0 0 0 1 3298.dat
1 4 70 32 100 1 0 0 0 1 0 0 0 1 15068.dat
1 4 70 32 200 1 0 0 0 1 0 0 0 1 15068.dat
1 4 60 48 120 1 0 0 0 1 0 0 0 1 3004.dat
1 4 60 48 180 1 0 0 0 1 0 0 0 1 3004.dat

0 // ── Cockpit ──
0 STEP
1 4 40 56 160 1 0 0 0 1 0 0 0 1 30363.dat
1 4 40 64 140 1 0 0 0 1 0 0 0 1 3068b.dat
1 0 40 56 200 0 0 1 0 1 0 -1 0 0 3823.dat

0 // ── Halo ──
0 STEP
1 0 40 72 180 0 0 1 0 1 0 -1 0 0 3665.dat
1 0 60 72 180 0 0 1 0 1 0 -1 0 0 3665.dat
1 0 40 80 170 1 0 0 0 1 0 0 0 1 3023.dat

0 // ── Rear Wing ──
0 STEP
1 0 40 48 20 1 0 0 0 1 0 0 0 1 3023.dat
1 0 40 56 20 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 48 20 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 56 20 1 0 0 0 1 0 0 0 1 3023.dat
1 0 40 64 30 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 64 30 1 0 0 0 1 0 0 0 1 3023.dat
1 0 40 72 25 0 0 1 0 1 0 -1 0 0 3665.dat
1 0 60 72 25 0 0 1 0 1 0 -1 0 0 3665.dat

0 // ── Headlight ──
0 STEP
1 14 40 24 300 1 0 0 0 1 0 0 0 1 6141.dat
1 14 60 24 300 1 0 0 0 1 0 0 0 1 6141.dat

0 // ── Taillight ──
0 STEP
1 4 40 40 10 1 0 0 0 1 0 0 0 1 6141.dat
1 4 60 40 10 1 0 0 0 1 0 0 0 1 6141.dat

0 // ── Wheel Arch ──
0 STEP
1 0 60 24 60 0 0 1 0 1 0 -1 0 0 11477.dat
1 0 60 24 260 0 0 1 0 1 0 -1 0 0 11477.dat

0 // ── Wheel ──
0 STEP
1 0 60 8 60 1 0 0 0 1 0 0 0 1 4624c00.dat
1 0 60 8 260 1 0 0 0 1 0 0 0 1 4624c00.dat

0 // ── Detail ──
0 STEP
1 0 40 24 20 1 0 0 0 1 0 0 0 1 4599.dat
1 0 60 24 20 1 0 0 0 1 0 0 0 1 4599.dat
1 0 40 16 100 1 0 0 0 1 0 0 0 1 3023.dat
1 0 60 16 100 1 0 0 0 1 0 0 0 1 3023.dat
"""

# ── Template registry ───────────────────────────

CAR_TEMPLATES = {
    "sports_car": {
        "name": "Sports Car",
        "body_style": "sports_car",
        "ldr": TEMPLATE_SPORTS_CAR,
        "car_makes": [
            "Ferrari", "Lamborghini", "McLaren", "Porsche", "Bugatti",
            "Koenigsegg", "Pagani", "Aston Martin", "Lotus", "Maserati",
            "Alfa Romeo", "Corvette", "Dodge", "Jaguar", "Nissan",
            "Toyota Supra", "Honda NSX", "Lexus LC", "Shelby",
        ],
        "default_color": 4,  # Red
        "wheel_type": "4624c00",  # Standard sports
        "roof_style": "coupe",
    },
    "suv": {
        "name": "SUV / Off-Road",
        "body_style": "suv",
        "ldr": TEMPLATE_SUV,
        "car_makes": [
            "Land Rover", "Jeep", "Mercedes-Benz G", "Toyota Land Cruiser",
            "Ford Bronco", "Suzuki Jimny", "Hummer", "Mercedes-Benz",
        ],
        "default_color": 2,  # Green
        "wheel_type": "56904c00",  # Large off-road
        "roof_style": "wagon",
    },
    "sedan": {
        "name": "Sedan",
        "body_style": "sedan",
        "ldr": TEMPLATE_SEDAN,
        "car_makes": [
            "BMW", "Mercedes-Benz", "Audi", "Toyota", "Honda", "Volkswagen",
            "Hyundai", "Kia", "Tesla", "BYD", "Lexus", "Nissan",
            "Chevrolet", "Cadillac", "Genesis", "Volvo",
        ],
        "default_color": 1,  # Blue
        "wheel_type": "4624c00",
        "roof_style": "sedan",
    },
    "pickup": {
        "name": "Pickup Truck",
        "body_style": "pickup",
        "ldr": TEMPLATE_PICKUP,
        "car_makes": [
            "Ford", "Ram", "Chevrolet", "Toyota", "GMC", "Nissan",
        ],
        "default_color": 25,  # Orange
        "wheel_type": "56904c00",
        "roof_style": "cab",
    },
    "hatchback": {
        "name": "Hatchback",
        "body_style": "hatchback",
        "ldr": TEMPLATE_HATCHBACK,
        "car_makes": [
            "Volkswagen", "Honda", "Mini", "Ford", "Toyota",
            "Hyundai", "Renault", "Peugeot", "Fiat",
            "Suzuki", "Mazda",
        ],
        "default_color": 14,  # Yellow
        "wheel_type": "4624c00",
        "roof_style": "hatch",
    },
    "f1_race": {
        "name": "F1 / Open-Wheel Race Car",
        "body_style": "formula",
        "ldr": TEMPLATE_F1_RACE,
        "car_makes": [
            "Red Bull", "Mercedes-AMG", "Ferrari", "McLaren", "Aston Martin",
            "Alpine", "Williams", "Haas", "Sauber", "RB",
            "APXGP", "F1 Academy",
        ],
        "default_color": 4,  # Red
        "wheel_type": "4624c00",
        "roof_style": "open",
    },
}


def classify_car_to_template(make: str, body_style: str | None = None) -> str:
    """Map a car make to the closest body style template.

    Uses make matching first (from CAR_TEMPLATES registry), then falls back
    to body_style keyword matching, and finally defaults to sports_car.
    """
    make_lower = make.lower()

    # Fast path: F1 / Formula / Race team detection
    f1_keywords = ["f1", "formula", "racing", "grand prix", "f1 academy"]
    if any(kw in make_lower for kw in f1_keywords):
        return "f1_race"

    # Standard make matching
    for template_id, info in CAR_TEMPLATES.items():
        for car_make in info["car_makes"]:
            if car_make.lower() in make_lower or make_lower in car_make.lower():
                return template_id

    # Fallback based on body style
    if body_style:
        body_lower = body_style.lower()
        if "suv" in body_lower or "truck" in body_lower or "jeep" in body_lower or "off-road" in body_lower:
            return "suv"
        if "pickup" in body_lower:
            return "pickup"
        if "hatchback" in body_lower or "hatch" in body_lower:
            return "hatchback"
        if "sedan" in body_lower or "saloon" in body_lower:
            return "sedan"
        if "formula" in body_lower or "race" in body_lower or "open-wheel" in body_lower:
            return "f1_race"

    # Model-name heuristics for common patterns
    model_lower = make_lower
    if any(suv in model_lower for suv in ["land cruiser", "wrangler", "bronco", "defender", "g-wagon", "g 500", "g-class"]):
        return "suv"
    if any(pickup in model_lower for pickup in ["f-150", "silverado", "ram", "tacoma", "tundra"]):
        return "pickup"

    return "sports_car"  # default


def get_scale_spec(scale: str | None = None) -> dict:
    """Get the dimension spec for a scale. Falls back to DEFAULT_SCALE."""
    if scale and scale in SCALE_SPECS:
        return SCALE_SPECS[scale]
    return SCALE_SPECS[DEFAULT_SCALE]


def validate_scale(scale: str | None) -> str:
    """Validate and normalize a scale choice. Returns valid scale or DEFAULT_SCALE."""
    if scale and scale in SCALE_SPECS:
        return scale
    return DEFAULT_SCALE


def get_template_ldr(make: str, body_style: str | None = None, scale: str | None = None) -> str:
    """Get the appropriate base template LDraw for a car at the given scale."""
    template_id = classify_car_to_template(make, body_style)
    template = CAR_TEMPLATES.get(template_id, CAR_TEMPLATES["sports_car"])
    return template["ldr"]


def get_template_info(make: str, body_style: str | None = None) -> dict:
    """Get the template metadata dict for a car make."""
    template_id = classify_car_to_template(make, body_style)
    return CAR_TEMPLATES.get(template_id, CAR_TEMPLATES["sports_car"])


def format_scale_for_prompt(scale: str) -> str:
    """Build a concise scale dimension block for the AI prompt."""
    s = get_scale_spec(scale)
    return (
        f"## Scale: {scale}\n"
        f"- Dimensions (LDU): Z={s['length_ldu']}  X={s['width_ldu']}  Y={s['height_ldu']}\n"
        f"- Wheels: {s['wheel']}\n"
        f"- Target: {s['unique_parts'][0]}–{s['unique_parts'][1]} unique parts ({s['total_pieces'][0]}–{s['total_pieces'][1]} total pieces)\n"
        f"- Reference sets: {s['ref_sets']}\n"
        f"- {s['note']}"
    )
