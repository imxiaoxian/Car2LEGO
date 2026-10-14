"""Celery tasks for Studio-integrated LEGO design generation.

Uses OpenAI models and generated image references for Studio .io generation.
User opens the .io file directly in BrickLink Studio for viewing.
"""

import asyncio
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session
from app.models.design import Design
from app.services.design_parts import replace_design_parts
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
    vehicle_features: dict | None = None,
    source_image_path: str = "",
):
    """Generate a Studio .io file for a car model.

    The output is a BrickLink Studio .io file that the user opens directly.
    Studio handles all 3D rendering, instruction generation, and parts management.
    """
    self.update_state(state="PROCESSING", meta={"stage": "analyzing_car"})

    async def _run_generation():
        async with async_session() as db:
            design = await db.get(Design, uuid.UUID(design_id))
            if design is None:
                raise ValueError("Design not found")
            design.status = "processing"
            await db.commit()
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
            vehicle_features=vehicle_features,
            source_image_path=source_image_path,
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
        "status": result["status"],
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
                .where(Design.id == uuid.UUID(design_id))
                .options(selectinload(Design.parts))
            )
            res = await db.execute(stmt)
            design = res.scalar_one_or_none()
            if not design:
                return

            if result["status"] in ("pending", "processing"):
                design.status = result["status"]
            elif result["status"] in ("completed", "draft", "paused", "cancelled"):
                design.status = result["status"]
                design.completed_at = datetime.now(timezone.utc) if result["status"] == "completed" else None
                design.parts_count = result.get("parts_count", 0)
                design.difficulty = result.get("difficulty", "Medium")
                design.file_io_path = result.get("file_io_path")
                design.file_ldr_path = result.get("file_ldr_path")
                design.file_pdf_path = result.get("file_pdf_path")
                design.steps_count = result.get("steps_count")
                design.error_message = result.get("error_message") or None
                design.metadata_ = {**(design.metadata_ or {}), **result.get("metadata", {})}

                await replace_design_parts(db, design.id, result.get("parts_data", []))
            else:
                design.status = "failed"
                design.error_message = result.get("error_message")

            await db.commit()
        except Exception as e:
            await db.rollback()
            raise e
