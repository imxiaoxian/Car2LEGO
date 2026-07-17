"""API-level integration tests with mocked LLM (Phase 6).

These tests monkeypatch the LLM factory functions so the full HTTP request
pipeline runs without any real API calls. They verify:
- POST /designs (text input) triggers L4 generation and produces a .io file
- POST /designs/{id}/customize produces a child design
- POST /designs/from-image mocks vision + text LLM

The real-API versions (skipped in CI) live in test_design_real.py.
"""

import zipfile
from pathlib import Path
from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base
from app.deps import get_db
from app.main import app
from app.config import settings
from tests.conftest import MockChatModel


# Use a separate in-memory DB for integration tests
INTEGRATION_DB_URL = "sqlite+aiosqlite:///test_integration_e2e.db"


@pytest.fixture
async def e2e_client():
    """Create an async test client wired to the FastAPI app with a fresh SQLite DB.

    Overrides the `get_db` dependency so requests use a SQLite engine instead
    of the app's default PostgreSQL engine (which isn't running in CI/dev).
    """
    engine = create_async_engine(INTEGRATION_DB_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    test_session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def get_test_db():
        async with test_session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = get_test_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

    app.dependency_overrides.clear()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest.fixture
def tmp_storage(tmp_path, monkeypatch):
    """Redirect settings.storage_path to a temp dir."""
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    return tmp_path


@pytest.fixture(autouse=True)
def force_sync_generation(monkeypatch):
    """Force GENERATION_MODE=sync so no Celery/Redis is needed."""
    monkeypatch.setenv("GENERATION_MODE", "sync")
    monkeypatch.setenv("REDIS_URL", "")


class TestCreateDesignL4Mocked:
    """POST /designs with an unknown car → L4 AI generation (mocked)."""

    async def test_unknown_car_triggers_l4_generation(
        self, e2e_client, tmp_storage, mock_design_customization
    ):
        """An unknown car falls through to L4 and the mocked LLM produces a design."""
        # Patch create_text_llm at the design_graph module level
        mock_llm = MockChatModel(structured_output=mock_design_customization)
        with patch("app.agents.design_graph.create_text_llm", return_value=mock_llm):
            response = await e2e_client.post(
                "/api/v1/designs",
                json={"make": "Zenvo", "model": "TSR-S", "year": 2023, "scale": "1:38"},
            )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # L4 = AI generated
        assert data["match"]["level"] == 4

    async def test_completed_design_has_io_file(
        self, e2e_client, tmp_storage, mock_design_customization
    ):
        """After sync generation, the .io file is downloadable."""
        mock_llm = MockChatModel(structured_output=mock_design_customization)
        with patch("app.agents.design_graph.create_text_llm", return_value=mock_llm):
            create_resp = await e2e_client.post(
                "/api/v1/designs",
                json={"make": "Koenigsegg", "model": "Jesko", "year": 2024, "scale": "1:38"},
            )
        design_id = create_resp.json()["id"]

        # Download the .io file
        io_resp = await e2e_client.get(f"/api/v1/export/io/{design_id}")
        assert io_resp.status_code == 200
        assert io_resp.headers.get("content-type", "").startswith("application/") or \
               io_resp.headers.get("content-type", "").startswith("application/octet-stream")

        # Verify it's a valid ZIP
        import io as std_io
        with zipfile.ZipFile(std_io.BytesIO(io_resp.content), "r") as zf:
            names = zf.namelist()
            assert "model.ldr" in names
            assert "model2.ldr" in names

    async def test_design_has_ldr_content(
        self, e2e_client, tmp_storage, mock_design_customization
    ):
        """The LDraw endpoint returns LDraw content with part lines."""
        mock_llm = MockChatModel(structured_output=mock_design_customization)
        with patch("app.agents.design_graph.create_text_llm", return_value=mock_llm):
            create_resp = await e2e_client.post(
                "/api/v1/designs",
                json={"make": "Pagani", "model": "Huayra", "year": 2022, "scale": "1:38"},
            )
        design_id = create_resp.json()["id"]

        ldr_resp = await e2e_client.get(f"/api/v1/export/ldr/{design_id}")
        assert ldr_resp.status_code == 200
        content = ldr_resp.text
        assert "0 STEP" in content
        assert "3020.dat" in content

    async def test_design_has_parts(
        self, e2e_client, tmp_storage, mock_design_customization
    ):
        """The design detail includes parts after generation."""
        mock_llm = MockChatModel(structured_output=mock_design_customization)
        with patch("app.agents.design_graph.create_text_llm", return_value=mock_llm):
            create_resp = await e2e_client.post(
                "/api/v1/designs",
                json={"make": "Rimac", "model": "Nevera", "year": 2023, "scale": "1:38"},
            )
        design_id = create_resp.json()["id"]

        detail_resp = await e2e_client.get(f"/api/v1/designs/{design_id}")
        assert detail_resp.status_code == 200
        detail = detail_resp.json()
        assert detail["status"] == "completed"
        assert detail["parts_count"] > 0
        assert len(detail["parts"]) > 0


class TestCustomizationE2EMocked:
    """POST /designs/{id}/customize with mocked LLM."""

    async def test_customize_produces_child_design(
        self, e2e_client, tmp_storage, mock_design_customization, mock_customized_design
    ):
        """Customizing an existing design produces a child design with modifications."""
        # First create a base design
        text_llm = MockChatModel(structured_output=mock_design_customization)
        with patch("app.agents.design_graph.create_text_llm", return_value=text_llm):
            create_resp = await e2e_client.post(
                "/api/v1/designs",
                json={"make": "Aston Martin", "model": "Vantage", "year": 2023, "scale": "1:38"},
            )
        base_id = create_resp.json()["id"]

        # Now customize it
        custom_llm = MockChatModel(structured_output=mock_customized_design)
        with patch("app.agents.customization_graph.create_text_llm", return_value=custom_llm):
            custom_resp = await e2e_client.post(
                f"/api/v1/designs/{base_id}/customize",
                json={"customization_text": "Add a large rear wing and wider fenders"},
            )

        assert custom_resp.status_code in (200, 201)
        child = custom_resp.json()
        assert "id" in child
        assert child["id"] != base_id  # It's a new child design
        assert child.get("parent_design_id") == base_id
        assert child["status"] == "completed"


class TestFromImageMocked:
    """POST /designs/from-image with mocked vision + text LLM."""

    async def test_from_image_creates_design(
        self, e2e_client, tmp_storage, mock_design_customization, mock_car_features_output
    ):
        """Uploading a car photo with mocked vision + text LLM creates a design."""
        from app.agents.vision_graph import CarFeaturesOutput

        vision_output = CarFeaturesOutput(**mock_car_features_output)
        vision_llm = MockChatModel(structured_output=vision_output)
        text_llm = MockChatModel(structured_output=mock_design_customization)

        # Create a minimal JPEG image
        import io as std_io
        img_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"

        with patch("app.agents.vision_graph.create_vision_llm", return_value=vision_llm), \
             patch("app.agents.design_graph.create_text_llm", return_value=text_llm):
            response = await e2e_client.post(
                "/api/v1/designs/from-image",
                files={"image": ("car.jpg", img_bytes, "image/jpeg")},
                data={"make": "", "model": "", "year": 2020},
            )

        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        # The mocked vision returns Ferrari F40, so make should be Ferrari
        assert data["car"]["make"] == "Ferrari"
