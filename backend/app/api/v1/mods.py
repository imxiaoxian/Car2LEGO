"""Modification parts catalog API."""

from fastapi import APIRouter

from app.services.mod_parts_catalog import MOD_CATALOG

router = APIRouter()


@router.get("")
async def list_mods():
    """List all available modification parts organized by category."""
    result = {}
    for category, mods in MOD_CATALOG.items():
        result[category] = [
            {
                "id": m.id,
                "name": m.name,
                "category": m.category,
                "real_world_ref": m.real_world_ref,
                "description": m.description,
                "difficulty": m.difficulty,
                "estimated_parts": m.estimated_parts,
                "visual_change": m.visual_change,
                "lego_parts_count": len(m.lego_parts),
            }
            for m in mods
        ]
    return result


@router.get("/categories")
async def list_categories():
    """List all modification categories."""
    return [
        {
            "id": cat_id,
            "label": cat_id.replace("_", " ").title(),
            "count": len(mods),
        }
        for cat_id, mods in MOD_CATALOG.items()
    ]
