"""Real-API end-to-end test: DeepSeek → LangGraph → LDraw → .io → validation.

This test calls the REAL DeepSeek API to generate a LEGO car design, saves the
.io file, and validates it against Studio + LDraw standards.

Marked as `slow` — skipped by default. Run explicitly:

    cd D:/lego/backend
    $env:DEEPSEEK_API_KEY = "sk-..."
    python -m pytest tests/integration/test_real_generate.py -m slow -s

Or via the standalone script:

    $env:DEEPSEEK_API_KEY = "sk-..."
    $env:GENERATION_MODE = "sync"
    python tests/integration/test_real_generate.py
"""

import asyncio
import os
import uuid
import zipfile
from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.deps import get_db
from app.main import app
from app.services.io_validator import validate_io_file
from app.services.studio_design_generator import StudioDesignGenerator


pytestmark = pytest.mark.slow


def _check_api_key():
    """Skip if DEEPSEEK_API_KEY is not set."""
    from app.config import settings

    if not settings.deepseek_api_key:
        pytest.skip("DEEPSEEK_API_KEY not set — skipping real-API test")


@pytest.fixture
async def test_db():
    """Set up SQLite test DB and override get_db dependency."""
    db_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///test_real.db")
    engine = create_async_engine(db_url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def get_test_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = get_test_db
    yield
    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.mark.asyncio
async def test_real_generate_and_validate(test_db):
    """Generate a Ferrari F40 design via real DeepSeek API and validate the .io file."""
    _check_api_key()

    from app.config import settings

    storage_path = Path(settings.storage_path)
    storage_path.mkdir(parents=True, exist_ok=True)

    # Step 1: Generate design
    generator = StudioDesignGenerator()
    design_id = str(uuid.uuid4())

    result = await generator.generate(
        design_id=design_id,
        make="Ferrari",
        model="F40",
        year=1990,
        scale="1:38",
    )

    assert result["status"] == "completed", f"Generation failed: {result.get('error_message')}"
    assert result["parts_count"] > 0, "No parts generated"
    assert result["file_io_path"], "No .io file path returned"

    # Step 2: Locate .io file
    io_path = storage_path / result["file_io_path"]
    assert io_path.exists(), f".io file not found at {io_path}"
    assert io_path.stat().st_size > 0, ".io file is empty"

    # Step 3: Validate .io file
    report = validate_io_file(io_path)

    assert not report.has_errors, (
        f".io validation failed with {len(report.errors)} errors:\n"
        + "\n".join(f"  [{e.category}] {e.message}" for e in report.errors)
    )

    # Step 4: Verify .io ZIP structure
    with zipfile.ZipFile(io_path, "r") as zf:
        names = zf.namelist()
        assert "model.ldr" in names, "model.ldr missing from .io"
        assert ".info" in names, ".info missing from .io"

        ldr = zf.read("model.ldr").decode("utf-8", errors="replace")
        part_lines = [l for l in ldr.split("\n") if l.strip().startswith("1 ")]
        assert len(part_lines) >= 20, f"Only {len(part_lines)} parts in model.ldr"

    # Step 5: Verify car-specific geometry (slope parts, windshield, wheels, ratio)
    from app.services.io_validator import (
        SLOPE_PART_NUMBERS,
        TRANSPARENT_COLORS,
        WHEEL_PART_NUMBERS,
        _parse_ldr,
    )

    parsed = _parse_ldr(ldr)
    parts = parsed["parts"]

    # At least 10 slope/curved parts for streamlined body shape
    slope_parts = [p for p in parts if p["part_file"] in SLOPE_PART_NUMBERS]
    assert len(slope_parts) >= 10, (
        f"Only {len(slope_parts)} slope/curved parts — expected >= 10 for streamlined body"
    )

    # Windshield: at least one transparent part at roof level (Y >= 64)
    windshield = [
        p for p in parts
        if p["color"] in TRANSPARENT_COLORS and p["y"] >= 64
    ]
    assert len(windshield) >= 1, "No transparent windshield parts at roof level"

    # At least 4 wheels
    wheels = [p for p in parts if p["part_file"] in WHEEL_PART_NUMBERS]
    assert len(wheels) >= 4, f"Only {len(wheels)} wheel parts — expected >= 4"

    # Body length/width ratio 1.5-3.0
    x_coords = [p["x"] for p in parts]
    z_coords = [p["z"] for p in parts]
    x_range = max(x_coords) - min(x_coords)
    z_range = max(z_coords) - min(z_coords)
    if x_range > 0:
        ratio = z_range / x_range
        assert 1.5 <= ratio <= 3.0, (
            f"Body length/width ratio = {ratio:.2f} — expected 1.5-3.0"
        )
