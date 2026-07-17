"""Seed the database with known LEGO car sets mapped to real car models.

Run: python data/seed_sets.py

Covers Speed Champions, Technic, Creator Expert/Icons, and other themes.
"""

import asyncio
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent / "backend"))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.lego_set import LegoSet

# ── Known LEGO car sets ──────────────────────────
# Format: (set_num, name, year, brick_count, car_make, car_model, theme_id, instructions_url)

SEED_SETS: list[tuple[str, str, int, int, str, str, int | None, str | None]] = [
    # ═══ Speed Champions ═══
    ("75890-1", "Ferrari F40 Competizione", 2019, 198, "Ferrari", "F40", 601, None),
    ("75891-1", "Chevrolet Camaro ZL1 Race Car", 2019, 198, "Chevrolet", "Camaro ZL1", 601, None),
    ("75892-1", "McLaren Senna", 2019, 219, "McLaren", "Senna", 601, None),
    ("75893-1", "2018 Dodge Challenger SRT Demon & 1970 Dodge Charger R/T", 2019, 478, "Dodge", "Challenger SRT Demon", 601, None),
    ("75894-1", "1967 Mini Cooper S Rally & 2018 MINI John Cooper Works Buggy", 2019, 481, "Mini", "Cooper S", 601, None),
    ("75895-1", "1974 Porsche 911 Turbo 3.0", 2019, 180, "Porsche", "911 Turbo", 601, None),
    ("75899-1", "Ferrari LaFerrari", 2015, 177, "Ferrari", "LaFerrari", 601, None),
    ("75909-1", "McLaren P1", 2015, 168, "McLaren", "P1", 601, None),
    ("75910-1", "Porsche 918 Spyder", 2015, 168, "Porsche", "918 Spyder", 601, None),
    ("76895-1", "Ferrari F8 Tributo", 2020, 275, "Ferrari", "F8 Tributo", 601, None),
    ("76896-1", "Nissan GT-R NISMO", 2020, 298, "Nissan", "GT-R NISMO", 601, None),
    ("76897-1", "1985 Audi Sport Quattro S1", 2020, 250, "Audi", "Sport Quattro S1", 601, None),
    ("76899-1", "Lamborghini Huracán Super Trofeo EVO & Urus ST-X", 2020, 660, "Lamborghini", "Huracán", 601, None),
    ("76900-1", "Koenigsegg Jesko", 2021, 280, "Koenigsegg", "Jesko", 601, None),
    ("76901-1", "Toyota GR Supra", 2021, 299, "Toyota", "Supra", 601, None),
    ("76902-1", "McLaren Elva", 2021, 263, "McLaren", "Elva", 601, None),
    ("76903-1", "Chevrolet Corvette C8.R & 1968 Corvette", 2021, 512, "Chevrolet", "Corvette C8.R", 601, None),
    ("76904-1", "Mopar Dodge//SRT Top Fuel Dragster & 1970 Challenger T/A", 2021, 627, "Dodge", "Challenger T/A", 601, None),
    ("76905-1", "Ford GT Heritage Edition & Bronco R", 2021, 660, "Ford", "GT", 601, None),
    ("76906-1", "1970 Ferrari 512 M", 2022, 291, "Ferrari", "512 M", 601, None),
    ("76907-1", "Lotus Evija", 2022, 247, "Lotus", "Evija", 601, None),
    ("76908-1", "Lamborghini Countach", 2022, 262, "Lamborghini", "Countach", 601, None),
    ("76909-1", "Mercedes-AMG F1 W12 E Performance & Project One", 2022, 564, "Mercedes-AMG", "F1 W12", 601, None),
    ("76910-1", "Aston Martin Valkyrie AMR Pro & Vantage GT3", 2022, 592, "Aston Martin", "Valkyrie", 601, None),
    ("76911-1", "007 Aston Martin DB5", 2022, 298, "Aston Martin", "DB5", 601, None),
    ("76912-1", "Fast & Furious 1970 Dodge Charger R/T", 2022, 345, "Dodge", "Charger R/T", 601, None),
    ("76914-1", "Ferrari 812 Competizione", 2023, 261, "Ferrari", "812 Competizione", 601, None),
    ("76915-1", "Pagani Utopia", 2023, 249, "Pagani", "Utopia", 601, None),
    ("76916-1", "Porsche 963", 2023, 280, "Porsche", "963", 601, None),
    ("76917-1", "Nissan Skyline GT-R (R34)", 2023, 319, "Nissan", "Skyline GT-R R34", 601, None),
    ("76918-1", "McLaren Solus GT & McLaren F1 LM", 2023, 581, "McLaren", "Solus GT", 601, None),
    ("76919-1", "2023 McLaren Formula 1 Race Car", 2024, 245, "McLaren", "F1", 601, None),
    ("76920-1", "Ford Mustang Dark Horse", 2024, 270, "Ford", "Mustang Dark Horse", 601, None),
    ("76921-1", "Audi S1 e-tron quattro", 2024, 278, "Audi", "S1 e-tron", 601, None),
    ("76922-1", "BMW M4 GT3 & BMW M Hybrid V8", 2024, 676, "BMW", "M4 GT3", 601, None),
    ("76923-1", "Lamborghini Lambo V12 Vision Gran Turismo", 2024, 230, "Lamborghini", "Lambo V12 Vision GT", 601, None),
    ("76924-1", "Mercedes-AMG G 63 & Mercedes-AMG SL 63", 2024, 808, "Mercedes-AMG", "SL 63", 601, None),
    ("76925-1", "Aston Martin Vantage Safety Car & AMR23", 2024, 564, "Aston Martin", "Vantage", 601, None),
    ("76935-1", "NASCAR Next Gen Chevrolet Camaro ZL1", 2024, 328, "Chevrolet", "Camaro ZL1 NASCAR", 601, None),
    # ── Speed Champions 2025 F1 Grid ──
    ("77242-1", "Ferrari SF-24 F1 Race Car", 2025, 275, "Ferrari", "SF-24 F1", 601, None),
    ("77243-1", "Oracle Red Bull Racing RB20 F1 Race Car", 2025, 251, "Red Bull", "RB20 F1", 601, None),
    ("77244-1", "Mercedes-AMG F1 W15 E Performance", 2025, 267, "Mercedes-AMG", "F1 W15", 601, None),
    ("77245-1", "Aston Martin Aramco F1 AMR24 Race Car", 2025, 269, "Aston Martin", "AMR24 F1", 601, None),
    ("77246-1", "Visa Cash App RB VCARB 01 F1 Race Car", 2025, 248, "RB", "VCARB 01 F1", 601, None),
    ("77247-1", "KICK Sauber F1 Team C44 Race Car", 2025, 259, "Sauber", "C44 F1", 601, None),
    ("77248-1", "BWT Alpine F1 Team A524 Race Car", 2025, 258, "Alpine", "A524 F1", 601, None),
    ("77249-1", "Williams Racing FW46 F1 Race Car", 2025, 263, "Williams", "FW46 F1", 601, None),
    ("77250-1", "MoneyGram Haas F1 Team VF-24 Race Car", 2025, 242, "Haas", "VF-24 F1", 601, None),
    ("77251-1", "McLaren F1 Team MCL38 Race Car", 2025, 269, "McLaren", "MCL38 F1", 601, None),
    # ── Speed Champions 2025 Summer ──
    ("77241-1", "2 Fast 2 Furious Honda S2000", 2025, 300, "Honda", "S2000", 601, None),
    ("77237-1", "Dodge Challenger SRT Hellcat", 2025, 390, "Dodge", "Challenger SRT Hellcat", 601, None),
    ("77238-1", "Lamborghini Revuelto & Huracán STO", 2025, 607, "Lamborghini", "Revuelto", 601, None),
    ("77239-1", "Porsche 911 GT3 RS", 2025, 348, "Porsche", "911 GT3 RS", 601, None),
    ("77240-1", "Bugatti Centodieci", 2025, 291, "Bugatti", "Centodieci", 601, None),
    # ── Speed Champions 2026 ──
    ("77252-1", "APXGP Team Race Car (F1 Movie)", 2026, 268, "APXGP", "F1 Movie", 601, None),
    ("77253-1", "Bugatti Vision Gran Turismo", 2026, 284, "Bugatti", "Vision Gran Turismo", 601, None),
    ("77254-1", "Ferrari SF90 XX Stradale", 2026, 339, "Ferrari", "SF90 XX Stradale", 601, None),
    ("77255-1", "Lightning McQueen (Disney Pixar Cars)", 2026, 270, "Disney", "Lightning McQueen", 601, None),
    ("77256-1", "Time Machine (Back to the Future)", 2026, 357, "DeLorean", "DMC-12 Time Machine", 601, None),
    ("77257-1", "McLaren W1", 2026, 287, "McLaren", "W1", 601, None),
    ("77258-1", "F1 ACADEMY LEGO Race Car", 2026, 201, "F1 Academy", "Race Car", 601, None),
    ("77259-1", "Audi Revolut F1 Team R26", 2026, 215, "Audi", "R26 F1", 601, None),
    ("77260-1", "Fast & Furious Toyota Supra MK4", 2026, 292, "Toyota", "Supra MK4", 601, None),
    ("77261-1", "Ferrari 499P Hypercar", 2026, 329, "Ferrari", "499P", 601, None),
    ("77262-1", "Ken Block's 1965 Ford Mustang Hoonicorn V1", 2026, 345, "Ford", "Mustang Hoonicorn", 601, None),
    ("77263-1", "BMW M3 (E30) 40th Anniversary", 2026, 358, "BMW", "M3 E30", 601, None),
    ("77264-1", "Jaguar F-TYPE Project 7 & Land Rover Defender Classic", 2026, 740, "Jaguar", "F-TYPE Project 7", 601, None),

    # ═══ Technic ═══
    ("42056-1", "Porsche 911 GT3 RS", 2016, 2704, "Porsche", "911 GT3 RS", 1, None),
    ("42083-1", "Bugatti Chiron", 2018, 3599, "Bugatti", "Chiron", 1, None),
    ("42093-1", "Chevrolet Corvette ZR1", 2019, 579, "Chevrolet", "Corvette ZR1", 1, None),
    ("42096-1", "Porsche 911 RSR", 2019, 1580, "Porsche", "911 RSR", 1, None),
    ("42098-1", "Car Transporter", 2019, 2493, "Generic", "Car Transporter", 1, None),
    ("42109-1", "App-Controlled Top Gear Rally Car", 2020, 463, "Top Gear", "Rally Car", 1, None),
    ("42110-1", "Land Rover Defender", 2019, 2573, "Land Rover", "Defender", 1, None),
    ("42111-1", "Dom's Dodge Charger", 2020, 1077, "Dodge", "Charger", 1, None),
    ("42115-1", "Lamborghini Sián FKP 37", 2020, 3696, "Lamborghini", "Sián FKP 37", 1, None),
    ("42122-1", "Jeep Wrangler", 2021, 665, "Jeep", "Wrangler", 1, None),
    ("42123-1", "McLaren Senna GTR", 2021, 830, "McLaren", "Senna GTR", 1, None),
    ("42125-1", "Ferrari 488 GTE AF Corse #51", 2021, 1677, "Ferrari", "488 GTE", 1, None),
    ("42126-1", "Ford F-150 Raptor", 2021, 1379, "Ford", "F-150 Raptor", 1, None),
    ("42138-1", "Ford Mustang Shelby GT500", 2022, 544, "Ford", "Mustang Shelby GT500", 1, None),
    ("42143-1", "Ferrari Daytona SP3", 2022, 3778, "Ferrari", "Daytona SP3", 1, None),
    ("42151-1", "Bugatti Bolide", 2023, 905, "Bugatti", "Bolide", 1, None),
    ("42154-1", "2022 Ford GT", 2023, 1466, "Ford", "GT", 1, None),
    ("42161-1", "Lamborghini Huracán Tecnica", 2023, 806, "Lamborghini", "Huracán Tecnica", 1, None),
    ("42165-1", "Mercedes-AMG F1 W14 E Performance (Pull-Back)", 2024, 240, "Mercedes-AMG", "F1 W14", 1, None),
    ("42171-1", "Mercedes-AMG F1 W14 E Performance", 2024, 1642, "Mercedes-AMG", "F1 W14", 1, None),
    ("42173-1", "Koenigsegg Jesko Absolut", 2024, 801, "Koenigsegg", "Jesko Absolut", 1, None),
    ("42172-1", "McLaren P1", 2024, 3893, "McLaren", "P1", 1, None),
    ("42232-1", "Koenigsegg Sadair's Spear", 2026, 4104, "Koenigsegg", "Sadair's Spear", 1, None),
    # ── Technic 2023-2025 ──
    ("42156-1", "Peugeot 9X8 24H Le Mans Hybrid Hypercar", 2023, 1775, "Peugeot", "9X8", 1, None),
    ("42169-1", "NEOM McLaren Formula E Race Car", 2024, 452, "McLaren", "Formula E", 1, None),
    ("42176-1", "Porsche GT4 e-Performance RC Race Car", 2024, 838, "Porsche", "GT4 e-Performance", 1, None),
    ("42177-1", "Mercedes-Benz G 500 Professional Line 4x4", 2024, 2891, "Mercedes-Benz", "G 500", 1, None),
    ("42204-1", "Fast & Furious Toyota Supra MK4", 2025, 810, "Toyota", "Supra MK4", 1, None),
    ("42205-1", "Chevrolet Corvette Stingray", 2025, 732, "Chevrolet", "Corvette Stingray", 1, None),
    ("42206-1", "Oracle Red Bull Racing RB20 F1 Car", 2025, 1639, "Red Bull", "RB20 F1", 1, None),
    ("42207-1", "Ferrari SF-24 F1 Car", 2025, 1361, "Ferrari", "SF-24 F1", 1, None),

    # ═══ Creator Expert / Icons ═══
    ("10242-1", "MINI Cooper Mk VII", 2014, 1077, "Mini", "Cooper", 3, None),
    ("10248-1", "Ferrari F40", 2015, 1158, "Ferrari", "F40", 3, None),
    ("10252-1", "Volkswagen Beetle", 2016, 1167, "Volkswagen", "Beetle", 3, None),
    ("10258-1", "London Bus", 2017, 1686, "Routemaster", "London Bus", 3, None),
    ("10262-1", "James Bond Aston Martin DB5", 2018, 1295, "Aston Martin", "DB5", 3, None),
    ("10265-1", "Ford Mustang", 2019, 1471, "Ford", "Mustang", 3, None),
    ("10271-1", "Fiat 500", 2020, 960, "Fiat", "500", 3, None),
    ("10274-1", "Ghostbusters ECTO-1", 2020, 2352, "Cadillac", "ECTO-1", 3, None),
    ("10279-1", "Volkswagen T2 Camper Van", 2021, 2207, "Volkswagen", "T2 Camper", 3, None),
    ("10290-1", "Pickup Truck", 2021, 1677, "Generic", "Pickup Truck", 3, None),
    ("10295-1", "Porsche 911 (Turbo & Targa)", 2021, 1458, "Porsche", "911", 3, None),
    ("10300-1", "Back to the Future Time Machine", 2022, 1872, "DeLorean", "DMC-12", 3, None),
    ("10304-1", "Chevrolet Camaro Z28", 2022, 1456, "Chevrolet", "Camaro Z28", 3, None),
    ("10317-1", "Land Rover Classic Defender 90", 2023, 2336, "Land Rover", "Defender 90", 3, None),
    ("10321-1", "Chevrolet Corvette C1", 2024, 1210, "Chevrolet", "Corvette C1", 3, None),
    # ── Icons 2024-2025 ──
    ("10330-1", "McLaren MP4/4 & Ayrton Senna", 2024, 693, "McLaren", "MP4/4", 3, None),
    ("10337-1", "Lamborghini Countach 5000 Quattrovalvole", 2024, 1506, "Lamborghini", "Countach 5000 QV", 3, None),
    ("10353-1", "Williams Racing FW14B & Nigel Mansell", 2025, 799, "Williams", "FW14B F1", 3, None),
    ("10357-1", "Shelby Cobra 427 S/C", 2025, 1241, "Shelby", "Cobra 427 S/C", 3, None),
    # ── Advanced Models / Early Creator Expert ──
    ("10220-1", "Volkswagen T1 Camper Van", 2011, 1334, "Volkswagen", "T1 Camper", 3, None),

    # ═══ Speed Champions (older) ═══
    ("75870-1", "Chevrolet Corvette Z06", 2016, 173, "Chevrolet", "Corvette Z06", 601, None),
    ("75871-1", "Ford Mustang GT", 2016, 185, "Ford", "Mustang GT", 601, None),
    ("75872-1", "Audi R18 e-tron quattro", 2016, 166, "Audi", "R18 e-tron", 601, None),
    ("75873-1", "Audi R8 LMS Ultra", 2016, 175, "Audi", "R8 LMS", 601, None),
    ("75874-1", "Chevrolet Camaro Drag Race", 2016, 445, "Chevrolet", "Camaro", 601, None),
    ("75875-1", "Ford F-150 Raptor & Model A Hot Rod", 2016, 574, "Ford", "F-150 Raptor", 601, None),
    ("75876-1", "Porsche 919 Hybrid & 917K Pit Lane", 2016, 732, "Porsche", "919 Hybrid", 601, None),
    ("75877-1", "Mercedes-AMG GT3", 2017, 196, "Mercedes-AMG", "GT3", 601, None),
    ("75878-1", "Bugatti Chiron", 2017, 174, "Bugatti", "Chiron", 601, None),
    ("75879-1", "Scuderia Ferrari SF16-H", 2017, 184, "Ferrari", "SF16-H", 601, None),
    ("75880-1", "McLaren 720S", 2017, 162, "McLaren", "720S", 601, None),
    ("75881-1", "2016 Ford GT & 1966 Ford GT40", 2017, 336, "Ford", "GT", 601, None),
    ("75882-1", "Ferrari FXX K & Development Center", 2017, 494, "Ferrari", "FXX K", 601, None),
    ("75883-1", "Mercedes-AMG PETRONAS Formula One Team", 2017, 392, "Mercedes-AMG", "F1 W07", 601, None),
    ("75884-1", "1968 Ford Mustang Fastback", 2018, 183, "Ford", "Mustang Fastback", 601, None),
    ("75885-1", "Ford Fiesta M-Sport WRC", 2018, 203, "Ford", "Fiesta WRC", 601, None),
    ("75886-1", "Ferrari 488 GT3 Scuderia Corsa", 2018, 179, "Ferrari", "488 GT3", 601, None),
    ("75887-1", "Porsche 919 Hybrid", 2018, 163, "Porsche", "919 Hybrid", 601, None),
    ("75888-1", "Porsche 911 RSR & 911 Turbo 3.0", 2018, 391, "Porsche", "911 RSR", 601, None),
    ("75889-1", "Ferrari Ultimate Garage", 2018, 841, "Ferrari", "F1", 601, None),

    # Additional iconic car sets
    ("76934-1", "Ferrari F40", 2024, 318, "Ferrari", "F40", 601, None),
    ("42184-1", "Koenigsegg Jesko Absolut (small)", 2024, 801, "Koenigsegg", "Jesko Absolut", 1, None),
]


async def seed():
    """Insert known LEGO car sets into the database (idempotent)."""
    async with async_session() as db:
        added = 0
        skipped = 0

        for set_num, name, year, brick_count, car_make, car_model, theme_id, instructions_url in SEED_SETS:
            # Check if already exists
            result = await db.execute(select(LegoSet).where(LegoSet.set_num == set_num))
            existing = result.scalar_one_or_none()
            if existing:
                skipped += 1
                continue

            lego_set = LegoSet(
                set_num=set_num,
                name=name,
                year=year,
                brick_count=brick_count,
                car_make=car_make,
                car_model=car_model,
                theme_id=theme_id,
                instructions_url=instructions_url,
            )
            db.add(lego_set)
            added += 1

        await db.commit()
        print(f"Seed complete: {added} sets added, {skipped} already existed.")
        return added, skipped


if __name__ == "__main__":
    asyncio.run(seed())
