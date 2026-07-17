"""Celery tasks for Studio-integrated LEGO design generation.

Uses Claude API → Studio .io file generation.
User opens the .io file directly in BrickLink Studio for viewing.
"""

import asyncio
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.design import Design, DesignPart
from app.services.studio_design_generator import StudioDesignGenerator
from tasks.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def generate_lego_design(
    self,
    design_id: str,
    make: str,
    model: str,
    year: int,
    mod_ids: list[str] | None = None,
    custom_request: str = "",
    flagship_metadata: dict | None = None,
    scale: str = "1:38",
):
    """Generate a Studio .io file for a car model.

    The output is a BrickLink Studio .io file that the user opens directly.
    Studio handles all 3D rendering, instruction generation, and parts management.
    """
    self.update_state(state="PROCESSING", meta={"stage": "analyzing_car"})

    async def _run_generation():
        generator = StudioDesignGenerator()
        result = await generator.generate(
            design_id=design_id,
            make=make,
            model=model,
            year=year,
            mod_ids=mod_ids,
            custom_request=custom_request,
            flagship_metadata=flagship_metadata,
            scale=scale,
        )
        await _update_design(design_id, result)
        return result

    try:
        result = asyncio.run(_run_generation())
    except Exception as e:
        self.update_state(
            state="FAILURE",
            meta={"error": str(e)},
        )
        raise

    if result["status"] == "failed":
        self.update_state(
            state="FAILURE",
            meta={"error": result.get("error_message", "Generation failed")},
        )
        raise Exception(result.get("error_message"))

    return {
        "status": "completed",
        "design_id": design_id,
        "parts_count": result.get("parts_count", 0),
        "io_file": result.get("file_io_path", ""),
        "design_notes": result.get("design_notes", ""),
    }


async def _update_design(design_id: str, result: dict):
    """Update design record with generation results."""
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
                design.file_io_path = result.get("file_io_path")
                design.file_ldr_path = result.get("file_ldr_path")
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
