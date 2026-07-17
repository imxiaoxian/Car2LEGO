"""Seed the car_specs knowledge base with 50+ popular car models.

Run: python data/seed_car_specs.py

Covers Ferrari, Lamborghini, Porsche, McLaren, Bugatti, BMW, Mercedes-AMG,
Audi, Nissan, Toyota, Honda — the most commonly requested brands for
Speed Champions-style LEGO models.

All specs sourced from public manufacturer/Wikipedia data (2020-2024 models).
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.car_spec import CarSpec


# ── Car specifications ──────────────────────────
# Format: (make, model, year, body_style, length, width, height, wheelbase,
#          engine, drive, hp, top_speed, features[], colors[], body_proportions)

SEED_SPECS: list[tuple] = [
    # ═══ Ferrari ═══
    ("Ferrari", "F40", 1992, "sports_car", 4430, 1980, 1120, 2450,
     "2.9L Twin-Turbo V8", "RWD", 478, 324,
     ["pop-up headlights", "rear wing", "triple exhaust", "slatted engine cover"],
     ["Red", "Black", "Yellow"],
     "rear-engine, low wide wedge, large fixed rear wing, pop-up headlights"),
    ("Ferrari", "488 GTB", 2016, "sports_car", 4568, 1952, 1213, 2650,
     "3.9L Twin-Turbo V8", "RWD", 670, 330,
     ["aerodynamic S-duct", "side air intakes", "quad exhaust", "flying buttress rear"],
     ["Red", "Black", "Silver", "Yellow"],
     "mid-engine, aerodynamic S-duct front, side intakes, slim LED taillights"),
    ("Ferrari", "LaFerrari", 2015, "sports_car", 4702, 1992, 1116, 2665,
     "6.3L V12 Hybrid", "RWD", 963, 350,
     ["active aerodynamics", "split rear wing", "diverging side intakes", "low nose"],
     ["Red", "Black"],
     "mid-engine hypercar, sharp wedge profile, active aero, divergent side intakes"),
    ("Ferrari", "SF90 Stradale", 2021, "sports_car", 4710, 1972, 1186, 2650,
     "4.0L Twin-Turbo V8 Hybrid", "AWD", 1000, 340,
     ["T-shaped taillight bar", "split front intakes", "active rear wing", "aero bridge"],
     ["Red", "Black", "Yellow"],
     "plug-in hybrid hypercar, sharp angular body, full-width T-shape taillight"),
    ("Ferrari", "812 Superfast", 2018, "sports_car", 4618, 1972, 1273, 2650,
     "6.5L V12", "RWD", 800, 340,
     ["quad exhaust", "side air intakes", "low aggressive front", "aerodynamic bridge"],
     ["Red", "Black", "Silver"],
     "front-engine V12, long hood, quad exhaust, aggressive front splitter"),

    # ═══ Lamborghini ═══
    ("Lamborghini", "Huracán", 2019, "sports_car", 4520, 1933, 1165, 2620,
     "5.2L V10", "AWD", 640, 325,
     ["hexagonal design", "Y-shape LED headlights", "quad exhaust", "sharp angular body"],
     ["Green", "Yellow", "Orange", "Black"],
     "mid-engine, wedge profile, Y-shape headlights, hexagonal design motifs"),
    ("Lamborghini", "Aventador", 2018, "sports_car", 4775, 2030, 1136, 2700,
     "6.5L V12", "AWD", 770, 350,
     ["scissor doors", "hexagonal exhaust", "Y-shape headlights", "large rear wing"],
     ["Green", "Orange", "Black", "Silver"],
     "mid-engine, extreme wedge, scissor doors, hexagonal exhaust tips"),
    ("Lamborghini", "Countach", 1988, "sports_car", 4215, 2000, 1070, 2500,
     "5.2L V12", "RWD", 455, 295,
     ["scissor doors", "periscope roof intake", "triple rectangular taillights", "sharp wedge"],
     ["Red", "White", "Yellow"],
     "rear-engine, extreme wedge, scissor doors, periscope roof scoop"),
    ("Lamborghini", "Diablo", 1999, "sports_car", 4460, 2040, 1105, 2640,
     "5.7L V12", "AWD", 530, 325,
     ["scissor doors", "retractable headlights", "wide rear", "hexagonal intake"],
     ["Yellow", "Orange", "Purple"],
     "rear-engine, wedge profile, pop-up headlights, wide rear hips"),
    ("Lamborghini", "Murciélago", 2008, "sports_car", 4636, 2058, 1135, 2665,
     "6.5L V12", "AWD", 670, 342,
     ["scissor doors", "pop-up air intakes", "large rear wing", "single exhaust"],
     ["Yellow", "Orange", "Black", "Green"],
     "mid-engine, aggressive wide body, scissor doors, active side intakes"),

    # ═══ Porsche ═══
    ("Porsche", "911 GT3", 2023, "sports_car", 4573, 1852, 1279, 2457,
     "4.0L Flat-6", "RWD", 502, 318,
     ["round headlights", "rear wing", "center exhaust", "wide rear haunches"],
     ["White", "Silver", "Black", "Yellow", "Red"],
     "rear-engine, sloping roofline, wide rear haunches, swan-neck rear wing"),
    ("Porsche", "918 Spyder", 2015, "sports_car", 4643, 1940, 1167, 2730,
     "4.6L V8 Hybrid", "AWD", 887, 345,
     ["top-pipe exhaust", "active rear wing", "spyder roof", "aero blades"],
     ["Silver", "Black", "White"],
     "mid-engine hypercar, top-exit exhaust pipes, black aero blades"),
    ("Porsche", "Taycan", 2022, "sports_car", 4963, 1966, 1379, 2900,
     "Dual Electric Motors", "AWD", 750, 260,
     ["four-point headlights", "sloping roofline", "full-width taillight bar", "no grille"],
     ["White", "Black", "Silver", "Blue"],
     "electric sedan-coupe, four-point LED headlights, continuous taillight bar"),
    ("Porsche", "Cayman", 2022, "sports_car", 4379, 1801, 1295, 2475,
     "2.0L Flat-4", "RWD", 300, 275,
     ["sloping roofline", "side intakes", "round headlights", "low stance"],
     ["Yellow", "White", "Black", "Silver"],
     "mid-engine, balanced coupe, side air intakes behind doors"),
    ("Porsche", "718 Boxster", 2021, "sports_car", 4379, 1801, 1281, 2475,
     "2.0L Flat-4", "RWD", 300, 275,
     ["convertible soft-top", "side intakes", "round headlights", "four-point taillights"],
     ["Red", "White", "Black", "Yellow"],
     "mid-engine roadster, soft-top convertible, side intakes"),

    # ═══ McLaren ═══
    ("McLaren", "720S", 2019, "sports_car", 4544, 1930, 1196, 2670,
     "4.0L Twin-Turbo V8", "RWD", 720, 341,
     ["dihedral doors", "eye-socket headlights", "active rear wing", "folding airbrake"],
     ["Orange", "Black", "Silver", "Blue"],
     "mid-engine supercar, teardrop canopy, dihedral doors, double-skin aero"),
    ("McLaren", "P1", 2015, "sports_car", 4588, 1946, 1188, 2670,
     "3.8L Twin-Turbo V8 Hybrid", "RWD", 903, 350,
     ["dihedral doors", "low nose", "large rear wing", "roof snorkel intake"],
     ["Yellow", "Black", "Silver"],
     "mid-engine hypercar, extreme aero, roof intake, dihedral doors"),
    ("McLaren", "Senna", 2019, "sports_car", 4744, 1953, 1196, 2710,
     "4.0L Twin-Turbo V8", "RWD", 789, 340,
     ["dihedral doors", "huge rear wing", "aero gaps", "triple exhaust"],
     ["Grey", "Black", "Orange"],
     "mid-engine track car, massive active rear wing, aero blade gaps"),
    ("McLaren", "Artura", 2023, "sports_car", 4539, 1940, 1193, 2640,
     "3.0L Twin-Turbo V6 Hybrid", "RWD", 671, 330,
     ["dihedral doors", "slim headlights", "dual exhaust", "aero blades"],
     ["Green", "Blue", "Black", "Orange"],
     "mid-engine hybrid, slim headlights, compact aero, dihedral doors"),
    ("McLaren", "570S", 2018, "sports_car", 4530, 1930, 1202, 2670,
     "3.8L Twin-Turbo V8", "RWD", 562, 328,
     ["dihedral doors", "eye-socket headlights", "rear wing", "quad exhaust"],
     ["Orange", "Black", "Silver", "Blue"],
     "mid-engine, entry-level supercar, eye-socket headlights"),

    # ═══ Bugatti ═══
    ("Bugatti", "Chiron", 2020, "sports_car", 4621, 2038, 1212, 2711,
     "8.0L W16 Quad-Turbo", "AWD", 1500, 420,
     ["C-shape side profile", "horseshoe grille", "full-width taillight", "spoked rims"],
     ["Blue", "Black", "Silver"],
     "mid-engine hypercar, C-shaped side line, horseshoe grille, duo-tone blue"),
    ("Bugatti", "Veyron", 2010, "sports_car", 4462, 1998, 1204, 2710,
     "8.0L W16 Quad-Turbo", "AWD", 1001, 407,
     ["horseshoe grille", "rounded body", "full-width taillight", "large side intakes"],
     ["Blue", "Black", "Silver"],
     "mid-engine hypercar, rounded body, horseshoe grille"),
    ("Bugatti", "Divo", 2020, "sports_car", 4641, 2018, 1212, 2711,
     "8.0L W16 Quad-Turbo", "AWD", 1500, 380,
     ["huge rear wing", "aggressive front splitter", "fins", "3D taillight"],
     ["Blue", "Silver", "Black"],
     "mid-engine, aggressive aero, massive fixed rear wing, shark fin"),
    ("Bugatti", "Centodieci", 2021, "sports_car", 4641, 2038, 1212, 2711,
     "8.0L W16 Quad-Turbo", "AWD", 1600, 380,
     ["EB110 tribute", "small horseshoe grille", "rear wing", "quad exhaust"],
     ["White", "Blue"],
     "mid-engine, EB110 homage, small grille, low wide rear wing"),

    # ═══ BMW ═══
    ("BMW", "M3", 2022, "sedan", 4794, 1903, 1433, 2857,
     "3.0L Twin-Turbo Inline-6", "RWD", 503, 290,
     ["kidney grille", "quad exhaust", "wide fenders", "M badge"],
     ["White", "Black", "Blue", "Grey"],
     "front-engine sedan, large kidney grille, quad exhaust, wide fenders"),
    ("BMW", "M4", 2022, "sports_car", 4794, 1886, 1393, 2857,
     "3.0L Twin-Turbo Inline-6", "RWD", 503, 290,
     ["vertical kidney grille", "quad exhaust", "carbon roof", "wide haunches"],
     ["White", "Black", "Blue", "Grey"],
     "front-engine coupe, vertical kidney grille, carbon fiber roof"),
    ("BMW", "M5", 2022, "sedan", 4983, 1903, 1471, 2982,
     "4.4L Twin-Turbo V8", "AWD", 600, 305,
     ["kidney grille", "quad exhaust", "wide fenders", "M badge"],
     ["Black", "White", "Blue", "Grey"],
     "front-engine sedan, subtle aggressive styling, quad exhaust"),
    ("BMW", "i8", 2018, "sports_car", 4689, 1942, 1282, 2800,
     "1.5L Turbo I3 Hybrid", "AWD", 369, 250,
     ["scissor doors", "blue accents", "transparent hood", "U-shape taillights"],
     ["White", "Blue", "Grey", "Black"],
     "mid-engine hybrid, scissor doors, blue accent lines, layered body"),
    ("BMW", "Z4", 2022, "sports_car", 4336, 1864, 1292, 2470,
     "3.0L Turbo Inline-6", "RWD", 382, 250,
     ["soft-top convertible", "long hood", "kidney grille", "twin exhaust"],
     ["White", "Black", "Blue", "Orange"],
     "front-engine roadster, soft-top, long hood, low stance"),

    # ═══ Mercedes-AMG ═══
    ("Mercedes-AMG", "GT", 2022, "sports_car", 4544, 1939, 1287, 2630,
     "4.0L Twin-Turbo V8", "RWD", 577, 312,
     ["long hood", "sloping roofline", "twin exhaust", "panam grille"],
     ["Silver", "Black", "Grey", "Yellow"],
     "front-engine, long hood, panamericana grille, sloping fastback"),
    ("Mercedes-AMG", "SLS", 2014, "sports_car", 4638, 1939, 1262, 2680,
     "6.2L V8", "RWD", 583, 320,
     ["gullwing doors", "long hood", "quad exhaust", "wide rear"],
     ["Silver", "Red", "Black", "Yellow"],
     "front-engine, gullwing doors, long hood, wide rear"),
    ("Mercedes-AMG", "GTR", 2021, "sports_car", 4551, 1939, 1283, 2630,
     "4.0L Twin-Turbo V8", "RWD", 577, 318,
     ["large rear wing", "wide body", "panam grille", "twin exhaust"],
     ["Green", "Grey", "Black", "Silver"],
     "front-engine, GT3-inspired, large rear wing, wide body kit"),
    ("Mercedes-AMG", "SLR", 2008, "sports_car", 4656, 1954, 1261, 2700,
     "5.4L Supercharged V8", "RWD", 617, 334,
     ["long hood", "side exhaust", "gullwing doors", "wide grille"],
     ["Silver", "Black"],
     "front-engine, long nose, side pipes, butterfly doors"),

    # ═══ Audi ═══
    ("Audi", "R8", 2022, "sports_car", 4429, 1940, 1240, 2650,
     "5.2L V10", "AWD", 602, 330,
     ["hexagonal grille", "side blades", "quad exhaust", "LED headlights"],
     ["White", "Green", "Black", "Silver"],
     "mid-engine, hexagonal grille, large side blades, LED headlight signature"),
    ("Audi", "RS6", 2022, "wagon", 4995, 1950, 1470, 2928,
     "4.0L Twin-Turbo V8", "AWD", 591, 305,
     ["wagon body", "wide fenders", "oval exhaust", "honeycomb grille"],
     ["Black", "Grey", "Blue", "White"],
     "front-engine wagon, wide fenders, honeycomb grille, oval quad exhaust"),
    ("Audi", "TT RS", 2022, "sports_car", 4191, 1832, 1342, 2505,
     "2.5L Turbo Inline-5", "AWD", 394, 280,
     ["compact coupe", "oval exhaust", "hexagonal grille", "small rear wing"],
     ["White", "Red", "Black", "Grey"],
     "front-engine compact coupe, single-frame grille, oval exhaust"),
    ("Audi", "e-tron GT", 2022, "sports_car", 4985, 1964, 1392, 2900,
     "Dual Electric Motors", "AWD", 637, 250,
     ["sloping roofline", "hexagonal grille", "full-width taillight", "no exhaust"],
     ["Black", "Blue", "Grey", "Red"],
     "electric four-door coupe, low stance, hexagonal grille, full-width taillight"),

    # ═══ Nissan ═══
    ("Nissan", "GT-R", 2017, "sports_car", 4710, 1895, 1370, 2780,
     "3.8L Twin-Turbo V6", "AWD", 565, 315,
     ["boxy fenders", "quad exhaust", "round taillights", "V-motion grille"],
     ["White", "Black", "Silver", "Red"],
     "front-engine, boxy angular body, quad round taillights, V-motion grille"),
    ("Nissan", "370Z", 2020, "sports_car", 4265, 1840, 1315, 2550,
     "3.7L V6", "RWD", 332, 260,
     ["long hood", "sloping roofline", "dual exhaust", "vertical headlights"],
     ["White", "Yellow", "Black", "Red"],
     "front-engine, long hood fastback, vertical headlights"),
    ("Nissan", "400Z", 2023, "sports_car", 4278, 1845, 1315, 2570,
     "3.0L Twin-Turbo V6", "RWD", 400, 280,
     ["long hood", "round taillights", "dual exhaust", "sloping roof"],
     ["Yellow", "Blue", "White", "Black"],
     "front-engine, retro Z styling, long hood, round taillights"),

    # ═══ Toyota ═══
    ("Toyota", "Supra", 2023, "sports_car", 4380, 1865, 1290, 2470,
     "3.0L Turbo Inline-6", "RWD", 382, 250,
     ["long hood", "double-bubble roof", "center exhaust", "spoke wheels"],
     ["Yellow", "Red", "White", "Black", "Orange"],
     "front-engine, long hood, double-bubble roof, single center exhaust"),
    ("Toyota", "86", 2020, "sports_car", 4240, 1775, 1320, 2570,
     "2.0L Flat-4", "RWD", 205, 225,
     ["sloping roofline", "dual exhaust", "low stance", "slim headlights"],
     ["White", "Orange", "Black", "Blue"],
     "front-engine, balanced coupe, low center of gravity, slim headlights"),
    ("Toyota", "GR Corolla", 2023, "hatchback", 4395, 1840, 1440, 2640,
     "1.6L Turbo Inline-3", "AWD", 300, 230,
     ["wide fenders", "triple exhaust", "honeycomb grille", "wide body"],
     ["White", "Black", "Red"],
     "front-engine hot hatch, wide fenders, unique triple exhaust center"),

    # ═══ Honda ═══
    ("Honda", "NSX", 2020, "sports_car", 4490, 1940, 1215, 2630,
     "3.5L Twin-Turbo V6 Hybrid", "AWD", 573, 307,
     ["sharp headlights", "side intakes", "quad exhaust", "low stance"],
     ["White", "Red", "Black", "Silver"],
     "mid-engine hybrid, sharp angular headlights, side air intakes"),
    ("Honda", "Civic Type R", 2022, "hatchback", 4595, 1800, 1420, 2700,
     "2.0L Turbo Inline-4", "FWD", 306, 270,
     ["large rear wing", "triple exhaust", "red Honda badge", "wide body"],
     ["White", "Yellow", "Black", "Red"],
     "front-engine hot hatch, large rear wing, triple center exhaust"),
    ("Honda", "S2000", 2008, "sports_car", 4135, 1750, 1285, 2400,
     "2.2L Inline-4", "RWD", 240, 240,
     ["long hood", "soft-top convertible", "twin exhaust", "slim headlights"],
     ["White", "Yellow", "Black", "Red"],
     "front-engine roadster, long hood, rear-wheel drive, high-revving"),

    # ═══ Additional iconic models ═══
    ("Aston Martin", "Valkyrie", 2021, "sports_car", 4465, 1925, 1035, 2710,
     "6.5L V12 Hybrid", "RWD", 1160, 402,
     ["F1-style nose", "teardrop canopy", "open underbody", "KERS wing"],
     ["Green", "Red", "White", "Black"],
     "F1-inspired hypercar, open-wheel front, teardrop canopy, extreme aero"),
    ("Aston Martin", "DB5", 1964, "sports_car", 4572, 1676, 1360, 2489,
     "4.0L Inline-6", "RWD", 282, 233,
     ["classic grille", "wire wheels", "slim headlights", "fastback roof"],
     ["Silver", "Green", "Black"],
     "front-engine grand tourer, classic British styling, wire wheels"),
    ("Koenigsegg", "Jesko", 2022, "sports_car", 4660, 2030, 1210, 2700,
     "5.0L Twin-Turbo V8", "RWD", 1280, 480,
     ["wraparound windshield", "large rear wing", "dihedral synchro doors", "triple exhaust"],
     ["White", "Silver", "Black"],
     "mid-engine hypercar, wraparound windshield, synchro-helix doors"),
    ("Ford", "GT", 2022, "sports_car", 4694, 1950, 1125, 2700,
     "3.5L Twin-Turbo V6", "RWD", 660, 348,
     ["low wedge shape", "flying buttresses", "dual exhaust", "hexagonal taillights"],
     ["Blue", "Silver", "Black", "Red"],
     "mid-engine supercar, low wedge, flying buttresses, racing heritage"),
]


async def seed():
    """Insert car specs into the database (idempotent)."""
    async with async_session() as db:
        added = 0
        skipped = 0
        updated = 0

        for spec_tuple in SEED_SPECS:
            (
                make, model, year, body_style,
                length_mm, width_mm, height_mm, wheelbase_mm,
                engine_type, drive_type, horsepower, top_speed_kmh,
                distinctive_features, colors_available, body_proportions,
            ) = spec_tuple

            # Check if already exists
            result = await db.execute(
                select(CarSpec).where(
                    CarSpec.make == make,
                    CarSpec.model == model,
                    CarSpec.year == year,
                )
            )
            existing = result.scalar_one_or_none()

            if existing:
                # Update existing entry
                existing.body_style = body_style
                existing.length_mm = length_mm
                existing.width_mm = width_mm
                existing.height_mm = height_mm
                existing.wheelbase_mm = wheelbase_mm
                existing.engine_type = engine_type
                existing.drive_type = drive_type
                existing.horsepower = horsepower
                existing.top_speed_kmh = top_speed_kmh
                existing.distinctive_features = distinctive_features
                existing.colors_available = colors_available
                existing.body_proportions = body_proportions
                existing.source = "seed_wikipedia"
                existing.confidence = 0.95
                updated += 1
            else:
                car_spec = CarSpec(
                    make=make,
                    model=model,
                    year=year,
                    body_style=body_style,
                    length_mm=length_mm,
                    width_mm=width_mm,
                    height_mm=height_mm,
                    wheelbase_mm=wheelbase_mm,
                    engine_type=engine_type,
                    drive_type=drive_type,
                    horsepower=horsepower,
                    top_speed_kmh=top_speed_kmh,
                    distinctive_features=distinctive_features,
                    colors_available=colors_available,
                    body_proportions=body_proportions,
                    source="seed_wikipedia",
                    confidence=0.95,
                )
                db.add(car_spec)
                added += 1

        await db.commit()
        print(f"Seed complete: {added} specs added, {updated} updated, {skipped} unchanged.")
        return added, updated, skipped


if __name__ == "__main__":
    asyncio.run(seed())
