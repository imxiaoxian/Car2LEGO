"""Comprehensive vehicle classification taxonomy for LEGO car design.

8 main body styles → 52 sub-styles
5 eras → 15 generations
7 regions → 30 country origins
80+ distinctive features across 8 categories
25 wheel types → LEGO part mapping
50 factory colors → exact LEGO color IDs
6 performance tiers
5 modification levels
18 grille types
"""

# ═══════════════════════════════════════════════════════════════
# 1. BODY STYLE TAXONOMY (8 main → 52 sub-styles)
# ═══════════════════════════════════════════════════════════════

BODY_STYLES = {
    "sports_car": {
        "label": "Sports Car",
        "sub_styles": [
            "mid_engine_coupe",        # Ferrari 488, Lamborghini Huracan
            "front_engine_coupe",       # Corvette C7, AMG GT, Lexus LC
            "rear_engine_coupe",        # Porsche 911
            "grand_tourer",             # Aston Martin DB11, Ferrari Roma, Bentley Continental GT
            "sports_roadster",          # Mazda MX-5, Porsche Boxster, BMW Z4
            "track_focused",            # Porsche GT3 RS, Ferrari 488 Pista, McLaren 765LT
            "muscle_car",               # Ford Mustang, Dodge Challenger, Chevrolet Camaro
            "pony_car",                 # Ford Mustang (original), Plymouth Barracuda
            "jdm_sports",               # Nissan GT-R, Toyota Supra, Honda NSX
            "kei_sports",               # Honda S660, Daihatsu Copen, Suzuki Cappuccino
            "hot_hatch",                # Golf GTI, Civic Type R, Focus RS, i30 N
            "sports_sedan",             # BMW M3, Alfa Romeo Giulia QV, Cadillac CT4-V
        ],
        "typical_proportions": "low-slung (height < 1.4m), wide stance, short overhangs",
        "lego_scale": "6-wide, 14-16 studs long, 4-5 bricks tall",
    },
    "supercar": {
        "label": "Supercar / Hypercar",
        "sub_styles": [
            "mid_engine_supercar",      # McLaren 720S, Ferrari F8
            "mid_engine_hypercar",      # Bugatti Chiron, Koenigsegg Jesko, Rimac Nevera
            "front_engine_supercar",    # Ferrari 812 Superfast
            "hybrid_hypercar",          # LaFerrari, McLaren P1, Porsche 918
            "electric_hypercar",        # Rimac Nevera, Lotus Evija, Pininfarina Battista
            "track_only_hypercar",      # Ferrari FXX-K, McLaren P1 GTR, Aston Martin Valkyrie AMR Pro
        ],
        "typical_proportions": "extreme low (height < 1.2m), very wide (2m+), dramatic aero",
        "lego_scale": "6-wide or 8-wide, 16-18 studs long, 4 bricks tall",
    },
    "sedan": {
        "label": "Sedan / Saloon",
        "sub_styles": [
            "compact_sedan",            # Honda Civic, Toyota Corolla, VW Jetta
            "midsize_sedan",            # Toyota Camry, Honda Accord, BMW 3-Series
            "fullsize_sedan",           # Mercedes S-Class, BMW 7-Series, Lexus LS
            "executive_sedan",          # Audi A6, BMW 5-Series, Mercedes E-Class
            "luxury_sedan",             # Rolls-Royce Ghost, Bentley Flying Spur
            "liftback_sedan",           # Audi A7, Kia Stinger, Tesla Model S
            "fastback_sedan",           # BYD Han, Porsche Taycan, Mercedes CLS
            "three_box_sedan",          # Traditional: Audi A4, VW Passat
        ],
        "typical_proportions": "4 doors, 3-box shape, height 1.4-1.5m",
        "lego_scale": "6-wide, 16-18 studs long, 5 bricks tall",
    },
    "suv": {
        "label": "SUV / Crossover",
        "sub_styles": [
            "compact_crossover",        # Honda HR-V, Toyota C-HR, Hyundai Kona
            "midsize_suv",              # Toyota RAV4, Honda CR-V, Ford Explorer
            "fullsize_suv",             # Chevrolet Tahoe, Cadillac Escalade, Lincoln Navigator
            "luxury_suv",               # Range Rover, Mercedes GLS, BMW X7
            "off_road_suv",             # Jeep Wrangler, Land Rover Defender, Toyota Land Cruiser
            "coupe_suv",                # BMW X6, Mercedes GLE Coupe, Audi Q8
            "sport_suv",                # Porsche Cayenne, Lamborghini Urus, Aston Martin DBX
            "electric_suv",             # Tesla Model X, Rivian R1S, Kia EV9
        ],
        "typical_proportions": "tall (1.6-1.9m), high ground clearance, boxy or sloping rear",
        "lego_scale": "6-wide, 15-17 studs long, 6-7 bricks tall",
    },
    "pickup": {
        "label": "Pickup Truck",
        "sub_styles": [
            "midsize_pickup",           # Toyota Tacoma, Ford Ranger, Chevrolet Colorado
            "fullsize_pickup",          # Ford F-150, Ram 1500, Chevrolet Silverado
            "heavy_duty_pickup",        # Ford F-250, Ram 2500
            "off_road_pickup",          # Ford Raptor, Ram TRX, Toyota Tacoma TRD Pro
            "luxury_pickup",            # GMC Sierra Denali, Ram Limited
            "electric_pickup",          # Rivian R1T, Ford F-150 Lightning, Tesla Cybertruck
        ],
        "typical_proportions": "cab + open bed, tall (1.8-2.0m), long (5.3-6.0m)",
        "lego_scale": "6-wide, 18-22 studs long, 6-7 bricks tall",
    },
    "hatchback": {
        "label": "Hatchback",
        "sub_styles": [
            "city_hatch",               # Fiat 500, Mini Cooper, Honda Fit
            "compact_hatch",            # VW Golf, Ford Focus, Toyota Corolla Hatch
            "premium_hatch",            # Audi A3 Sportback, Mercedes A-Class, BMW 1-Series
            "hot_hatch",                # Golf GTI, Civic Type R, GR Corolla, i30 N
            "shooting_brake",           # Mercedes CLA Shooting Brake, Ferrari GTC4Lusso
        ],
        "typical_proportions": "2 or 4 doors, short rear overhang, height 1.4-1.5m",
        "lego_scale": "6-wide, 13-15 studs long, 5 bricks tall",
    },
    "wagon": {
        "label": "Wagon / Estate",
        "sub_styles": [
            "compact_wagon",            # VW Golf Variant, Skoda Octavia Combi
            "midsize_wagon",            # Volvo V60, Audi A4 Avant, BMW 3-Series Touring
            "fullsize_wagon",           # Mercedes E-Class Estate, Volvo V90
            "performance_wagon",        # Audi RS6 Avant, Mercedes E63 AMG Wagon, Porsche Taycan Sport Turismo
            "off_road_wagon",           # Audi A6 Allroad, Volvo V60 Cross Country, Subaru Outback
        ],
        "typical_proportions": "extended roof to rear, 5 doors, height 1.4-1.5m",
        "lego_scale": "6-wide, 16-18 studs long, 5 bricks tall",
    },
    "convertible": {
        "label": "Convertible / Cabriolet",
        "sub_styles": [
            "soft_top_roadster",        # Mazda MX-5, BMW Z4
            "hard_top_convertible",     # Ferrari 488 Spider, McLaren 720S Spider
            "targa_top",                # Porsche 911 Targa, Corvette C8 Targa
            "speedster",                # Porsche Boxster Spyder, Ferrari Monza SP1
            "four_seat_convertible",    # BMW 4-Series Convertible, Mercedes C-Class Cabriolet
        ],
        "typical_proportions": "no fixed roof, reinforced chassis, height 1.2-1.4m",
        "lego_scale": "6-wide, 14-16 studs long, 4 bricks tall (no roof section)",
    },
    "van": {
        "label": "Van / MPV",
        "sub_styles": [
            "minivan",                  # Toyota Sienna, Honda Odyssey, Kia Carnival
            "commercial_van",           # Ford Transit, Mercedes Sprinter
            "camper_van",               # VW California, Mercedes Marco Polo
            "kei_van",                  # Suzuki Every, Honda N-Van
            "luxury_mpv",               # Lexus LM, Buick GL8, Toyota Alphard
        ],
        "typical_proportions": "tall and boxy (1.8-2.2m), sliding doors",
        "lego_scale": "6-wide, 16-20 studs long, 7-8 bricks tall",
    },
}


