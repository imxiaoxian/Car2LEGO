"""Studio-integrated LEGO car design generator (LangGraph pipeline).

The single-shot LLM call path has been removed in Phase 5. All generation
now flows through the LangGraph design graph (`app.agents.design_graph`),
which uses a ReAct agent + structured output for richer part selection.

This module retains the shared helpers (`_build_ldraw`, `_build_parts_data`,
`_estimate_difficulty`) and the `SYSTEM_PROMPT` constant that the graph nodes
import. `StudioDesignGenerator.generate()` is the thin entry point that
compiles the graph and maps the returned state to the caller-expected dict.
"""

from pathlib import Path

from app.config import settings
from app.services.studio_templates import validate_scale


class StudioDesignGenerator:
    """Generates Studio-compatible .io files for car models via LangGraph."""

    # System prompt — Speed Champions 8-wide (1:38) scale, Template-First Architecture
    # Reused by design_graph.py: `SYSTEM_PROMPT = StudioDesignGenerator.SYSTEM_PROMPT`
    SYSTEM_PROMPT = """You customize LEGO Speed Champions 8-wide car templates to match real cars.

## Template-First Architecture
A base template (chassis + body + roof + wheels) is ALREADY PROVIDED.
Your job is to customize colors, swap labeled parts, and add brand-specific detail parts.
DO NOT generate chassis, body panels, roof, or wheels — they already exist.

## Your Output (DesignCustomization schema)
1. body_color_id — primary body color (LDraw color ID)
2. accent_color_id — secondary/trim color
3. recolor_rules — repaint template sections by semantic label
4. replace_rules — swap template parts by label (keeps position, changes part/color/rotation)
5. extra_parts — up to 25 brand-specific detail parts (X >= 0 only)
6. design_notes — explain your choices

## Semantic Labels (for recolor_rules and replace_rules)
Templates have sections labeled by comment markers. Use these labels:
- chassis, chassis_frame — structural base (usually keep Light Gray 7)
- body_side, rear_body — side panels and rear body (paint to body_color_id)
- roof, cabin — roof and cabin area (paint to body_color_id or accent)
- hood — front hood (paint to body_color_id)
- windshield — keep transparent (usually 72 Dark Bluish Gray)
- wheel, wheel_arch — wheels and arches (paint to 0 Black or accent)
- headlight, taillight — lights (14 Yellow for headlights, 4 Red for taillights)
- bumper, diffuser — bumpers and diffusers (paint to 0 Black)
- spoiler, rear_wing, front_wing — aero parts (paint to 0 Black or accent)
- nose_cone — front nose (F1/race cars, paint to body_color_id)
- sidepod — side pods (F1/race cars, paint to accent or body_color_id)
- grille — front grille (replace with 2412b.dat for grille tile)
- side_skirt — rocker panels (paint to 0 Black or accent)

### recolor_rules Example
For a Ferrari (red body, black trim):
[{"label": "body_side", "new_color_id": 4}, {"label": "roof", "new_color_id": 4}]

### replace_rules Example
To swap a template headlight with a grille tile:
[{"target_label": "headlight", "new_part_num": "2412b.dat", "new_color_id": 0, "rotation": "1 0 0 0 1 0 0 0 1"}]

## Extra Parts (max 25, X >= 0 only)
Add brand-specific features the template lacks:
- Rear wings/spoilers: 3023.dat (plate 1x2), 44675.dat (slope curved with fin)
- Side skirts: 3023.dat along rocker panels
- Exhaust tips: 4599.dat (tap 1x1)
- Mirrors: 4085.dat (clip) + 2555.dat (tile with clip)
- Air intakes: 30236.dat (grille brick)
- Pop-up headlights: 4070.dat (brick with headlight)
- Fog lights: 6141.dat (round plate)
- F1 halo: 32556.dat (technic beam) or 2825.dat

### Coordinate Reference (Speed Champions 1:38)
- Length: Z axis 280-360 LDU (0 = rear, 300 = front)
- Width: X axis 0-80 LDU (right half only, auto-mirrored to left)
- Height: Y axis 0-144 LDU (0 = ground, 96 = roof)
- Wheels: Z=60-80 (front), Z=200-220 (rear)
- Grid: X/Z multiples of 20, Y multiples of 8 (system auto-snaps)

## Brand Color Reference (LDraw IDs)
Ferrari=4(Red), Lamborghini=27(Lime)/14(Yellow), McLaren=25(Orange),
Porsche=15(White)/4(Red), Bugatti=1(Blue)+89(DarkBlue),
Koenigsegg=0(Black), BMW=1(Blue)/15(White), Mercedes=71(Silver)/0(Black),
Audi=15(White)/71(Gray), Ford=1(Blue)/4(Red), Chevy=4(Red)/14(Yellow),
Nissan=4(Red)/15(White), Toyota=4(Red)/15(White), Honda=15(White)/4(Red)

## Per-Body-Style Tips
- Sports/Supercar: mid-engine (taller rear), large diffuser, low roofline, add rear wing
- F1/Race car: no roof, front+rear wings, open cockpit, Halo bar, nose_cone + sidepod
- SUV/Off-road: taller body, large wheel arches, boxy shape, roof rack
- Sedan: 3-box (hood/cabin/trunk), balanced proportions
- Pickup: cab + flat cargo bed at rear
- Hatchback: short rear overhang, steep rear window

## Brand Features Library
When the prompt includes a "Brand Features Reference" section, use those coordinates
as guidance for placing extra_parts. The brand library provides real-world feature
positions (rear wing height, exhaust location, etc.) for accurate replication.

## Rules
1. Only use parts from the provided catalog — never invent part numbers
2. Only output X >= 0 for extra_parts (system auto-mirrors to left)
3. Match the real car's front grille, headlights, roofline, rear lights, side profile
4. Use real LEGO color IDs from the provided palette
5. Use replace_rules to swap template parts for better brand match (e.g., grille tile)
6. Keep extra_parts minimal — only add what the template is missing"""

    def __init__(self, storage_path: str | None = None):
        self.storage = Path(storage_path or settings.storage_path)
        self.storage.mkdir(parents=True, exist_ok=True)

    async def generate(
        self,
        design_id: str,
        make: str,
        model: str,
        year: int,
        mod_ids: list[str] | None = None,
        custom_request: str = "",
        flagship_metadata: dict | None = None,
        scale: str | None = None,
    ) -> dict:
        """Generate a Studio .io file for a car model via the LangGraph design graph.

        Args:
            design_id: UUID for this design
            make/model/year: Target car
            mod_ids: List of mod part IDs to apply
            custom_request: Free-text customization description
            flagship_metadata: Technic flagship specs (engine, gearbox, doors, etc.)
            scale: Target LEGO scale (only "1:38" supports AI generation)
        """
        # Imported here to avoid circular import: design_graph.py imports
        # StudioDesignGenerator at module level for SYSTEM_PROMPT + helpers.
        from app.agents.design_graph import build_design_graph

        scale = validate_scale(scale)
        graph = build_design_graph()
        initial_state = {
            "design_id": design_id,
            "make": make,
            "model": model,
            "year": year,
            "scale": scale,
            "mod_ids": mod_ids or [],
            "custom_request": custom_request,
            "flagship_metadata": flagship_metadata,
            "messages": [],
            "design_output": None,
            "retry_count": 0,
            "status": "",
            "error_message": "",
        }
        result = await graph.ainvoke(initial_state)

        # Map graph state → return-dict shape expected by callers.
        status = result.get("status", "completed")
        return {
            "status": status,
            "parts_count": result.get("parts_count", 0),
            "difficulty": result.get("difficulty", "Medium"),
            "file_io_path": result.get("io_path", ""),
            "file_ldr_path": result.get("ldr_path", ""),
            "parts_data": result.get("parts_data", []),
            "design_notes": result.get("design_notes", ""),
            "body_color_id": result.get("body_color_id", 4),
            "metadata": result.get("metadata", {}),
            "error_message": result.get("error_message", ""),
        }

    def _build_ldraw(self, data: dict, make: str, model: str, year: int) -> str:
        """Build complete LDraw content from structured output.

        Groups parts by build step with `0 STEP` separators.
        Auto-mirrors every part with X > 0.1 to -X with flipped rotation
        (negate columns 0, 3, 6 of the rotation matrix). The LLM only
        outputs the right half; this function creates the left side.
        """
        lines = [
            f"0 {year} {make} {model}",
            "0 Author: Car2LEGO AI (Claude + Studio 2.26.6)",
            f"0 Name: {make}_{model}_{year}",
            "0 !LICENSE Redistributable under CC BY 4.0",
            "0",
            f"0 // Design Notes: {data.get('design_notes', '')}",
            "0",
        ]

        parts = data.get("parts", [])
        # Auto-mirror: every part with X > 0.1 gets a copy at -X
        expanded: list[dict] = []
        for p in parts:
            x = float(p.get("x", 0))
            expanded.append(p)
            if abs(x) > 0.1:
                mirrored = dict(p)
                mirrored["x"] = -x
                # Flip rotation matrix X-column (indices 0, 3, 6)
                rot = p.get("rotation", "1 0 0 0 1 0 0 0 1").strip().split()
                if len(rot) == 9:
                    rot[0] = f"{-float(rot[0]):.6g}"
                    rot[3] = f"{-float(rot[3]):.6g}"
                    rot[6] = f"{-float(rot[6]):.6g}"
                    mirrored["rotation"] = " ".join(rot)
                expanded.append(mirrored)

        # Group by step
        steps: dict[int, list[dict]] = {}
        for p in expanded:
            step = p.get("step", 1)
            steps.setdefault(step, []).append(p)

        for step_num in sorted(steps.keys()):
            lines.append("0 STEP")
            for p in steps[step_num]:
                rot = p.get("rotation", "1 0 0 0 1 0 0 0 1")
                rot_parts = rot.strip().split()
                if len(rot_parts) != 9:
                    rot_parts = ["1", "0", "0", "0", "1", "0", "0", "0", "1"]

                for q in range(p.get("quantity", 1)):
                    x = float(p["x"])
                    if p.get("quantity", 1) > 1 and q == 1 and abs(x) > 1:
                        x = -x
                    lines.append(
                        f"1 {p['color_id']} "
                        f"{x:.1f} {float(p['y']):.1f} {float(p['z']):.1f} "
                        f"{rot_parts[0]} {rot_parts[1]} {rot_parts[2]} "
                        f"{rot_parts[3]} {rot_parts[4]} {rot_parts[5]} "
                        f"{rot_parts[6]} {rot_parts[7]} {rot_parts[8]} "
                        f"{p['part_num']}"
                    )

        lines.append("0")
        return "\n".join(lines)

    def _build_parts_data(self, data: dict) -> list[dict]:
        """Deduplicate parts for database storage.

        Auto-mirrors parts with X > 0.1 (each counts as 2x).
        """
        from collections import Counter
        key_counter = Counter()
        part_map = {}
        for p in data.get("parts", []):
            key = (p["part_num"], p["color_id"])
            qty = p.get("quantity", 1)
            if abs(float(p.get("x", 0))) > 0.1:
                qty *= 2  # auto-mirrored copy doubles the count
            key_counter[key] += qty
            part_map[key] = p.get("bricklink_id", p["part_num"].replace(".dat", ""))

        return [
            {
                "part_num": part_num,
                "ldraw_color_id": color_id,
                "quantity": qty,
                "bricklink_id": part_map.get((part_num, color_id), part_num.replace(".dat", "")),
            }
            for (part_num, color_id), qty in key_counter.items()
        ]

    @staticmethod
    def _estimate_difficulty(parts_count: int) -> str:
        if parts_count < 80: return "Easy"
        elif parts_count < 180: return "Medium"
        elif parts_count < 400: return "Hard"
        return "Expert"
