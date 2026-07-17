"""Design endpoints — the core API for creating and retrieving LEGO designs."""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.deps import get_db
from app.models.design import Design, DesignPart
from app.models.car import Car
from app.schemas.car import (
    CarResponse,
    CustomizationRequest,
    CustomizationResponse,
    DesignCreate,
    DesignDetailResponse,
    DesignResponse,
    DesignPartResponse,
    DesignStatusResponse,
    MatchInfo,
)
from app.services.car_research import CarResearchService
from app.services.car_specs_service import CarSpecsService

from fastapi import UploadFile, File, Form as FastForm
from app.services.matching_engine import MatchingEngine

MATCH_LABELS = {1: "Official LEGO Set", 2: "Community Design", 3: "Template", 4: "AI Generated"}

router = APIRouter()


def _build_match_info(match_result) -> MatchInfo:
    """Helper to convert internal MatchResult to API schema."""
    return MatchInfo(
        level=match_result.level,
        label=match_result.label,
        confidence=match_result.confidence,
        set_num=match_result.set_num,
        set_name=match_result.set_name,
        moc_name=match_result.moc_name,
        moc_author=match_result.moc_author,
    )


async def _car_to_response(car: Car | None) -> CarResponse | None:
    """Convert Car model to CarResponse schema."""
    if car is None:
        return None
    return CarResponse(
        id=car.id,
        make=car.make,
        model=car.model,
        year=car.year,
        trim=car.trim,
        body_style=car.body_style,
        image_url=car.image_url,
        created_at=car.created_at,
    )


async def _design_to_detail(
    design: Design, db: AsyncSession
) -> DesignDetailResponse:
    """Build a full DesignDetailResponse including car and parts."""
    match_result = None
    if design.match_level:
        from app.services.matching_engine import MatchResult
        match_result = MatchResult(
            level=design.match_level,
            label=MATCH_LABELS.get(design.match_level, "Unknown"),
            confidence=0.9 if design.match_level == 1 else 0.7,
            set_num=design.matched_set_num,
            set_name=design.matched_set.name if design.matched_set else None,
        )

    parts_list = []
    if design.parts:
        for p in design.parts:
            parts_list.append(
                DesignPartResponse(
                    part_num=p.part_num,
                    ldraw_color_id=p.ldraw_color_id,
                    quantity=p.quantity,
                    bricklink_id=p.bricklink_id,
                )
            )

    return DesignDetailResponse(
        id=design.id,
        car_id=design.car_id,
        match=_build_match_info(match_result) if match_result else None,
        status=design.status,
        parts_count=design.parts_count,
        difficulty=design.difficulty,
        created_at=design.created_at,
        completed_at=design.completed_at,
        error_message=design.error_message,
        car=await _car_to_response(design.car) if design.car else None,
        parts=parts_list,
        parent_design_id=design.parent_design_id,
        customization_request=design.customization_request,
        file_urls={
            "io": f"/api/v1/export/io/{design.id}" if design.file_io_path else "",
            "ldr": f"/api/v1/export/ldr/{design.id}" if design.file_ldr_path else "",
            "pdf": f"/api/v1/export/pdf/{design.id}" if design.file_pdf_path else "",
            "xml": f"/api/v1/export/xml/{design.id}",
            "csv": f"/api/v1/export/csv/{design.id}",
        },
    )


async def _run_sync_generation(db: AsyncSession, design: Design, car: Car) -> None:
    """Run AI generation synchronously (Celery fallback for dev / no-Redis)."""

    from app.services.studio_design_generator import StudioDesignGenerator

    design.status = "processing"
    await db.flush()

    try:
        generator = StudioDesignGenerator()
        # Pass flagship metadata if available (L1 match on Technic 1:8 supercar)
        flagship = (design.metadata_ or {}).get("flagship")
        result = await generator.generate(
            design_id=str(design.id),
            make=car.make,
            model=car.model,
            year=car.year,
            flagship_metadata=flagship,
            scale=design.scale,
        )

        if result["status"] == "completed":
            design.status = "completed"
            design.parts_count = result.get("parts_count", 0)
            design.difficulty = result.get("difficulty", "Medium")
            design.file_io_path = result.get("file_io_path")
            design.file_ldr_path = result.get("file_ldr_path")
            design.metadata_ = (design.metadata_ or {}) | (result.get("metadata", {}) or {})

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
            design.error_message = result.get("error_message", "Generation failed")
    except Exception as exc:
        design.status = "failed"
        design.error_message = str(exc)

    await db.flush()