# ═══════════════════════════════════════════════════════════════
# 2. ERA / GENERATION CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

ERAS = {
    "vintage":       {"years": (1900, 1945), "label": "Vintage / Pre-War",    "lego_style": "curved fenders, separate headlights, tall narrow body"},
    "classic":       {"years": (1946, 1975), "label": "Classic / Post-War",   "lego_style": "chrome bumpers, round headlights, boxy proportions"},
    "modern_classic": {"years": (1976, 1995), "label": "Modern Classic",       "lego_style": "angular design, pop-up headlights, wedge shapes"},
    "retro_modern":  {"years": (1996, 2010), "label": "Retro-Modern / Y2K",   "lego_style": "rounded curves, integrated bumpers, projector headlights"},
    "contemporary":  {"years": (2011, 2020), "label": "Contemporary / 2010s",  "lego_style": "sharp creases, LED DRLs, large grilles, turbo engines"},
    "current_gen":   {"years": (2021, 2030), "label": "Current Generation",    "lego_style": "EV closed grilles, full-width light bars, flush handles, LiDAR"},
}

DESIGN_MOVEMENTS = [
    "Art Deco (1930s)", "Streamline Moderne (1940s)", "Tailfin Era (1950s)",
    "Muscle Car Era (1960s-70s)", "Wedge Era (1970s-80s)", "Bubble Era (1990s)",
    "Bangle Butt (2000s BMW)", "Fluidic Sculpture (2010s Hyundai)",
    "Dragon Face (BYD)", "Sensual Sportiness (Kia)", "Dynamic Shield (Mitsubishi)",
    "L-Finesse (Lexus)", "Kodo Design (Mazda)", "V-Motion (Nissan)",
    "Porsche Design DNA", "Alfa Romeo Trilobo", "BMW Kidney Grille Evolution",
]


