"""Design endpoints — the core API for creating and retrieving LEGO designs."""

import os
import uuid
import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
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
from app.agents.security import mask_api_key
from app.services.reference_images import ALL_REFERENCE_VIEWS
from app.services.design_parts import replace_design_parts

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

    reference_images = []
    meta = design.metadata_ or {}
    design_directory = Path(settings.storage_path) / str(design.id)
    report_path = design_directory / "quality_report.json"
    quality = json.loads(report_path.read_text(encoding="utf-8")) if report_path.is_file() else meta.get("quality_report")
    physical_path = design_directory / "physical_specifications.json"
    physical = (quality or {}).get("physical_specifications")
    if not physical and physical_path.is_file():
        physical = json.loads(physical_path.read_text(encoding="utf-8"))
    if physical:
        physical = physical | {"applied_to_design": True}
    elif design.car:
        from app.services.vehicle_physics import load_profile
        physical = load_profile(design.car.make, design.car.model, design.car.year).resolved(design.scale or "1:38") | {"applied_to_design": False}
    external_path = design_directory / "external" / "report.json"
    external_report = json.loads(external_path.read_text(encoding="utf-8")) if external_path.is_file() else {}
    external_checks = (quality or {}).get("external_checks") or external_report.get("checks", {})
    external_renders = _external_render_records(design.id, design_directory, external_checks)
    from app.services.assembly_v3.jobs import JobStore
    from app.services.assembly_v3.official_guides import guide_records
    job = JobStore().get(str(design.id))
    from app.services.assembly_v3.requirements import SCALES, requirements_for_scale
    requirements = (quality or {}).get("scale_requirements") or (job or {}).get("data", {}).get("checkpoint", {}).get("scale_requirements")
    requirements_applied = bool(requirements)
    if quality and "scale_requirements" in quality:
        requirements_applied = quality.get("requirements_applied", False)
    if requirements is None and (design.scale or "1:38") in SCALES:
        requirements = requirements_for_scale(design.scale or "1:38")
    public_job = {k: job[k] for k in ("state", "stage", "progress", "updated")} | {
        k: job["data"][k] for k in ("calls", "limits", "module_repairs", "replans")} if job else None
    if public_job is not None:
        public_job["failure"] = job["data"].get("failure")
        public_job["resume_stage"] = (job["data"].get("failure") or {}).get("stage") or (
            "reference_consistency" if job["data"]["checkpoint"].get("references") and not job["data"]["checkpoint"].get("intent") else None)
    manifest = Path(settings.storage_path) / str(design.id) / "references" / "manifest.json"
    if manifest.is_file():
        for image in json.loads(manifest.read_text(encoding="utf-8")).get("images", []):
            reference_images.append({
                "view": image["view"], "model": image["model"], "synthetic": True,
                "category": image.get("category", "detail" if image["view"] not in ("overview", "chassis", "front", "body", "rear", "wheels") else "exterior"),
                "purpose": image.get("purpose", ""), "shot_request": image.get("shot_request"),
                "url": f"/api/v1/designs/{design.id}/reference-images/{image['view']}?v={image.get('sha256', '')}",
            })
    return DesignDetailResponse(
        id=design.id,
        car_id=design.car_id,
        match=_build_match_info(match_result) if match_result else None,
        status=job["state"] if job else design.status,
        parts_count=design.parts_count,
        difficulty=design.difficulty,
        created_at=design.created_at,
        completed_at=design.completed_at,
        error_message=job["data"].get("error") or None if job else design.error_message,
        car=await _car_to_response(design.car) if design.car else None,
        parts=parts_list,
        parent_design_id=design.parent_design_id,
        customization_request=design.customization_request,
        reference_images=reference_images,
        official_build_references=guide_records(settings.storage_path, dict(make=design.car.make if design.car else "",
            model=design.car.model if design.car else "",scale=design.scale)),
        assembly_preview_url=f"/api/v1/designs/{design.id}/assembly-preview" if
            (Path(settings.storage_path) / str(design.id) / "assembly_preview.png").is_file() else None,
        assembly_preview_rear_url=f"/api/v1/designs/{design.id}/assembly-preview?view=rear" if
            (Path(settings.storage_path) / str(design.id) / "assembly_preview_rear.png").is_file() else None,
        quality_level=(design.metadata_ or {}).get("quality_level"),
        workflow_version=meta.get("workflow_version"),
        requested_scale=design.scale if design.scale and design.scale.startswith("1:") else "1:38",
        actual_dimensions_mm=(quality or {}).get("actual_mm", {}),
        scale_deviation_percent=(quality or {}).get("scale_deviation_percent", {}),
        scale_requirements=(requirements | {"applied_to_design": requirements_applied}) if requirements else {},
        physical_specifications=physical or {},
        mechanisms=(quality or {}).get("mechanisms", []), quality_report=quality, job=public_job,
        external_checks=external_checks, external_renders=external_renders,
        scene_url=f"/api/v1/designs/{design.id}/scene" if all((Path(settings.storage_path) / str(design.id) / n).is_file() for n in ("scene.json","geometry.json")) else None,
        renders=[dict(view=v, url=f"/api/v1/designs/{design.id}/renders/{v}") for v in ("front", "rear", "left", "right", "top", "bottom")
                 if (Path(settings.storage_path) / str(design.id) / f"render_{v}.png").is_file()],
        file_urls={
            "io": f"/api/v1/export/io/{design.id}" if design.file_io_path else "",
            "ldr": f"/api/v1/export/ldr/{design.id}" if design.file_ldr_path else "",
            "pdf": f"/api/v1/export/pdf/{design.id}" if design.file_pdf_path else "",
            "xml": f"/api/v1/export/xml/{design.id}",
            "csv": f"/api/v1/export/csv/{design.id}",
            "mpd": f"/api/v1/export/mpd/{design.id}" if (Path(settings.storage_path) / str(design.id) / "model.mpd").is_file() else "",
            "quality": f"/api/v1/designs/{design.id}/quality" if quality else "",
        },
    )


