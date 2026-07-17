"""Celery task for LLM-based design customization."""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.design import Design, DesignPart
from app.services.customization_service import CustomizationService
from tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def customize_design(
    self,
    new_design_id: str,
    base_design_id: str,
    car_info: str,
    customization_request: str,
):
    """Customize an existing LEGO car design using Claude LLM.

    Args:
        new_design_id: UUID for the new customized design record
        base_design_id: UUID of the base design to modify
        car_info: Car description string
        customization_request: User's modification instructions
    """
    self.update_state(state="PROCESSING", meta={"stage": "analyzing_customization"})

    # Load the base design's LDraw content
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        base_data = loop.run_until_complete(_load_base_design(base_design_id))
    finally:
        loop.close()

    if not base_data:
        self.update_state(state="FAILURE", meta={"error": "Base design not found"})
        raise Exception("Base design not found")

    # Run customization
    service = CustomizationService()
    result = service.customize(
        design_id=new_design_id,
        base_ldr_content=base_data["ldr_content"],
        base_parts_summary=base_data["parts_summary"],
        car_info=car_info,
        customization_request=customization_request,
    )

    # Update database
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(_update_customized_design(new_design_id, result))
    finally:
        loop.close()

    if result["status"] == "failed":
        self.update_state(
            state="FAILURE",
            meta={"error": result.get("error_message", "Customization failed")},
        )
        raise Exception(result.get("error_message", "Customization failed"))

    return {
        "status": "completed",
        "design_id": new_design_id,
        "parts_count": result.get("parts_count", 0),
        "added_parts": result.get("added_parts", 0),
        "removed_parts": result.get("removed_parts", 0),
        "notes": result.get("design_notes", ""),
    }


async def _load_base_design(design_id: str) -> dict | None:
    """Load base design parts and LDraw content."""
    from pathlib import Path
    from app.config import settings

    async with async_session() as db:
        stmt = (
            select(Design)
            .where(Design.id == design_id)
            .options(selectinload(Design.parts))
        )
        result = await db.execute(stmt)
        design = result.scalar_one_or_none()

        if not design:
            return None

        # Build parts summary
        from collections import Counter
        parts_counter = Counter()
        for p in design.parts:
            parts_counter[(p.part_num, p.ldraw_color_id)] += p.quantity

        summary_lines = [f"Base design has {design.parts_count or 0} total parts:"]
        for (part_num, color_id), qty in sorted(parts_counter.items()):
            summary_lines.append(f"  - {part_num} (color {color_id}): {qty}x")

        # Try to load LDraw file
        ldr_content = ""
        if design.file_ldr_path:
            ldr_path = Path(settings.storage_path) / design.file_ldr_path
            if ldr_path.exists():
                ldr_content = ldr_path.read_text(encoding="utf-8")
        else:
            # Generate minimal LDraw from parts
            from app.services.ldraw_service import LDrawService
            part_tuples = []
            for p in design.parts:
                for _ in range(p.quantity):
                    part_tuples.append((p.ldraw_color_id, 0, 0, 0, p.part_num))
            ldr_content = LDrawService.create_basic_ldraw(
                part_tuples, name=f"Base Design {design_id}"
            )

        return {
            "parts_summary": "\n".join(summary_lines),
            "ldr_content": ldr_content,
        }


async def _update_customized_design(design_id: str, result: dict):
    """Update the customized design record with results."""
    async with async_session() as db:
        try:
            stmt = (
                select(Design)
                .where(Design.id == design_id)
                .options(selectinload(Design.parts))
            )
            res = await db.execute(stmt)
            design = res.scalar_one_or_none()

            if not design:
                return

            if result["status"] == "completed":
                design.status = "completed"
                design.completed_at = datetime.now(timezone.utc)
                design.parts_count = result.get("parts_count", 0)
                design.difficulty = result.get("difficulty", "Medium")
                design.file_ldr_path = result.get("file_ldr_path")
                design.file_io_path = result.get("file_io_path")
                design.metadata_ = result.get("metadata", {})

                for part_data in result.get("parts_data", []):
                    design_part = DesignPart(
                        design_id=design.id,
                        part_num=part_data["part_num"],
                        ldraw_color_id=part_data["ldraw_color_id"],
                        quantity=part_data["quantity"],
                        bricklink_id=part_data.get("bricklink_id"),
                    )
                    db.add(design_part)
            else:
                design.status = "failed"
                design.error_message = result.get("error_message")

            await db.commit()
        except Exception as e:
            await db.rollback()
            raise e