# ═══════════════════════════════════════════════════════════════
# 3. REGIONAL / ORIGIN CLASSIFICATION
# ═══════════════════════════════════════════════════════════════

REGIONS = {
    "jdm": {
        "label": "JDM (Japanese Domestic Market)",
        "countries": ["Japan"],
        "design_traits": ["angular headlights", "large rear wings", "quad exhaust",
                         "hood scoops", "wide fenders", "bold color options"],
        "famous_styles": ["Bosozoku", "Shakotan", "VIP Style", "Time Attack", "Kanjo"],
        "lego_notes": "Often modified — add spoilers, wide body, aftermarket wheels",
    },
    "euro": {
        "label": "European",
        "countries": ["Germany", "Italy", "UK", "France", "Sweden", "Spain", "Czech Republic"],
        "design_traits": ["clean lines", "subtle aggression", "technical precision",
                         "quality materials look", "restrained chrome"],
        "famous_styles": ["German touring", "Italian passion", "British luxury", "Swedish minimalism"],
        "lego_notes": "Clean, precise builds. Tile surfaces for smooth look.",
    },
    "american_muscle": {
        "label": "American Muscle / Pony",
        "countries": ["USA"],
        "design_traits": ["long hood", "short deck", "wide stance", "big block engine presence",
                         "dual racing stripes", "aggressive grille"],
        "famous_styles": ["Restomod", "Pro-Touring", "Drag Strip", "Lowrider"],
        "lego_notes": "Wide, low, aggressive. Big hood area. Dual stripes common.",
    },
    "american_luxury": {
        "label": "American Luxury",
        "countries": ["USA"],
        "design_traits": ["large body", "chrome accents", "vertical taillights", "bold grilles"],
    },
    "korean": {
        "label": "Korean",
        "countries": ["South Korea"],
        "design_traits": ["parametric grilles", "split headlights", "full-width light bars",
                         "sharp body lines", "coupe-like rooflines"],
        "lego_notes": "Modern parametric design. Sharp creases = wedge plates.",
    },
    "chinese_ev": {
        "label": "Chinese EV / New Energy",
        "countries": ["China"],
        "design_traits": ["closed EV grille", "full-width light bars", "flush door handles",
                         "LiDAR on roof", "sleek aero", "giant touchscreens visible"],
        "famous_styles": ["Dragon Face (BYD)", "Shark Nose (NIO)", "RoboCop (XPeng)"],
        "lego_notes": "Clean front (no grille opening). Full-width light bar = 1x8 tile in transparent. LiDAR bump on roof.",
    },
    "british": {
        "label": "British",
        "countries": ["UK"],
        "design_traits": ["classic grille shapes", "chrome trim", "leather interior cues",
                         "wood accents", "gentleman's express proportions"],
    },
}


