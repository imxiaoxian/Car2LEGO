"""LLM-based car customization service (LangGraph pipeline).

Takes an existing LEGO car design + user modification instructions →
the LangGraph customization graph produces a modified complete design →
returns updated .io + parts list.

The single-shot LLM call path has been removed in Phase 5. All
customization now flows through `app.agents.customization_graph`.
"""

import asyncio
from pathlib import Path

from app.config import settings


class CustomizationService:
    """Orchestrates LLM-based design customization via LangGraph.

    Given a base design (parts + LDraw data) and a user's modification
    request, delegates to the customization graph which uses a ReAct
    agent + structured output to produce a modified parts list.
    """

    SYSTEM_PROMPT = """You are a master LEGO car customization expert. Your specialty is taking an existing LEGO car design and applying modifications — body kits, spoilers, wheel swaps, color changes, convertible conversions, wide-body kits, racing stripes, etc.

## Your Task

Given:
1. The complete parts list of an existing LEGO car design (with exact 3D coordinates)
2. The user's customization request

You will output a **modified** complete parts list that incorporates the requested changes.

## Modification Guidelines

1. **Preserve structure**: Keep parts that the user didn't ask to change. Only modify/add/remove what's needed.
2. **Part selection**: Use parts from the provided catalog. Match the style of the existing build.
3. **Color consistency**: If swapping a body panel, match the existing body color. For new accent parts, use contrasting colors that work with the base.
4. **Structural integrity**: Modified designs must still be buildable. Added parts must connect to existing structure. Don't leave floating pieces.
5. **Scale**: Stay in Speed Champions 6-wide scale. Don't dramatically change the car's proportions unless the user explicitly asks.
6. **Coordinate system**: Same LDraw system as the base design (X=left-right, Y=up-down, Z=front-back, units in LDU).

## Common Modification Types

- **Body kit**: Add front splitter, side skirts, rear diffuser (use wedges/slopes at low Y)
- **Spoiler/wing**: Add rear wing elements (mount at high Y, rear Z)
- **Wheel swap**: Replace wheel parts with different sizes/styles
- **Color change**: Change color_id on body panels (keep part_num and position)
- **Roof conversion**: Convert coupe→convertible (remove roof parts, add windshield frame)
- **Wide body**: Add fender flares (curved slopes at wheel arches with wider X)
- **Racing livery**: Add tiles/plates in accent colors on the body surface
- **Engine detail**: Add mechanical parts visible through rear window/engine cover
- **Exhaust**: Add or modify exhaust tips (round plates/taps at rear bumper)
- **Lighting**: Modify headlight/taillight design

## Output

Call the output_customized_design function with your complete modified parts list.
The parts list should be COMPLETE — include all parts from the base design that should be kept, plus new parts, minus removed parts."""

    def __init__(self, storage_path: str | None = None):
        self.storage = Path(storage_path or settings.storage_path)
        self.storage.mkdir(parents=True, exist_ok=True)

    def customize(
        self,
        design_id: str,
        base_ldr_content: str,
        base_parts_summary: str,
        car_info: str,              # e.g., "2020 Porsche 911 Turbo"
        customization_request: str,  # e.g., "Add a large rear wing and wider fenders"
    ) -> dict:
        """Run the customization pipeline synchronously (for Celery tasks).

        Args:
            design_id: New design ID for the customized result
            base_ldr_content: Full LDraw content of the base design
            base_parts_summary: Human-readable summary of base design parts
            car_info: Car description string
            customization_request: What the user wants to change

        Returns:
            Dict with paths and status for updating the design record
        """
        return asyncio.run(self.customize_async(
            design_id=design_id,
            base_ldr_content=base_ldr_content,
            base_parts_summary=base_parts_summary,
            car_info=car_info,
            customization_request=customization_request,
        ))

    async def customize_async(
        self,
        design_id: str,
        base_ldr_content: str,
        base_parts_summary: str,
        car_info: str,
        customization_request: str,
    ) -> dict:
        """Run the customization pipeline asynchronously (for async callers).

        Args:
            design_id: New design ID for the customized result
            base_ldr_content: Full LDraw content of the base design
            base_parts_summary: Human-readable summary of base design parts
            car_info: Car description string
            customization_request: What the user wants to change

        Returns:
            Dict with paths and status for updating the design record
        """
        # Imported here to avoid circular import: customization_graph.py
        # imports CustomizationService at module level for SYSTEM_PROMPT.
        from app.agents.customization_graph import build_customization_graph

        graph = build_customization_graph()
        initial_state = {
            "design_id": design_id,
            "base_ldr_content": base_ldr_content,
            "base_parts_summary": base_parts_summary,
            "car_info": car_info,
            "customization_request": customization_request,
            "messages": [],
            "design_output": None,
            "status": "",
            "error_message": "",
        }

        try:
            result = await graph.ainvoke(initial_state)
        except Exception as exc:
            return {"status": "failed", "error_message": f"Customization graph failed: {exc}"}

        return {
            "status": result.get("status", "completed"),
            "parts_count": result.get("parts_count", 0),
            "difficulty": result.get("difficulty", "Medium"),
            "file_ldr_path": result.get("ldr_path", ""),
            "file_io_path": result.get("io_path", ""),
            "file_pdf_path": None,
            "parts_data": result.get("parts_data", []),
            "design_notes": result.get("modification_summary", ""),
            "added_parts": result.get("added_parts", 0),
            "removed_parts": result.get("removed_parts", 0),
            "metadata": result.get("metadata", {}),
        }
