"""Export endpoints — download LDraw, BrickLink XML, CSV, and PDF files."""

import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import get_db
from app.models.design import Design, DesignPart
from app.services.export_service import ExportService

router = APIRouter()


async def _get_design_with_parts(design_id: uuid.UUID, db: AsyncSession) -> Design:
    """Helper: load a design with its parts or raise 404."""
    stmt = (
        select(Design)
        .where(Design.id == design_id)
        .options(selectinload(Design.parts))
    )
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    return design


@router.get("/xml/{design_id}")
async def export_xml(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Export BrickLink Wanted List XML for purchasing all parts."""
    design = await _get_design_with_parts(design_id, db)
    xml_content = ExportService.generate_bricklink_xml(design, design.parts)
    return PlainTextResponse(
        content=xml_content,
        media_type="application/xml",
        headers={
            "Content-Disposition": f"attachment; filename=car2lego-{design_id}.xml"
        },
    )


@router.get("/csv/{design_id}")
async def export_csv(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Export parts list as CSV."""
    design = await _get_design_with_parts(design_id, db)
    csv_content = ExportService.generate_csv(design, design.parts)
    return PlainTextResponse(
        content=csv_content,
        media_type="text/csv",
        headers={
            "Content-Disposition": f"attachment; filename=car2lego-{design_id}.csv"
        },
    )


@router.get("/ldr/{design_id}")
async def export_ldr(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download LDraw .ldr file for the design."""
    design = await _get_design_with_parts(design_id, db)

    # If design has a stored LDR file, serve it
    if design.file_ldr_path:
        file_path = Path(settings.storage_path) / design.file_ldr_path
        if file_path.exists():
            return FileResponse(
                file_path,
                media_type="application/octet-stream",
                filename=f"car2lego-{design_id}.ldr",
            )

    # Otherwise generate basic LDR
    ldr_content = ExportService.generate_ldr_content(design)
    return PlainTextResponse(
        content=ldr_content,
        media_type="text/plain",
        headers={
            "Content-Disposition": f"attachment; filename=car2lego-{design_id}.ldr"
        },
    )


@router.get("/io/{design_id}")
async def export_io(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download Studio .io file for the design."""
    design = await _get_design_with_parts(design_id, db)

    if design.file_io_path:
        file_path = Path(settings.storage_path) / design.file_io_path
        if file_path.exists():
            return FileResponse(
                file_path,
                media_type="application/octet-stream",
                filename=f"car2lego-{design_id}.io",
            )

    raise HTTPException(
        status_code=404,
        detail=".io file not yet generated. For AI designs, wait for completion.",
    )


@router.get("/pdf/{design_id}")
async def export_pdf(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download PDF building instructions."""
    design = await _get_design_with_parts(design_id, db)

    if design.file_pdf_path:
        file_path = Path(settings.storage_path) / design.file_pdf_path
        if file_path.exists():
            return FileResponse(
                file_path,
                media_type="application/pdf",
                filename=f"car2lego-{design_id}.pdf",
            )

    raise HTTPException(
        status_code=404,
        detail="PDF instructions not yet generated.",
    )