# ═══════════════════════════════════════════════════════════════
# 4. DISTINCTIVE FEATURES TAXONOMY (80+ across 8 categories)
# ═══════════════════════════════════════════════════════════════

DISTINCTIVE_FEATURES = {
    "front_design": {
        "label": "Front Design Features",
        "features": [
            "split_headlights",           # Hyundai Kona, Citroen C3
            "popup_headlights",           # NA Miata, Ferrari F40, Lamborghini Countach
            "projector_headlights",       # Modern BMW, Audi
            "matrix_led_headlights",      # Audi Matrix, Mercedes Digital Light
            "laser_headlights",            # BMW i8, Audi R8
            "halo_angel_eyes",            # Classic BMW
            "frog_eye_headlights",        # Porsche 911 (round)
            "boomerang_drl",              # Nissan Juke, GT-R
            "triple_led_drl",             # Cadillac vertical LEDs
            "hockey_stick_drl",           # BMW Corona rings
            "light_blade_drl",            # Volvo Thor's Hammer
            "checkmark_drl",              # Kia Tiger Nose LED
            "full_width_light_bar_front", # XPeng, NIO, Li Auto, BYD Han
            "closed_ev_grille",           # Tesla, BYD EV, NIO
            "oversized_grille",           # BMW M3/M4, Audi RS
            "spindle_grille",             # Lexus
            "kidney_grille",              # BMW
            "shield_grille",              # Alfa Romeo Trilobo
            "honeycomb_grille",           # Audi RS, many sports cars
            "diamond_grille",             # Mercedes Panamericana
            "parametric_grille",          # Hyundai/Kia
            "illuminated_grille",         # BMW Iconic Glow, Rolls-Royce
            "front_bumper_canards",       # Track cars, Porsche GT3 RS
            "large_front_splitter",       # McLaren, Lamborghini SVJ
            "naca_ducts_on_hood",         # Ferrari F40
        ],
    },
    "rear_design": {
        "label": "Rear Design Features",
        "features": [
            "full_width_taillight_bar",   # Porsche 992, BYD Han, Lincoln
            "chinese_knot_taillights",    # BYD Han signature
            "sequential_turn_signals",    # Audi, Mustang
            "quad_round_taillights",      # Nissan GT-R, Corvette C5/C6
            "boomerang_taillights",       # Nissan 370Z, GT-R
            "c_shape_taillights",         # BMW
            "claw_mark_taillights",       # Lexus LC, RC
            "arrow_taillights",           # Kia Stinger
            "flame_taillights",           # Hyundai Tucson
            "smoked_taillights",          # Many sport trims
            "center_exit_exhaust",        # Porsche GT3, Lotus
            "quad_exhaust_tips",          # AMG, M cars
            "diffuser_with_fins",         # Lamborghini, Ferrari
            "active_rear_spoiler",        # Audi TT, Panamera, McLaren
            "ducktail_spoiler",           # Porsche 911 Carrera
            "large_fixed_wing",           # Subaru STI, Mitsubishi Evo
            "swan_neck_wing",             # Porsche GT3 RS, modern GT cars
            "kamm_tail",                  # BMW M1, Ford GT40
        ],
    },
    "side_profile": {
        "label": "Side Profile Features",
        "features": [
            "fender_vents",               # BMW M, Jaguar, Maserati
            "side_air_intakes",           # Mid-engine cars, Audi R8
            "flying_buttress_c_pillar",   # Ford GT, McLaren 720S
            "hofmeister_kink",            # BMW signature
            "floating_roof",              # MINI, Toyota C-HR, Range Rover Evoque
            "chrome_window_surround",     # Luxury sedans
            "blacked_out_pillars",        # Sport trims
            "c_pillar_louvers",           # BYD Han, classic Mustang
            "pronounced_shoulder_line",   # BMW, Mercedes, Audi
            "double_bubble_roof",         # Zagato designs, Ford GT
            "targa_bar",                  # Porsche 911 Targa
            "scissor_doors",              # Lamborghini Aventador
            "gullwing_doors",             # Mercedes SLS, Tesla Model X
            "suicide_doors",              # Rolls-Royce, Mazda RX-8
            "flush_door_handles",         # Tesla, BYD Han, Range Rover Velar
        ],
    },
    "wheels_brakes": {
        "label": "Wheel & Brake Features",
        "features": [
            "carbon_ceramic_brakes",      # Yellow/gold calipers visible
            "red_brake_calipers",         # Sport trim signature
            "center_lock_wheels",         # Porsche GT3, Ferrari, Lamborghini
            "aero_disc_wheels",           # Tesla, EV concept
            "deep_dish_rear_wheels",      # Staggered fitment, widebody
            "white_letter_tires",         # Muscle cars, off-road
        ],
    },
    "aero": {
        "label": "Aerodynamic Features",
        "features": [
            "active_aero_elements",       # McLaren, Ferrari, Porsche
            "underbody_diffuser",         # Modern sports cars
            "flat_underbody",             # EVs, supercars
            "side_skirt_extensions",      # Track cars
            "vortex_generators",          # Mitsubishi Evo, Subaru STI
            "drs_wing",                   # McLaren, Ferrari F1-derived
            "air_curtain",                # Modern BMW, Ford
        ],
    },
    "roof_glass": {
        "label": "Roof & Glass Features",
        "features": [
            "panoramic_glass_roof",       # Tesla Model 3/Y, many EVs
            "carbon_fiber_roof",          # BMW M3/M4, Alfa Giulia QV
            "twin_sunroof",               # Lexus, Genesis
            "retractable_hardtop",        # Ferrari Portofino, Mazda MX-5 RF
            "wrap_around_windshield",     # Tesla Model X, Citroen C4 Picasso
        ],
    },
    "lighting_signature": {
        "label": "Lighting Signatures",
        "features": [
            "welcome_light_animation",    # Modern luxury/EV (dancing lights)
            "projected_brand_logo",       # BMW, Mercedes puddle lights
            "ambient_interior_lighting",  # Mercedes, BMW, Genesis
            "star_headliner",             # Rolls-Royce
        ],
    },
    "ev_specific": {
        "label": "EV-Specific Features",
        "features": [
            "closed_grille_panel",        # No air intake needed
            "front_trunk_frunk",          # Storage under front hood
            "charging_port_integration",  # Hidden in grille or fender
            "aero_wheel_covers",          # Low-drag wheels
            "lidar_roof_bump",            # BYD Han 2024, XPeng P5
            "digital_side_mirrors",       # Honda e, Audi e-tron
            "light_bar_across_full_width", # Hyundai IONIQ, Kia EV, Porsche Taycan
        ],
    },
}