async def _run_sync_customization(
    db: AsyncSession,
    new_design: Design,
    base_design: Design,
    car_info: str,
    customization_request: str,
) -> None:
    """Run customization synchronously (Celery fallback for dev / no-Redis).

    Builds the parts summary + LDraw preview from `base_design`, runs the
    customization graph, and updates `new_design` with the result.
    """
    from collections import Counter
    from pathlib import Path

    from app.services.customization_service import CustomizationService

    new_design.status = "processing"
    await db.flush()

    try:
        parts_counter = Counter()
        for p in base_design.parts:
            parts_counter[(p.part_num, p.ldraw_color_id)] += p.quantity
        summary_lines = [f"Base design has {base_design.parts_count or 0} total parts:"]
        for (part_num, color_id), qty in sorted(parts_counter.items()):
            summary_lines.append(f"  - {part_num} (color {color_id}): {qty}x")
        parts_summary = "\n".join(summary_lines)

        ldr_content = ""
        if base_design.file_ldr_path:
            ldr_path = Path(settings.storage_path) / base_design.file_ldr_path
            if ldr_path.exists():
                ldr_content = ldr_path.read_text(encoding="utf-8")

        service = CustomizationService()
        result = await service.customize_async(
            design_id=str(new_design.id),
            base_ldr_content=ldr_content,
            base_parts_summary=parts_summary,
            car_info=car_info,
            customization_request=customization_request,
        )

        if result["status"] == "completed":
            new_design.status = "completed"
            new_design.parts_count = result.get("parts_count", 0)
            new_design.difficulty = result.get("difficulty", "Medium")
            new_design.file_io_path = result.get("file_io_path")
            new_design.file_ldr_path = result.get("file_ldr_path")
            new_design.metadata_ = (new_design.metadata_ or {}) | (result.get("metadata", {}) or {})

            for part_data in result.get("parts_data", []):
                design_part = DesignPart(
                    design_id=new_design.id,
                    part_num=part_data["part_num"],
                    ldraw_color_id=part_data["ldraw_color_id"],
                    quantity=part_data["quantity"],
                    bricklink_id=part_data.get("bricklink_id"),
                )
                db.add(design_part)
        else:
            new_design.status = "failed"
            new_design.error_message = result.get("error_message", "Customization failed")
    except Exception as exc:
        new_design.status = "failed"
        new_design.error_message = str(exc)

    await db.flush()


def _preprocess_uploaded_image(data: bytes, suffix: str) -> bytes:
    """Preprocess an uploaded car photo before sending to Claude Vision.

    - Resizes to max 2048px on the longest side (Claude downsamples large images anyway)
    - Corrects EXIF orientation (prevents rotated photos)
    - Converts to JPEG at 85% quality for consistent size
    - Handles WebP, HEIC (via Pillow), and common formats

    Returns the processed image bytes.
    """
    from io import BytesIO

    try:
        from PIL import Image, ImageOps

        img = Image.open(BytesIO(data))

        # Apply EXIF orientation (phones often tag rotation)
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if needed (RGBA, P, etc.)
        if img.mode in ("RGBA", "P", "LA"):
            img = img.convert("RGB")

        # Resize if larger than 2048px on longest side
        max_dim = 2048
        w, h = img.size
        if w > max_dim or h > max_dim:
            ratio = min(max_dim / w, max_dim / h)
            new_size = (int(w * ratio), int(h * ratio))
            img = img.resize(new_size, Image.LANCZOS)

        # Save as JPEG for consistent, compact output
        out = BytesIO()
        img.save(out, format="JPEG", quality=85, optimize=True)
        return out.getvalue()
    except Exception:
        # If Pillow processing fails, return original data
        return data


