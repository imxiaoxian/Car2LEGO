"""Real-API integration tests (Phase 6.2).

These tests call real DeepSeek and Doubao APIs and are marked `@pytest.mark.slow`.
They are skipped by default in CI (pytest.ini has `-m "not slow"`).

To run them locally:
    cd D:/lego/backend
    DEEPSEEK_API_KEY="sk-xxx" DOUBAO_API_KEY="ark-xxx" \
        python -m pytest tests/integration/test_design_real.py -v -m slow

Requirements:
    - DEEPSEEK_API_KEY env var (for text→design generation)
    - DOUBAO_API_KEY env var (for vision→car features analysis)
    - A valid car.jpg image in tests/fixtures/ (for from-image test)
"""

import os
import zipfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine

from app.database import Base
from app.main import app
from app.config import settings


pytestmark = pytest.mark.slow

REAL_DB_URL = "sqlite+aiosqlite:///test_integration_real.db"


@pytest.fixture(scope="module")
async def real_client():
    """Create a test client for real-API integration tests."""
    engine = create_async_engine(REAL_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture(autouse=True)
def force_sync_generation(monkeypatch):
    """Force sync generation mode — no Celery/Redis."""
    monkeypatch.setenv("GENERATION_MODE", "sync")
    monkeypatch.setenv("REDIS_URL", "")


def _has_deepseek_key() -> bool:
    return bool(os.getenv("DEEPSEEK_API_KEY") or os.getenv("DEEPSEEK_API_KEY"))


def _has_doubao_key() -> bool:
    return bool(os.getenv("DOUBAO_API_KEY"))


@pytest.mark.slow
class TestRealDesignGeneration:
    """Real DeepSeek API calls — verify .io file is a valid ZIP with real parts."""

    @pytest.mark.skipif(not _has_deepseek_key(), reason="DEEPSEEK_API_KEY not set")
    async def test_real_deepseek_design(self, real_client, tmp_path, monkeypatch):
        """POST /designs with a real DeepSeek API call produces a valid .io file."""
        monkeypatch.setattr(settings, "storage_path", str(tmp_path))

        response = await real_client.post(
            "/api/v1/designs",
            json={"make": "Toyota", "model": "Supra MK5", "year": 2024, "scale": "1:38"},
        )
        assert response.status_code == 201
        data = response.json()
        design_id = data["id"]

        # Verify the design completed
        detail = await real_client.get(f"/api/v1/designs/{design_id}")
        assert detail.status_code == 200
        detail_data = detail.json()
        assert detail_data["status"] == "completed", \
            f"Design should complete, got status={detail_data['status']}"
        assert detail_data["parts_count"] > 0, "Should have real parts"

        # Download and verify the .io file
        io_resp = await real_client.get(f"/api/v1/export/io/{design_id}")
        assert io_resp.status_code == 200
        import io as std_io
        with zipfile.ZipFile(std_io.BytesIO(io_resp.content), "r") as zf:
            names = zf.namelist()
            assert "model.ldr" in names, "ZIP must contain model.ldr"
            assert "model2.ldr" in names, "ZIP must contain model2.ldr"
            model_ldr = zf.read("model.ldr").decode("utf-8", errors="replace")
            # Real DeepSeek output should have part placement lines
            assert "1 " in model_ldr, "Should have at least one part line"

    @pytest.mark.skipif(not _has_deepseek_key(), reason="DEEPSEEK_API_KEY not set")
    async def test_real_deepseek_design_unknown_car(self, real_client, tmp_path, monkeypatch):
        """An unknown car triggers L4 and produces a valid design."""
        monkeypatch.setattr(settings, "storage_path", str(tmp_path))

        response = await real_client.post(
            "/api/v1/designs",
            json={"make": "Zenvo", "model": "TSR-S", "year": 2023, "scale": "1:38"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["match"]["level"] == 4  # L4 = AI generated

        design_id = data["id"]
        # Poll for completion
        import asyncio
        for _ in range(30):
            detail = await real_client.get(f"/api/v1/designs/{design_id}")
            status = detail.json().get("status")
            if status in ("completed", "failed"):
                break
            await asyncio.sleep(2)

        assert detail.json()["status"] == "completed", \
            f"Design should complete, got: {detail.json()}"


@pytest.mark.slow
class TestRealVisionAnalysis:
    """Real Doubao Vision API calls — verify car features extraction."""

    @pytest.mark.skipif(not _has_doubao_key(), reason="DOUBAO_API_KEY not set")
    async def test_real_doubao_vision(self, real_client, tmp_path, monkeypatch):
        """POST /designs/from-image with a real car photo produces a design."""
        monkeypatch.setattr(settings, "storage_path", str(tmp_path))

        # Look for a test image in fixtures
        fixture_path = Path(__file__).parent / "fixtures" / "car.jpg"
        if not fixture_path.exists():
            pytest.skip("No test image at tests/integration/fixtures/car.jpg")

        with open(fixture_path, "rb") as f:
            img_bytes = f.read()

        response = await real_client.post(
            "/api/v1/designs/from-image",
            files={"image": ("car.jpg", img_bytes, "image/jpeg")},
            data={"make": "", "model": "", "year": 2020},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # Vision should have detected some make/model
        assert data["car"]["make"]


@pytest.mark.slow
class TestRealCustomization:
    """Real DeepSeek API call for customization."""

    @pytest.mark.skipif(not _has_deepseek_key(), reason="DEEPSEEK_API_KEY not set")
    async def test_real_customization(self, real_client, tmp_path, monkeypatch):
        """POST /designs/{id}/customize with real DeepSeek produces a child design."""
        monkeypatch.setattr(settings, "storage_path", str(tmp_path))

        # First create a base design
        create_resp = await real_client.post(
            "/api/v1/designs",
            json={"make": "Ferrari", "model": "F40", "year": 1987, "scale": "1:38"},
        )
        assert create_resp.status_code == 201
        base_id = create_resp.json()["id"]

        # Wait for base design to complete
        import asyncio
        for _ in range(30):
            detail = await real_client.get(f"/api/v1/designs/{base_id}")
            if detail.json().get("status") in ("completed", "failed"):
                break
            await asyncio.sleep(2)

        assert detail.json()["status"] == "completed", "Base design must complete first"

        # Now customize
        custom_resp = await real_client.post(
            f"/api/v1/designs/{base_id}/customize",
            json={"customization_text": "Add a large rear wing and wider fenders"},
        )
        assert custom_resp.status_code in (200, 201)
        child = custom_resp.json()
        assert child["id"] != base_id