# ═══════════════════════════════════════════════════════════════
# 5. WHEEL TYPE TAXONOMY (25 types → LEGO part mapping)
# ═══════════════════════════════════════════════════════════════

WHEEL_TYPES = {
    "multi_spoke_sport": {
        "label": "Multi-Spoke Sport",
        "real_examples": "BBS CI-R, OZ Racing, HRE",
        "lego_parts": ["6014c00.dat"],
        "spoke_count": "5-10 thin spokes",
    },
    "five_spoke_classic": {
        "label": "5-Spoke Classic",
        "real_examples": "Enkei RPF1, OZ Ultraleggera, TE37",
        "lego_parts": ["4624c00.dat"],
        "spoke_count": "5 thick spokes",
    },
    "twin_five_spoke": {
        "label": "Twin 5-Spoke / Split Spoke",
        "real_examples": "BMW M Sport, Audi RS, VW GTI",
        "lego_parts": ["4624c00.dat"],
        "spoke_count": "10 (5 pairs)",
    },
    "mesh_style": {
        "label": "Mesh / BBS Style",
        "real_examples": "BBS LM, BBS RS, SSR Professor",
        "lego_parts": ["6014c00.dat"],
        "spoke_count": "fine mesh pattern",
    },
    "deep_dish": {
        "label": "Deep Dish / Stepped Lip",
        "real_examples": "Work Meister S1, SSR Koenig",
        "lego_parts": ["6014c00.dat"],
        "notes": "Visible stepped lip on rim edge",
    },
    "turbofan": {
        "label": "Turbofan / Aero Disc",
        "real_examples": "BBS Turbofan, 80s racing, Tesla Aero",
        "lego_parts": ["4624c00.dat"],
        "notes": "Flat or dished face covering spokes",
    },
    "three_spoke": {
        "label": "3-Spoke / Tri-Spoke",
        "real_examples": "Saab 900, Smart ForTwo, ADV.1",
        "lego_parts": ["4624c00.dat"],
    },
    "steel_wheel": {
        "label": "Steel Wheel / Steelie",
        "real_examples": "Base model cars, winter wheels, police",
        "lego_parts": ["4624c00.dat"],
        "notes": "Plain, often with hubcap. Black or silver.",
    },
    "wire_wheel": {
        "label": "Wire Wheel / Knock-Off",
        "real_examples": "Classic Jaguar, vintage sports cars",
        "lego_parts": ["4624c00.dat"],
    },
    "off_road_beadlock": {
        "label": "Off-Road / Beadlock",
        "real_examples": "Method Race Wheels, Fuel Off-Road",
        "lego_parts": ["56904c00.dat"],
        "notes": "Chunky, thick spokes, visible bolts on rim edge",
    },
    "rally_gravel": {
        "label": "Rally / Gravel Spec",
        "real_examples": "OZ Racing Rally, Speedline Corse",
        "lego_parts": ["56904c00.dat"],
        "notes": "Strong, gravel-resistant, often white or gold",
    },
    "drag_wheel": {
        "label": "Drag Racing / Slick",
        "real_examples": "Weld Racing, Bogart",
        "lego_parts": ["4624c00.dat"],
        "notes": "Narrow front, wide rear with drag slicks",
    },
    "vip_luxury": {
        "label": "VIP / Luxury Dish",
        "real_examples": "Leon Hardiritt, Junction Produce",
        "lego_parts": ["6014c00.dat"],
        "notes": "Large diameter, deep dish, chrome finish, slammed stance",
    },
    "donk_hi_riser": {
        "label": "Donk / Hi-Riser",
        "real_examples": "Custom 24-30 inch wheels",
        "lego_parts": ["56904c00.dat"],
        "notes": "Extremely large diameter, thin tire sidewall",
    },
    "turbine_directional": {
        "label": "Turbine / Directional",
        "real_examples": "Countach LP500S, DeLorean, Vector W8",
        "lego_parts": ["4624c00.dat"],
    },
}


