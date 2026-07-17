"""Community Mod System API — Steam Workshop style for LEGO car mods."""

import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form

from app.config import settings
from app.services.community_mods import ModRepository

router = APIRouter()

# Singleton mod repository
_mod_repo: ModRepository | None = None


def get_mod_repo() -> ModRepository:
    global _mod_repo
    if _mod_repo is None:
        _mod_repo = ModRepository(str(Path(settings.storage_path) / "community_mods"))
    return _mod_repo


@router.get("")
async def list_mods(
    category: str | None = Query(default=None),
    body_style: str | None = Query(default=None),
    make: str | None = Query(default=None),
    difficulty: str | None = Query(default=None),
    search: str | None = Query(default=None),
    sort_by: str = Query(default="rating"),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
):
    """Browse and search community mods."""
    repo = get_mod_repo()
    mods = repo.list_mods(
        category=category, body_style=body_style, make=make,
        difficulty=difficulty, search=search,
        sort_by=sort_by, limit=limit, offset=offset,
    )
    return {
        "total": len(repo._index),
        "results": [repo.to_api_dict(m) for m in mods],
    }


@router.get("/categories")
async def list_categories():
    """Get all mod categories with counts."""
    return get_mod_repo().get_categories()


@router.get("/spec")
async def get_mod_spec():
    """Get the mod submission specification (MOD_SPEC v1.0)."""
    from app.services.community_mods import MOD_SPEC_SCHEMA
    return MOD_SPEC_SCHEMA


@router.get("/{mod_id}")
async def get_mod(mod_id: str):
    """Get details of a specific mod."""
    repo = get_mod_repo()
    mod = repo.get_mod(mod_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Mod not found")
    return repo.to_api_dict(mod)


@router.get("/{mod_id}/ldr")
async def get_mod_ldr(mod_id: str):
    """Download a mod's LDraw content."""
    repo = get_mod_repo()
    mod = repo.get_mod(mod_id)
    if not mod:
        raise HTTPException(status_code=404, detail="Mod not found")
    ldr = mod.get_ldraw_content()
    if not ldr:
        raise HTTPException(status_code=404, detail="Mod has no LDraw data")
    from fastapi.responses import PlainTextResponse
    return PlainTextResponse(ldr, media_type="text/plain")


@router.post("/submit")
async def submit_mod(
    mod_id: str = Form(..., description="Unique mod ID (lowercase_underscores)"),
    name: str = Form(...),
    version: str = Form(default="1.0.0"),
    author: str = Form(...),
    category: str = Form(...),
    description: str = Form(...),
    difficulty: str = Form(default="medium"),
    estimated_parts: int = Form(default=10),
    compatible_body_styles: str = Form(default="all"),
    tags: str = Form(default=""),
    license: str = Form(default="CC-BY-4.0"),
    ldraw_file: UploadFile = File(...),
    preview_image: UploadFile = File(...),
):
    """Submit a new community mod.

    Multipart form upload with mod.json metadata + LDraw file + preview image.
    """
    import json, shutil, tempfile

    # Create temp directory for mod
    tmp_dir = Path(tempfile.mkdtemp(prefix="mod_"))
    try:
        # Save uploaded files
        ldraw_path = tmp_dir / "model.ldr"
        with open(ldraw_path, "wb") as f:
            f.write(await ldraw_file.read())

        preview_path = tmp_dir / "preview.png"
        with open(preview_path, "wb") as f:
            f.write(await preview_image.read())

        # Build manifest
        manifest = {
            "mod_id": mod_id.lower().replace(" ", "_"),
            "name": name,
            "version": version,
            "author": author,
            "category": category,
            "description": description,
            "difficulty": difficulty,
            "estimated_parts": estimated_parts,
            "compatible_body_styles": compatible_body_styles.split(","),
            "tags": [t.strip() for t in tags.split(",") if t.strip()],
            "license": license,
            "ldraw_file": "model.ldr",
            "preview_image": "preview.png",
        }
        with open(tmp_dir / "mod.json", "w", encoding="utf-8") as f:
            json.dump(manifest, f, indent=2)

        # Install into repository
        repo = get_mod_repo()
        success, message = repo.install_mod(tmp_dir)

        if not success:
            raise HTTPException(status_code=400, detail=message)

        return {"success": True, "mod_id": mod_id, "message": message}

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