def _external_render_records(design_id: uuid.UUID, directory: Path, checks: dict) -> list[dict]:
    ldraw = checks.get("ldraw_mcp", {})
    nested_report_path = directory / "external" / "ldraw_mcp" / "report.json"
    nested_report = json.loads(nested_report_path.read_text(encoding="utf-8")) if nested_report_path.is_file() else {}
    renderer = nested_report or ldraw
    artifacts_root = (directory / "external" / "ldraw_mcp").resolve()
    records = []
    module_labels = {
        "engine": "发动机",
        "cockpit": "座舱与内饰",
        "seats": "座椅",
        "doors": "车门",
        "front_hood": "前盖",
        "engine_cover": "发动机盖",
        "details": "外观与机构",
    }

    def add(artifact: str, view: str, label: str, category: str, module: str | None = None):
        if not isinstance(artifact, str) or Path(artifact).name != artifact or not artifact.lower().endswith(".png"):
            return
        path = (artifacts_root / artifact).resolve()
        if not path.is_relative_to(artifacts_root) or not path.is_file():
            return
        records.append({"view": view, "label": label, "category": category, "module": module,
                        "synthetic": False, "url": f"/api/v1/designs/{design_id}/external-renders/{artifact}"})

    for item in renderer.get("render_views", []):
        if not isinstance(item, dict):
            continue
        azimuth = item.get("azimuth")
        add(item.get("artifact"), f"external_exterior_{item.get('view', azimuth)}",
            f"整车外观 · 方位 {azimuth}°", "exterior")
    if not any(record["category"] == "exterior" for record in records):
        for index, artifact in enumerate(renderer.get("renders", [])):
            add(artifact, f"external_exterior_{index}", "整车外观 · 多视角", "exterior")

    for detail in renderer.get("detail_renders", []):
        if not isinstance(detail, dict):
            continue
        module = str(detail.get("module", "detail"))
        module_label = module_labels.get(module, module)
        views = detail.get("views") or [{"artifact": artifact, "azimuth": None}
                                         for artifact in detail.get("artifacts", [])]
        for index, item in enumerate(views):
            if not isinstance(item, dict):
                continue
            azimuth = item.get("azimuth")
            angle_label = f" · 方位 {azimuth}°" if azimuth is not None else ""
            add(item.get("artifact"), f"external_{module}_{index}", f"{module_label}细节{angle_label}", "detail", module)
    return records


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
            vehicle_features=(design.metadata_ or {}).get("vision_features", {}),
            source_image_path=(design.metadata_ or {}).get("source_image_path", ""),
            custom_request=design.customization_request or "",
        )

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
            design.metadata_ = (design.metadata_ or {}) | (result.get("metadata", {}) or {})

            await replace_design_parts(db, design.id, result.get("parts_data", []))
        else:
            design.status = "failed"
            design.error_message = result.get("error_message", "Generation failed")
    except Exception as exc:
        design.status = "failed"
        design.error_message = mask_api_key(str(exc))[:1000]

    await db.flush()