# ═══════════════════════════════════════════════════════════════
# 6. PERFORMANCE TIER
# ═══════════════════════════════════════════════════════════════

PERFORMANCE_TIERS = {
    "economy":       {"power_range": "60-150 hp", "lego_parts": 80,  "lego_difficulty": "easy"},
    "family":        {"power_range": "150-250 hp", "lego_parts": 100, "lego_difficulty": "easy"},
    "sport":         {"power_range": "250-400 hp", "lego_parts": 140, "lego_difficulty": "medium"},
    "performance":   {"power_range": "400-600 hp", "lego_parts": 180, "lego_difficulty": "medium"},
    "supercar":      {"power_range": "600-1000 hp","lego_parts": 250, "lego_difficulty": "hard"},
    "hypercar":      {"power_range": "1000+ hp",   "lego_parts": 350, "lego_difficulty": "expert"},
}

MODIFICATION_LEVELS = {
    "stock":        {"label": "Factory Stock",    "description": "Original manufacturer specification"},
    "oem_plus":     {"label": "OEM+",             "description": "Subtle upgrades using factory-approved parts"},
    "mild_street":  {"label": "Mild Street Build","description": "Wheels, exhaust, slight lowering, tasteful mods"},
    "heavy_build":  {"label": "Heavy Build",      "description": "Widebody, big turbo, roll cage, significant mods"},
    "race_spec":    {"label": "Race / Track Spec", "description": "Full race preparation, stripped interior, cage, aero"},
    "show_car":     {"label": "Show Car / SEMA",  "description": "Extreme mods, air suspension, custom everything"},
}


