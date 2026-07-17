"""Body style templates API — pre-built Studio car chassis."""

from fastapi import APIRouter

from app.services.studio_templates import CAR_TEMPLATES

router = APIRouter()


@router.get("")
async def list_templates():
    """List all available car body style templates for Studio."""
    return [
        {
            "id": tid,
            "name": info["name"],
            "body_style": info["body_style"],
            "car_makes": info["car_makes"],
            "default_color": info["default_color"],
            "wheel_type": info["wheel_type"],
            "roof_style": info["roof_style"],
            "part_count": sum(1 for line in info["ldr"].split("\n") if line.strip().startswith("1 ") and len(line.split()) >= 15) if "ldr" in info else 0,
        }
        for tid, info in CAR_TEMPLATES.items()
    ]
