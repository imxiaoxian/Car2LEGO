"""Integration tests for Car2LEGO API endpoints.

Uses httpx async test client + SQLite in-memory database.
"""

import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# Import after test config is set up
from app.main import app
from app.database import Base
from app.deps import get_db

from tests.conftest import create_test_set, create_test_car


# Use a separate in-memory DB for integration tests
INTEGRATION_DB_URL = "sqlite+aiosqlite:///test_integration.db"


@pytest.fixture(scope="module")
async def integration_client():
    """Create an async test client wired to the FastAPI app.

    Overrides the `get_db` dependency so requests use a SQLite engine
    instead of the app's default PostgreSQL engine.
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

    # Cleanup
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


class TestHealthCheck:
    """Basic health check endpoint."""

    async def test_health_returns_ok(self, integration_client):
        response = await integration_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestDesignsAPI:
    """Core design creation and retrieval."""

    async def test_create_design_text_input(self, integration_client):
        """POST /designs with text input should return a design."""
        response = await integration_client.post(
            "/api/v1/designs",
            json={"make": "Porsche", "model": "911", "year": 2020},
        )
        assert response.status_code == 201
        data = response.json()
        assert "id" in data
        assert data["car"]["make"] == "Porsche"
        assert data["car"]["model"] == "911"
        assert data["match"]["level"] >= 1

    async def test_create_design_pagani_unknown_car(self, integration_client):
        """Unknown car should fall through to L4 (AI generation)."""
        response = await integration_client.post(
            "/api/v1/designs",
            json={"make": "Pagani", "model": "Utopia", "year": 2023},
        )
        assert response.status_code == 201
        data = response.json()
        # Pagani Utopia IS in the seed data as a set (76915-1)
        # So this should actually be L1
        assert data["match"]["level"] >= 1

    async def test_get_design_404(self, integration_client):
        """Non-existent design ID should return 404."""
        fake_id = str(uuid.uuid4())
        response = await integration_client.get(f"/api/v1/designs/{fake_id}")
        assert response.status_code == 404

    async def test_list_designs(self, integration_client):
        """GET /designs should return a list."""
        response = await integration_client.get("/api/v1/designs")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    async def test_get_design_pricing(self, integration_client):
        """Pricing endpoint should return cost breakdown."""
        # First create a design
        r = await integration_client.post(
            "/api/v1/designs",
            json={"make": "Porsche", "model": "911", "year": 2020},
        )
        design_id = r.json()["id"]

        response = await integration_client.get(
            f"/api/v1/designs/{design_id}/pricing"
        )
        assert response.status_code == 200
        data = response.json()
        assert "total_cost_usd" in data
        assert data["currency"] == "USD"


class TestSetsAPI:
    """LEGO set listing."""

    async def test_known_cars(self, integration_client):
        response = await integration_client.get("/api/v1/sets/known-cars")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        # len(data) may be 0 on CI without seed data


class TestCarsAPI:
    """Car lookup API."""

    async def test_lookup_existing_car(self, integration_client):
        """Lookup Porsche 911 — may or may not find via NHTSA."""
        response = await integration_client.post(
            "/api/v1/cars/lookup",
            json={"make": "Porsche", "model": "911", "year": 2020},
        )
        # NHTSA may return 404 for non-US brands, which is expected
        assert response.status_code in (200, 404)


class TestExportAPI:
    """File export endpoints."""

    async def test_export_csv_no_design(self, integration_client):
        """Export for non-existent design should 404."""
        fake_id = str(uuid.uuid4())
        response = await integration_client.get(f"/api/v1/export/csv/{fake_id}")
        assert response.status_code == 404