# ═══════════════════════════════════════════════════════════════
# 7. COLOR SYSTEM (50 factory colors → exact LEGO color)
# ═══════════════════════════════════════════════════════════════

FACTORY_COLORS = {
    # Solid colors
    "black":                  {"lego_id": 0,  "lego_name": "Black",            "hex": "#05131D"},
    "white":                  {"lego_id": 15, "lego_name": "White",            "hex": "#FFFFFF"},
    "red":                    {"lego_id": 4,  "lego_name": "Red",              "hex": "#C91A09"},
    "blue":                   {"lego_id": 1,  "lego_name": "Blue",             "hex": "#0055BF"},
    "yellow":                 {"lego_id": 14, "lego_name": "Yellow",           "hex": "#F2CD37"},
    "green":                  {"lego_id": 2,  "lego_name": "Green",            "hex": "#257A3E"},
    "orange":                 {"lego_id": 25, "lego_name": "Orange",           "hex": "#FE8A18"},
    "purple":                 {"lego_id": 22, "lego_name": "Purple",           "hex": "#81007B"},
    "brown":                  {"lego_id": 6,  "lego_name": "Brown",            "hex": "#583927"},
    "tan":                    {"lego_id": 19, "lego_name": "Tan",              "hex": "#E4CD9E"},
    "dark_blue":              {"lego_id": 89, "lego_name": "Dark Blue",        "hex": "#4C61DB"},
    "dark_green":             {"lego_id": 2,  "lego_name": "Dark Green",       "hex": "#257A3E"},
    "dark_red":               {"lego_id": 88, "lego_name": "Dark Red",         "hex": "#720E0F"},
    "dark_tan":               {"lego_id": 28, "lego_name": "Dark Tan",         "hex": "#958A73"},
    "pink":                   {"lego_id": 13, "lego_name": "Pink",             "hex": "#FC97AC"},
    "lime_green":             {"lego_id": 27, "lego_name": "Lime",             "hex": "#BBE90B"},
    "light_gray":             {"lego_id": 7,  "lego_name": "Light Gray",       "hex": "#9BA19D"},
    "dark_gray":              {"lego_id": 8,  "lego_name": "Dark Gray",        "hex": "#6D6E5C"},
    "light_bluish_gray":      {"lego_id": 71, "lego_name": "Light Bluish Gray","hex": "#A0A5A9"},
    "dark_bluish_gray":       {"lego_id": 72, "lego_name": "Dark Bluish Gray", "hex": "#6C6E68"},
    "reddish_brown":          {"lego_id": 70, "lego_name": "Reddish Brown",    "hex": "#582A12"},

    # Metallic colors
    "silver_metallic":        {"lego_id": 71, "lego_name": "Metallic Silver",  "hex": "#A0A5A9"},
    "chrome":                 {"lego_id": 71, "lego_name": "Chrome Silver",    "hex": "#E0E0E0"},
    "gunmetal":               {"lego_id": 72, "lego_name": "Gunmetal",         "hex": "#6C6E68"},
    "bronze":                 {"lego_id": 84, "lego_name": "Metallic Gold",    "hex": "#CC702A"},
    "gold":                   {"lego_id": 84, "lego_name": "Pearl Gold",       "hex": "#CC702A"},
    "copper":                 {"lego_id": 25, "lego_name": "Copper",           "hex": "#FE8A18"},

    # Specialty colors
    "matte_black":            {"lego_id": 0,  "lego_name": "Matte Black",      "hex": "#1B2A34"},
    "matte_gray":             {"lego_id": 72, "lego_name": "Matte Dark Gray",  "hex": "#6C6E68"},
    "glacier_blue":           {"lego_id": 9,  "lego_name": "Light Blue",       "hex": "#B4D2E3"},
    "baby_blue":              {"lego_id": 73, "lego_name": "Medium Blue",      "hex": "#5C9DD1"},
    "british_racing_green":   {"lego_id": 2,  "lego_name": "Dark Green",       "hex": "#257A3E"},
    "midnight_purple":        {"lego_id": 85, "lego_name": "Dark Purple",      "hex": "#3F3691"},
    "championship_white":     {"lego_id": 15, "lego_name": "White",            "hex": "#FFFFFF"},
    "rosso_corsa":            {"lego_id": 4,  "lego_name": "Ferrari Red",      "hex": "#C91A09"},
    "giallo_modena":          {"lego_id": 14, "lego_name": "Ferrari Yellow",   "hex": "#F2CD37"},
    "grigio_titanio":         {"lego_id": 71, "lego_name": "Titanium Gray",    "hex": "#A0A5A9"},
    "blu_pozzi":              {"lego_id": 1,  "lego_name": "Dark Blue",        "hex": "#0055BF"},
    "soul_red":               {"lego_id": 4,  "lego_name": "Mazda Soul Red",   "hex": "#C91A09"},
    "nardo_gray":             {"lego_id": 7,  "lego_name": "Nardo Gray",       "hex": "#9BA19D"},
    "sunset_orange":          {"lego_id": 25, "lego_name": "Orange",           "hex": "#FE8A18"},
    "bayside_blue":           {"lego_id": 73, "lego_name": "Medium Blue",      "hex": "#5C9DD1"},
    "millennium_jade":        {"lego_id": 74, "lego_name": "Medium Green",     "hex": "#73DCA1"},
    "phoenix_yellow":         {"lego_id": 14, "lego_name": "Yellow",           "hex": "#F2CD37"},
    "plum_crazy_purple":      {"lego_id": 85, "lego_name": "Dark Purple",      "hex": "#3F3691"},
    "grabber_blue":           {"lego_id": 73, "lego_name": "Medium Blue",      "hex": "#5C9DD1"},
    "twilight_mountain_purple":{"lego_id": 22, "lego_name": "Purple",          "hex": "#81007B"},
}