async def _import_set_parts(db: AsyncSession, design: Design, set_num: str) -> None:
    """Import real parts for an L1-matched LEGO set from Rebrickable API.

    Falls back gracefully: Rebrickable API not configured → leaves parts
    list empty with parts_count from the set's brick_count for reference.
    """
    from app.integrations.rebrickable import rebrickable_client

    try:
        rb_parts = await rebrickable_client.get_set_parts(set_num)
    except Exception:
        rb_parts = []

    if not rb_parts:
        # Rebrickable not available — parts_count from brick_count is
        # already set on the design; individual parts remain empty.
        return

    # Merge duplicates: Rebrickable may return same (part_num, color) as
    # alternate items or spare parts. We aggregate by unique key.
    merged: dict[tuple[str, int], tuple[str, int]] = {}
    for rb_part in rb_parts:
        part_num = rb_part.get("part", {}).get("part_num", "")
        if not part_num:
            continue

        color_info = rb_part.get("color", {})
        # Rebrickable returns "external_ids" mapping for BrickLink
        external = rb_part.get("part", {}).get("external_ids", {})
        bricklink_ids = external.get("BrickLink", [])
        bricklink_id = bricklink_ids[0] if bricklink_ids else part_num

        ldraw_color_id = _map_rebrickable_color_to_ldraw(
            color_info.get("id"), color_info.get("name", "")
        )

        quantity = rb_part.get("quantity", 1)
        if isinstance(quantity, str):
            try:
                quantity = int(quantity)
            except ValueError:
                quantity = 1

        key = (part_num, ldraw_color_id)
        if key in merged:
            prev_bl_id, prev_qty = merged[key]
            merged[key] = (prev_bl_id, prev_qty + quantity)
        else:
            merged[key] = (bricklink_id, quantity)

    imported = 0
    for (part_num, ldraw_color_id), (bricklink_id, quantity) in merged.items():
        design_part = DesignPart(
            design_id=design.id,
            part_num=part_num,
            ldraw_color_id=ldraw_color_id,
            quantity=quantity,
            bricklink_id=bricklink_id,
        )
        db.add(design_part)
        imported += 1

    # Update parts_count to reflect actual imported (unique) count
    if imported > 0:
        design.parts_count = imported
    await db.flush()


async def _build_io_from_parts(db: AsyncSession, design: Design) -> None:
    """Build a .io file directly from imported parts (e.g. Rebrickable).

    Arranges parts in a simple exploded grid layout. The .io file serves as
    a complete parts catalog that the user can rearrange in Studio.
    """
    from pathlib import Path as FilePath
    from app.services.studio_service import StudioService
    from app.services.ldraw_service import LDrawService
    from app.config import settings

    # Query parts from DB
    result = await db.execute(
        select(DesignPart).where(DesignPart.design_id == design.id)
    )
    parts = result.scalars().all()
    if not parts:
        return

    ldraw_lines = [
        f"0 {design.matched_set_num or 'LEGO Set'} — Parts Reference",
        f"0 Name: {design.matched_set_num or 'imported'}",
        "0 Author: Car2LEGO (Rebrickable)",
        "0 !LICENSE Redistributable under CC BY 4.0",
        "0",
        f"0 // {len(parts)} unique part types — arrange in Studio",
        "0",
    ]

    row_z = 0
    for i, part in enumerate(parts):
        if i > 0 and i % 8 == 0:
            ldraw_lines.append("0 STEP")
            row_z += 40
        col_x = (i % 8) * 30 - 105
        ldraw_lines.append(
            LDrawService.make_part_line(
                part.ldraw_color_id, col_x, 8, row_z, part.part_num
            )
        )

    ldr_content = "\n".join(ldraw_lines)

    car_name = f"{design.matched_set_num or 'LEGO'}"
    studio_file = StudioService.create_studio_file(
        ldr_content=ldr_content,
        name=car_name,
        description=f"Parts imported from {design.matched_set_num}",
    )

    storage = FilePath(settings.storage_path)
    design_dir = storage / str(design.id)
    design_dir.mkdir(parents=True, exist_ok=True)

    io_path = design_dir / "model.io"
    studio_file.save(io_path)
    design.file_io_path = str(io_path.relative_to(storage))

    ldr_path = design_dir / "model.ldr"
    ldr_path.write_text(ldr_content, encoding="utf-8")
    design.file_ldr_path = str(ldr_path.relative_to(storage))