async def _run_background_generation(design_id: uuid.UUID) -> None:
    from app.database import async_session

    async with async_session() as db:
        result = await db.execute(select(Design).where(Design.id == design_id).options(selectinload(Design.car)))
        design = result.scalar_one()
        design.status = "processing"
        await db.commit()
        await _run_sync_generation(db, design, design.car)
        await db.commit()


async def _dispatch_generation(
    db: AsyncSession, design: Design, car: Car, background_tasks: BackgroundTasks | None = None,
) -> None:
    """Make the row visible before the worker can load it."""
    if settings.design_workflow == "assembly_v3":
        from app.services.assembly_v3.jobs import JobStore
        JobStore().ensure(str(design.id), dict(design_id=str(design.id), make=car.make, model=car.model,
            year=car.year, scale=design.scale, custom_request=design.customization_request or "",
            vehicle_features=(design.metadata_ or {}).get("vision_features", {}),
            source_image_path=(design.metadata_ or {}).get("source_image_path", "")))
        design.metadata_ = {**(design.metadata_ or {}), "workflow_version": "assembly_v3"}
    if os.getenv("REDIS_URL", "") and os.getenv("GENERATION_MODE", "auto") != "sync":
        await db.commit()
        try:
            from tasks.generation import generate_lego_design

            task = generate_lego_design.delay(
                design_id=str(design.id), make=car.make, model=car.model, year=car.year,
                scale=design.scale,
                flagship_metadata=(design.metadata_ or {}).get("flagship"),
                vehicle_features=(design.metadata_ or {}).get("vision_features", {}),
                source_image_path=(design.metadata_ or {}).get("source_image_path", ""),
                custom_request=design.customization_request or "",
            )
            design.ai_job_id = task.id
            await db.flush()
            return
        except Exception:
            pass
    if os.getenv("GENERATION_MODE", "auto") != "sync" and background_tasks is not None:
        await db.commit()
        background_tasks.add_task(_run_background_generation, design.id)
    else:
        await _run_sync_generation(db, design, car)


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
            new_design.completed_at = datetime.now(timezone.utc)
            new_design.parts_count = result.get("parts_count", 0)
            new_design.difficulty = result.get("difficulty", "Medium")
            new_design.file_io_path = result.get("file_io_path")
            new_design.file_ldr_path = result.get("file_ldr_path")
            new_design.metadata_ = (new_design.metadata_ or {}) | (result.get("metadata", {}) or {})

            await replace_design_parts(db, new_design.id, result.get("parts_data", []))
        else:
            new_design.status = "failed"
            new_design.error_message = result.get("error_message", "Customization failed")
    except Exception as exc:
        new_design.status = "failed"
        new_design.error_message = str(exc)

    await db.flush()