def _map_rebrickable_color_to_ldraw(color_id: int | None, color_name: str) -> int:
    """Map Rebrickable color id/name to LDraw color id.

    Rebrickable color IDs differ from LDraw IDs. This provides a best-effort
    mapping for the most common LEGO colors used in car sets.
    """
    # Common Rebrickable → LDraw color mappings
    # Rebrickable uses their own numbering; LDraw uses 0-511 range
    _RB_TO_LDRAW: dict[int, int] = {
        1: 15,   # White
        2: 0,    # Black
        3: 4,    # Red
        4: 14,   # Yellow
        5: 1,    # Blue
        6: 2,    # Green
        7: 6,    # Brown
        8: 7,    # Dark Gray → Light Gray
        9: 8,    # Dark Gray
        10: 72,  # Dark Bluish Gray
        11: 71,  # Light Bluish Gray
        12: 3,   # Dark Turquoise → Teal
        13: 19,  # Tan
        14: 334, # Gold
        15: 383, # Silver
        19: 25,  # Orange
        28: 320, # Dark Red
        35: 9,   # Light Blue
        36: 10,  # Bright Green
        41: 68,  # Dark Orange
        47: 11,  # Dark Turquoise
        54: 115, # Pearl Gold
        59: 383, # Chrome Silver
        69: 77,  # Pearl Dark Gray
        80: 73,  # Medium Blue
        87: 11,  # Dark Turquoise
    }

    # Fast path: exact match
    if color_id is not None and color_id in _RB_TO_LDRAW:
        return _RB_TO_LDRAW[color_id]

    # Fuzzy path: match by color name keywords
    name_lower = color_name.lower()
    if "white" in name_lower:
        return 15
    if "black" in name_lower:
        return 0
    if "red" in name_lower:
        return 4
    if "blue" in name_lower:
        return 1
    if "yellow" in name_lower:
        return 14
    if "green" in name_lower:
        return 2
    if "orange" in name_lower:
        return 25
    if "gray" in name_lower or "grey" in name_lower:
        return 72
    if "tan" in name_lower or "brown" in name_lower:
        return 6
    if "gold" in name_lower:
        return 334
    if "silver" in name_lower or "chrome" in name_lower:
        return 383

    # Default: white (most common color)
    return 15


@router.get("/scales")
async def list_scales():
    """List supported scale ratios and capabilities."""
    from app.services.studio_templates import SUPPORTED_SCALES, SCALE_SPECS
    return {
        "scales": [
            {
                "ratio": s,
                "ai_generation": SCALE_SPECS[s].get("ai_supported", False),
                "official_sets": True,  # Rebrickable import works for all
                "note": SCALE_SPECS[s]["note"],
            }
            for s in SUPPORTED_SCALES
        ],
        "default": "1:38",
    }


@router.post("", response_model=DesignDetailResponse, status_code=201)
async def create_design(
    design_in: DesignCreate,
    db: AsyncSession = Depends(get_db),
):
    """Submit a car and get back a LEGO design.

    This is the main entry point. The matching engine will try L1→L4
    and return the best available design.
    """
    # 1. Find or create car record
    stmt = select(Car).where(
        func.lower(Car.make) == design_in.make.lower(),
        func.lower(Car.model) == design_in.model.lower(),
        Car.year == design_in.year,
    )
    result = await db.execute(stmt)
    car = result.scalar_one_or_none()

    if not car:
        from app.integrations.nhtsa import nhtsa_client
        nhtsa_data = await nhtsa_client.get_vehicle_details(
            design_in.make, design_in.model, design_in.year
        )

        # If NHTSA doesn't recognize this car (common for non-US brands),
        # do web research to gather specs
        research_data = {}
        if not nhtsa_data.get("validated"):
            # Use Claude to search and extract car info
            research_data = {
                "researched": True,
                "official_domain": CarResearchService.get_official_domain(design_in.make),
                "search_queries": [
                    q["query"] for q in CarResearchService.build_search_queries(
                        design_in.make, design_in.model, design_in.year
                    )[:3]
                ],
            }

        car = Car(
            make=nhtsa_data["make"],
            model=nhtsa_data["model"],
            year=nhtsa_data["year"],
            body_style=nhtsa_data.get("body_style"),
            image_url=design_in.image_url,
            metadata_={**nhtsa_data, **research_data},
        )
        db.add(car)
        await db.flush()
        await db.refresh(car)

        # Persist basic specs into the CarSpec knowledge base for future
        # design generations. build_prompt_node will query this table.
        try:
            research_result = CarResearchService.build_research_result(
                make=car.make,
                model=car.model,
                year=car.year,
                nhtsa_data=nhtsa_data,
                research_data=research_data,
            )
            await CarSpecsService.save_specs(db, research_result)
        except Exception:
            pass

    # 2. Run matching engine
    engine = MatchingEngine(db)
    match_result = await engine.match(car.make, car.model, car.year)

    # 3. Create design record
    design = Design(
        car_id=car.id,
        match_level=match_result.level,
        status="completed" if match_result.is_immediate else "pending",
        matched_set_num=match_result.set_num,
        scale=design_in.scale,
        metadata_=match_result.metadata,
    )

    if match_result.level == 1 and match_result.set_num:
        # For L1 matches, mark parts_count from the set
        from app.models.lego_set import LegoSet
        set_result = await db.execute(
            select(LegoSet).where(LegoSet.set_num == match_result.set_num)
        )
        lego_set = set_result.scalar_one_or_none()
        if lego_set and lego_set.brick_count:
            design.parts_count = lego_set.brick_count

    db.add(design)
    await db.flush()
    await db.refresh(design)

    # 4. For L4 AI generation, try Celery dispatch with sync fallback
    if match_result.level == 4:
        generation_mode = os.getenv("GENERATION_MODE", "auto")
        redis_url = os.getenv("REDIS_URL", "")

        if redis_url and generation_mode != "sync":
            # Async path: dispatch to Celery worker
            try:
                from tasks.generation import generate_lego_design
                task = generate_lego_design.delay(
                    design_id=str(design.id),
                    make=car.make, model=car.model, year=car.year,
                )
                design.ai_job_id = task.id
                await db.flush()
            except Exception:
                # Celery dispatch failed — fall through to sync
                pass
            else:
                # Successfully dispatched — skip sync fallback
                pass
        else:
            # Sync path: run generation inline (dev / no-Redis fallback)
            # Design stays "pending" while we generate; we update inline after
            pass

        # If still pending (no Celery dispatch), run sync generation
        if not design.ai_job_id:
            await _run_sync_generation(db, design, car)

    # 5. For L1 matches, import real parts from Rebrickable
    if match_result.level == 1 and match_result.set_num:
        await _import_set_parts(db, design, match_result.set_num)

    # 6. Build .io file
    if match_result.is_immediate and not design.file_io_path:
        imported_parts = (design.parts_count or 0) > 50
        if imported_parts:
            await _build_io_from_parts(db, design)
            await db.flush()  # persist file_io_path before refresh
        elif design_in.scale == "1:38":
            design.status = "pending"
            await db.flush()
            await _run_sync_generation(db, design, car)
        else:
            design.status = "failed"
            design.error_message = (
                f"AI generation only supports 1:38 (Speed Champions). "
                f"For {design_in.scale}, the car must match an official LEGO set."
            )
            await db.flush()
        await db.refresh(design)

    # 6. Reload with relationships
    stmt = (
        select(Design)
        .where(Design.id == design.id)
        .options(
            selectinload(Design.car),
            selectinload(Design.parts),
            selectinload(Design.matched_set),
        )
    )
    result = await db.execute(stmt)
    design = result.scalar_one()

    return await _design_to_detail(design, db)