def _preprocess_uploaded_image(data: bytes, suffix: str) -> bytes:
    """Validate and normalize an uploaded car photo for the vision model.

    - Resizes to max 2048px on the longest side
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
        if img.mode != "RGB":
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
    except Exception as exc:
        raise HTTPException(status_code=422, detail="Upload a valid JPEG, PNG or WebP image") from exc


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
async def list_scales(make: str = "Ferrari", model: str = "F40"):
    """List supported scale ratios and capabilities."""
    from app.services.assembly_v3.specifications import scale_capabilities
    return {
        "scales": scale_capabilities(make,model),
        "default": "1:38",
    }


@router.post("", response_model=DesignDetailResponse, status_code=201)
async def create_design(
    design_in: DesignCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """Submit a car and get back a LEGO design.

    This is the main entry point. The matching engine will try L1→L4
    and return the best available design.
    """
    if design_in.scale in ("1:8", "1:10"):
        raise HTTPException(status_code=422, detail="This scale has not passed structure validation; choose 1:38, 1:24, 1:16 or 1:12")
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

        research_data = {"visual_reference_source": "generated_images"}

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
        status="pending",
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

    # 1:38 always produces an assembled image-guided model, even for official matches.
    if settings.design_workflow == "assembly_v3" or design_in.scale == "1:38":
        await _dispatch_generation(db, design, car, background_tasks)
    elif match_result.level == 1 and match_result.set_num:
        await _import_set_parts(db, design, match_result.set_num)
        await _build_io_from_parts(db, design)
        design.status = "draft" if design.file_io_path else "failed"
        design.metadata_ = {**(design.metadata_ or {}), "quality_level": "inventory_only"}
        if design.status == "failed":
            design.error_message = "Official set parts unavailable; configure REBRICKABLE_API_KEY"
    else:
        design.status = "failed"
        design.error_message = "Image-guided generation supports 1:38; other scales require an official set"
    await db.flush()

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
        select(Design).where(Design.id == design_id).options(selectinload(Design.car))
    )
    design = result.scalar_one_or_none()

    if not design:
        raise HTTPException(status_code=404, detail="Design not found")

    from app.services.assembly_v3.jobs import JobStore
    job = JobStore().get(str(design_id))
    if job:
        return DesignStatusResponse(id=design.id, status=job["state"], stage=job["stage"], progress=job["progress"],
            error_message=job["data"].get("error") or design.error_message, calls=job["data"]["calls"],
            limits=job["data"]["limits"], module_repairs=job["data"]["module_repairs"])

    progress = {}
    progress_path = Path(settings.storage_path) / str(design.id) / "generation_status.json"
    if progress_path.is_file():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
    return DesignStatusResponse(
        id=design.id,
        status=design.status,
        progress=100 if design.status == "completed" else progress.get("progress", 0),
        stage=progress.get("stage", design.status),
        error_message=design.error_message,
    )


@router.get("/{design_id}/reference-images/{view}")
async def get_reference_image(design_id: uuid.UUID, view: str):
    from fastapi.responses import FileResponse

    if view not in ALL_REFERENCE_VIEWS:
        raise HTTPException(status_code=404, detail="Unknown reference view")
    path = Path(settings.storage_path) / str(design_id) / "references" / f"{view}.png"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Reference image not generated")
    return FileResponse(path, media_type="image/png")


@router.get("/{design_id}/scene")
@router.get("/{design_id}/quality")
@router.get("/{design_id}/geometry")
async def get_assembly_artifact(design_id: uuid.UUID, request: Request):
    from fastapi.responses import FileResponse
    name = {"scene": "scene.json", "quality": "quality_report.json", "geometry": "geometry.json"}[request.url.path.rsplit("/", 1)[-1]]
    path = Path(settings.storage_path) / str(design_id) / name
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Assembly artifact not yet available")
    return FileResponse(path, media_type="application/json", headers={"Cache-Control": "no-cache"})


@router.get("/{design_id}/renders/{view}")
async def get_scene_render(design_id: uuid.UUID, view: str):
    from fastapi.responses import FileResponse
    if view not in ("front", "rear", "left", "right", "top", "bottom"):
        raise HTTPException(status_code=404, detail="Unknown render view")
    path = Path(settings.storage_path) / str(design_id) / f"render_{view}.png"
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Render not yet available")
    return FileResponse(path, media_type="image/png")


@router.get("/{design_id}/external-renders/{artifact}")
async def get_external_render(design_id: uuid.UUID, artifact: str):
    from fastapi.responses import FileResponse

    directory = Path(settings.storage_path) / str(design_id)
    root = (directory / "external" / "ldraw_mcp").resolve()
    if Path(artifact).name != artifact or not artifact.lower().endswith(".png"):
        raise HTTPException(status_code=404, detail="Unknown external render")
    path = (root / artifact).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise HTTPException(status_code=404, detail="External render not found")
    report_path = root / "report.json"
    if not report_path.is_file():
        raise HTTPException(status_code=404, detail="External render is not registered")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    known = set(report.get("renders", []))
    for detail in report.get("detail_renders", []):
        known.update(detail.get("artifacts", []))
    if artifact not in known:
        raise HTTPException(status_code=404, detail="External render is not registered")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "public, max-age=3600"})


@router.post("/{design_id}/control/{action}")
async def control_generation(design_id: uuid.UUID, action: str, background_tasks: BackgroundTasks,
                             module: str | None = None, db: AsyncSession = Depends(get_db)):
    from app.services.assembly_v3.jobs import JobStore
    from app.services.assembly_v3.scene import AssemblyScene
    design = await db.get(Design, design_id)
    if not design:
        raise HTTPException(status_code=404, detail="Design not found")
    if action not in ("pause", "resume", "cancel", "retry"):
        raise HTTPException(status_code=422, detail="Unknown task control")
    if action == "retry":
        scene_path = Path(settings.storage_path) / str(design_id) / "scene.json"
        if not scene_path.is_file() or module not in {m.id for m in AssemblyScene.model_validate_json(scene_path.read_text(encoding="utf-8")).modules}:
            raise HTTPException(status_code=422, detail="Choose a module from the saved scene")
    try:
        job = JobStore().control(str(design_id), action, module)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    design.status = job["state"]
    await db.commit()
    if action in ("resume", "retry"):
        background_tasks.add_task(_run_background_generation, design_id)
    return {"id": str(design_id), "status": job["state"], "stage": job["stage"], "progress": job["progress"]}


@router.get("/{design_id}/assembly-preview")
async def get_assembly_preview(design_id: uuid.UUID, view: str = Query(default="front", pattern="^(front|rear)$")):
    from fastapi.responses import FileResponse
    path = Path(settings.storage_path) / str(design_id) / ("assembly_preview_rear.png" if view == "rear" else "assembly_preview.png")
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Assembly preview not generated")
    return FileResponse(path, media_type="image/png", headers={"Cache-Control": "no-cache"})


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
        select(Design).where(Design.id == design_id).options(selectinload(Design.car))
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
    background_tasks: BackgroundTasks,
    make: str = FastForm(default=""),
    model: str = FastForm(default=""),
    year: int | None = FastForm(default=None),
    scale: str = FastForm(default="1:38"),
    image: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Recognize a car, preserve its photo, and generate image-guided Studio output."""
    try:
        DesignCreate(make=make or "unknown", model=model or "unknown", year=year or 2000, scale=scale)
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc
    if scale in ("1:8", "1:10"):
        raise HTTPException(status_code=422, detail="Scale not yet validated for generation")
    import tempfile
    import os
    tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
    tmp_path = tmp_file.name
    tmp_file.close()
    try:
        raw_data = await image.read(20 * 1024 * 1024 + 1)
        # Preprocess image before sending to Vision API
        if len(raw_data) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Image exceeds 20 MB")
        processed_data = _preprocess_uploaded_image(raw_data, ".jpg")
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
        if not features or not make or not model or not year:
            raise HTTPException(status_code=422, detail="Unable to identify vehicle; provide make, model and year with a clear car photo")
        # Apply the same request validation as the text path.
        try:
            DesignCreate(make=make, model=model, year=year, scale=scale)
        except ValidationError as exc:
            raise RequestValidationError(exc.errors()) from exc
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
        design = Design(car_id=car.id, match_level=match_result.level, status="pending",
                        matched_set_num=match_result.set_num, scale=scale, metadata_=match_result.metadata)
        if features:
            from dataclasses import asdict
            design.metadata_ = {**(design.metadata_ or {}), "vision_features": asdict(features)}
        db.add(design)
        await db.flush()
        await db.refresh(design)
        source_dir = Path(settings.storage_path) / str(design.id)
        source_dir.mkdir(parents=True, exist_ok=True)
        source_path = source_dir / "source.jpg"
        source_path.write_bytes(processed_data)
        design.metadata_ = {**(design.metadata_ or {}), "source_image_path": str(source_path.resolve())}
        if settings.design_workflow == "assembly_v3" or scale == "1:38":
            await _dispatch_generation(db, design, car, background_tasks)
        elif match_result.level == 1 and match_result.set_num:
            await _import_set_parts(db, design, match_result.set_num)
            await _build_io_from_parts(db, design)
            design.status = "draft" if design.file_io_path else "failed"
            design.metadata_ = {**(design.metadata_ or {}), "quality_level": "inventory_only"}
            if design.status == "failed":
                design.error_message = "Official set parts unavailable; configure REBRICKABLE_API_KEY"
        else:
            design.status = "failed"
            design.error_message = "Image-guided generation supports 1:38; other scales require an official set"
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
    background_tasks: BackgroundTasks,
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

    if base_design.status not in ("completed", "draft"):
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
        scale=cust_req.scale or base_design.scale or "1:38",
        metadata_={"type": "customization", "base_design_id": str(base_design.id),
                   "source_image_path": (base_design.metadata_ or {}).get("source_image_path", ""),
                   "vision_features": (base_design.metadata_ or {}).get("vision_features", {})},
    )
    db.add(new_design)
    await db.flush()
    await db.refresh(new_design)

    if settings.design_workflow == "assembly_v3":
        await _dispatch_generation(db, new_design, car, background_tasks)
        return CustomizationResponse(id=new_design.id, status=new_design.status,
            message="New independent assembly created; acceptance is required", parent_design_id=base_design.id)

    # Dispatch Celery task (or run sync if no Redis / sync mode)
    generation_mode = os.getenv("GENERATION_MODE", "auto")
    redis_url = os.getenv("REDIS_URL", "")

    if redis_url and generation_mode != "sync":
        await db.commit()
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