@router.get("", response_model=list[DesignResponse])
async def list_designs(
    limit: int = Query(default=20, le=100),
    offset: int = Query(default=0),
    db: AsyncSession = Depends(get_db),
):
    """List recent designs, newest first."""
    stmt = (
        select(Design)
        .order_by(Design.created_at.desc())
        .offset(offset)
        .limit(limit)
    )
    result = await db.execute(stmt)
    designs = result.scalars().all()

    return [
        DesignResponse(
            id=d.id,
            car_id=d.car_id,
            match=MatchInfo(
                level=d.match_level,
                label=MATCH_LABELS.get(d.match_level, "Unknown"),
                confidence=0.9,
                set_num=d.matched_set_num,
            ),
            status=d.status,
            parts_count=d.parts_count,
            difficulty=d.difficulty,
            created_at=d.created_at,
            completed_at=d.completed_at,
            error_message=d.error_message,
        )
        for d in designs
    ]


@router.get("/{design_id}", response_model=DesignDetailResponse)
async def get_design(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get full design details including car info and parts list."""
    stmt = (
        select(Design)
        .where(Design.id == design_id)
        .options(
            selectinload(Design.car),
            selectinload(Design.parts),
            selectinload(Design.matched_set),
        )
    )
    result = await db.execute(stmt)
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    return await _design_to_detail(design, db)


@router.get("/{design_id}/status", response_model=DesignStatusResponse)
async def get_design_status(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Poll for async design generation status (L4 AI tasks)."""
    result = await db.execute(
        select(Design).where(Design.id == design_id)
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    return DesignStatusResponse(
        id=design.id,
        status=design.status,
        progress=100 if design.status == "completed" else 0,
        error_message=design.error_message,
    )


@router.get("/{design_id}/ldr")
async def get_design_ldr(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get the raw LDraw content for 3D preview."""
    from pathlib import Path as FilePath
    result = await db.execute(
        select(Design).where(Design.id == design_id)
    )
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if design.file_ldr_path:
        ldr_path = FilePath(settings.storage_path) / design.file_ldr_path
        if ldr_path.exists():
            from fastapi.responses import PlainTextResponse
            return PlainTextResponse(
                ldr_path.read_text(encoding="utf-8"),
                media_type="text/plain",
            )

    raise HTTPException(status_code=404, detail="LDraw file not yet generated")


@router.get("/{design_id}/parts", response_model=list[DesignPartResponse])
async def get_design_parts(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get detailed parts list for a design."""
    result = await db.execute(
        select(DesignPart).where(DesignPart.design_id == design_id)
    )
    parts = result.scalars().all()

    from app.services.ldraw_service import LDrawService

    return [
        DesignPartResponse(
            part_num=p.part_num,
            ldraw_color_id=p.ldraw_color_id,
            color_name=LDrawService.get_color_name(p.ldraw_color_id),
            quantity=p.quantity,
            bricklink_id=p.bricklink_id,
        )
        for p in parts
    ]


@router.get("/{design_id}/open-in-studio")
async def open_in_studio(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Download the .io file for opening in BrickLink Studio."""
    from pathlib import Path as FilePath
    from fastapi.responses import FileResponse

    result = await db.execute(
        select(Design).where(Design.id == design_id)
    )
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if design.file_io_path:
        io_path = FilePath(settings.storage_path) / design.file_io_path
        if io_path.exists():
            car = design.car
            filename = f"{car.make}_{car.model}_{car.year}.io" if car else f"car2lego_{design_id}.io"
            return FileResponse(
                io_path,
                media_type="application/octet-stream",
                filename=filename,
                headers={"X-Studio-File": "true"},
            )

    raise HTTPException(status_code=404, detail="Studio .io file not yet generated. Wait for generation to complete.")


@router.post("/from-image", response_model=DesignDetailResponse, status_code=201)
async def create_design_from_image(
    make: str = FastForm(default=""),
    model: str = FastForm(default=""),
    year: int = FastForm(default=2020),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Create a LEGO design from a car photo. Claude Vision analyzes the image."""
    import tempfile
    import os
    suffix = os.path.splitext(image.filename or "car.jpg")[1] or ".jpg"
    tmp_path = tempfile.mktemp(suffix=suffix)
    try:
        raw_data = await image.read()
        # Preprocess image before sending to Vision API
        processed_data = _preprocess_uploaded_image(raw_data, suffix)
        with open(tmp_path, "wb") as f:
            f.write(processed_data)
        from app.services.vision_analyzer import VisionAnalyzer
        from app.api.v1.research import collect_taxonomy_suggestions
        analyzer = VisionAnalyzer()
        features = await analyzer.analyze_image(tmp_path)
        if analyzer.get_taxonomy_suggestions():
            collect_taxonomy_suggestions(analyzer.get_taxonomy_suggestions())
        if features:
            make = make or features.make
            model = model or features.model
            year = year or features.year
        if not make:
            make = "custom"
        if not model:
            model = "car"
        stmt = select(Car).where(func.lower(Car.make) == make.lower(), func.lower(Car.model) == model.lower(), Car.year == year)
        result = await db.execute(stmt)
        car = result.scalar_one_or_none()
        if not car:
            car = Car(make=make, model=model, year=year, body_style=features.body_style if features else None, metadata_={"vision": features.analysis_text} if features else {})
            db.add(car)
            await db.flush()
            await db.refresh(car)
        engine = MatchingEngine(db)
        match_result = await engine.match(car.make, car.model, car.year)
        design = Design(car_id=car.id, match_level=match_result.level, status="completed" if match_result.is_immediate else "pending", matched_set_num=match_result.set_num)
        if features:
            design.metadata_ = {"vision_features": {"color": features.primary_color_name, "lego_color": features.closest_lego_color, "body_style": features.body_style, "detected_mods": features.detected_mods}}
        db.add(design)
        await db.flush()
        await db.refresh(design)
        if match_result.level == 4:
            generation_mode = os.getenv("GENERATION_MODE", "auto")
            redis_url = os.getenv("REDIS_URL", "")

            if redis_url and generation_mode != "sync":
                try:
                    from tasks.generation import generate_lego_design
                    design.ai_job_id = generate_lego_design.delay(
                        design_id=str(design.id),
                        make=car.make, model=car.model, year=car.year,
                    ).id
                    await db.flush()
                except Exception:
                    pass

            if not design.ai_job_id:
                await _run_sync_generation(db, design, car)
        stmt = select(Design).where(Design.id == design.id).options(selectinload(Design.car), selectinload(Design.parts), selectinload(Design.matched_set))
        result = await db.execute(stmt)
        return await _design_to_detail(result.scalar_one(), db)
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


@router.get("/{design_id}/pricing")
async def get_design_pricing(design_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Get reference pricing for all parts in a design."""
    result = await db.execute(select(DesignPart).where(DesignPart.design_id == design_id))
    parts = result.scalars().all()
    from app.services.pricing_service import PricingService
    from app.services.ldraw_service import LDrawService
    parts_data = [{"part_num": p.part_num, "bricklink_id": p.bricklink_id or p.part_num, "color_name": LDrawService.get_color_name(p.ldraw_color_id), "quantity": p.quantity} for p in parts]
    return PricingService.price_parts_list(parts_data)


@router.post("/{design_id}/studio-open")
async def studio_open(
    design_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Open this design directly in BrickLink Studio.

    Launches Studio with the .io file. Studio handles all 3D viewing,
    rendering, instruction generation, and parts export.
    """
    from pathlib import Path as FilePath

    result = await db.execute(
        select(Design).where(Design.id == design_id)
    )
    design = result.scalar_one_or_none()
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    if not design.file_io_path:
        raise HTTPException(
            status_code=400,
            detail="Studio .io file not yet generated. Wait for generation to complete.",
        )

    io_full_path = FilePath(settings.storage_path) / design.file_io_path
    if not io_full_path.exists():
        raise HTTPException(status_code=404, detail=".io file not found on disk")

    # Launch Studio with the .io file (Windows desktop only)
    import platform
    import os as _os
    if platform.system() != "Windows":
        raise HTTPException(
            status_code=400,
            detail="Studio automation only available on Windows. Download the .io file and open manually in BrickLink Studio.",
        )
    if not _os.path.exists(r"D:\lego\Studio 2.0\Studio.exe"):
        raise HTTPException(
            status_code=400,
            detail="Studio 2.0 not found at D:\\lego\\Studio 2.0\\. Install Studio or download the .io file manually.",
        )
    try:
        from app.services.studio_automation import open_design_in_studio
        result = open_design_in_studio(str(io_full_path))
        return {
            "success": result["success"],
            "io_path": result["io_path"],
            "studio_opened": result["studio_opened"],
            "file_opened": result["file_opened"],
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Studio automation failed: {e}")


@router.post("/{design_id}/customize", response_model=CustomizationResponse, status_code=201)
async def customize_design(
    design_id: uuid.UUID,
    cust_req: CustomizationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Customize an existing LEGO car design.

    Takes a base design and user's modification instructions,
    creates a new customized design as a child of the original.

    In sync mode (GENERATION_MODE=sync or no Redis), customization runs
    inline and the returned design is already completed. Otherwise the
    customization runs asynchronously via Celery — poll
    GET /designs/{new_id}/status for completion.
    """
    # Load base design
    stmt = (
        select(Design)
        .where(Design.id == design_id)
        .options(selectinload(Design.car), selectinload(Design.parts))
    )
    result = await db.execute(stmt)
    base_design = result.scalar_one_or_none()

    if not base_design:
        raise HTTPException(status_code=404, detail="Base design not found")

    if base_design.status != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Base design must be completed before customization. Current status: {base_design.status}",
        )

    # Build car info string
    car = base_design.car
    car_info = f"{car.make} {car.model} ({car.year})" if car else "Unknown car"

    # Create new design as child
    new_design = Design(
        car_id=base_design.car_id,
        match_level=base_design.match_level,
        status="pending",
        parent_design_id=base_design.id,
        customization_request=cust_req.customization_text,
        metadata_={"type": "customization", "base_design_id": str(base_design.id)},
    )
    db.add(new_design)
    await db.flush()
    await db.refresh(new_design)

    # Dispatch Celery task (or run sync if no Redis / sync mode)
    generation_mode = os.getenv("GENERATION_MODE", "auto")
    redis_url = os.getenv("REDIS_URL", "")

    if redis_url and generation_mode != "sync":
        try:
            from tasks.customization import customize_design as customize_task
            task = customize_task.delay(
                new_design_id=str(new_design.id),
                base_design_id=str(base_design.id),
                car_info=car_info,
                customization_request=cust_req.customization_text,
            )
            new_design.ai_job_id = task.id
            await db.flush()
        except Exception:
            pass

    if not new_design.ai_job_id:
        await _run_sync_customization(
            db, new_design, base_design, car_info, cust_req.customization_text
        )

    status_msg = (
        "Customization completed."
        if new_design.status == "completed"
        else f"Customization started. Poll /designs/{new_design.id}/status for completion."
    )

    return CustomizationResponse(
        id=new_design.id,
        status=new_design.status,
        message=status_msg,
        parent_design_id=base_design.id,
    )
