"""HTTP regressions with constructed references/model output, no external calls."""

import io
import json
import uuid
import zipfile
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from httpx import ASGITransport, AsyncClient
from PIL import Image
from sqlalchemy import event
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.deps import get_db
from app.main import app
from app.models.car import Car
from app.models.design import Design
from app.models.lego_set import LegoSet
from app.services.vision_analyzer import CarFeatures, VisionAnalyzer


@pytest.fixture
async def guided_client(tmp_path, monkeypatch, mock_reference_images, mock_image_guided_llm):
    monkeypatch.setenv("GENERATION_MODE", "sync")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setattr(settings, "storage_path", str(tmp_path))
    monkeypatch.setattr(settings, "design_workflow", "v2")
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    @event.listens_for(engine.sync_engine, "connect")
    def foreign_keys(connection, record):
        connection.execute("PRAGMA foreign_keys=ON")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        session.add(Car(make="Ferrari", model="F40", year=1990))
        await session.commit()

    async def database():
        async with sessions() as session:
            yield session
            await session.commit()

    from app import database as database_module
    monkeypatch.setattr(database_module, "async_session", sessions)
    app.dependency_overrides[get_db] = database
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, sessions, tmp_path
    finally:
        app.dependency_overrides.pop(get_db, None)
        await engine.dispose()


@pytest.mark.parametrize("official", [False, True])
async def test_text_to_references_five_sections_and_download(guided_client, official):
    client, sessions, storage = guided_client
    if official:
        async with sessions() as session:
            session.add(LegoSet(set_num="76934-1", name="Ferrari F40", car_make="Ferrari",
                                car_model="F40", year=2024, brick_count=318))
            await session.commit()
    response = await client.post("/api/v1/designs", json={"make": "Ferrari", "model": "F40", "year": 1990})
    assert response.status_code == 201, response.text
    design = response.json()
    assert design["status"] == "completed", design
    if official:
        assert design["match"]["level"] == 1
    assert design["parts_count"] == sum(p["quantity"] for p in design["parts"])
    assert len(design["reference_images"]) == 6
    preview = await client.get(design["assembly_preview_url"])
    assert preview.status_code == 200
    assert preview.headers["content-type"] == "image/png"
    assert (await client.get(design["assembly_preview_rear_url"])).status_code == 200
    assert (await client.get(f"/api/v1/designs/{design['id']}/assembly-preview?view=invalid")).status_code == 422
    assert design["quality_level"] == "stylized_prototype"
    for reference in design["reference_images"]:
        image = await client.get(reference["url"])
        assert image.status_code == 200
        assert image.headers["content-type"] == "image/png"
        assert reference["synthetic"]
    package = await client.get(design["file_urls"]["io"])
    assert package.status_code == 200
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert archive.read("model.ldr").decode().count("0 STEP") == 5
    download = await client.get(f"/api/v1/designs/{design['id']}/open-in-studio")
    assert download.status_code == 200
    status = (await client.get(f"/api/v1/designs/{design['id']}/status")).json()
    assert status["progress"] == 100
    assert json.loads((storage / design["id"] / "generation_status.json").read_text())["stage"] == "completed"


def photo():
    buffer = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(buffer, format="PNG")
    return buffer.getvalue()


async def test_photo_recognition_preserves_year_features_and_source(guided_client, monkeypatch, mock_reference_images):
    client, sessions, _ = guided_client
    seen = {}

    async def analyze(self, filename):
        seen["temporary_path"] = filename
        return CarFeatures(make="Ferrari", model="F40", year=1990, body_style="sports_car",
                           primary_color_name="Rosso Corsa", wheel_type="five_spoke_classic")

    async def generate(self, state):
        seen["state"] = dict(state)
        return await mock_reference_images(self, state)

    from app.services.reference_images import ReferenceImageService
    monkeypatch.setattr(VisionAnalyzer, "analyze_image", analyze)
    monkeypatch.setattr(ReferenceImageService, "generate", generate)
    response = await client.post("/api/v1/designs/from-image", files={"image": ("car.png", photo(), "image/png")})
    assert response.status_code == 201, response.text
    assert response.json()["status"] == "completed"
    assert response.json()["car"]["year"] == 1990
    assert seen["state"]["vehicle_features"]["primary_color_name"] == "Rosso Corsa"
    assert Path(seen["state"]["source_image_path"]).is_file()
    assert not Path(seen["temporary_path"]).exists()
    async with sessions() as session:
        design = await session.get(Design, uuid.UUID(response.json()["id"]))
        assert design.metadata_["vision_features"]["wheel_type"] == "five_spoke_classic"


async def test_invalid_photo_and_scale_are_422(guided_client, monkeypatch):
    client, _, _ = guided_client
    invalid = await client.post("/api/v1/designs/from-image", files={"image": ("bad.jpg", b"not an image", "image/jpeg")})
    assert invalid.status_code == 422
    monkeypatch.setattr(VisionAnalyzer, "analyze_image", AsyncMock(return_value=CarFeatures(make="Ferrari", model="F40", year=1990)))
    invalid_scale = await client.post("/api/v1/designs/from-image", files={"image": ("car.png", photo(), "image/png")}, data={"scale": "bad"})
    assert invalid_scale.status_code == 422


async def test_image_api_failure_returns_failed_design(guided_client, monkeypatch):
    from app.services.reference_images import ReferenceImageService
    client, _, _ = guided_client
    monkeypatch.setattr(ReferenceImageService, "generate", AsyncMock(side_effect=ValueError("gpt-image-2.5-sunburst unavailable")))
    response = await client.post("/api/v1/designs", json={"make": "Ferrari", "model": "F40", "year": 1990})
    data = response.json()
    assert data["status"] == "failed"
    assert "gpt-image-2.5-sunburst unavailable" in data["error_message"]
    assert not data["file_urls"]["io"]


async def test_no_redis_background_generation_commits_before_dispatch(guided_client, monkeypatch):
    client, _, _ = guided_client
    monkeypatch.setenv("GENERATION_MODE", "auto")
    response = await client.post("/api/v1/designs", json={"make": "Ferrari", "model": "F40", "year": 1990})
    assert response.status_code == 201
    assert response.json()["status"] == "pending"
    # ASGITransport waits for BackgroundTasks; the separate session has now committed its result.
    detail = (await client.get(f"/api/v1/designs/{response.json()['id']}")).json()
    assert detail["status"] == "completed", detail


@pytest.mark.parametrize("worker", ["generation", "customization"])
async def test_worker_persists_string_uuid_and_replaces_parts_on_repeat(guided_client, monkeypatch, worker):
    from tasks import generation, customization
    module = generation if worker == "generation" else customization
    client, sessions, _ = guided_client
    monkeypatch.setattr(module, "async_session", sessions)
    response = await client.post("/api/v1/designs", json={"make": "Ferrari", "model": "F40", "year": 1990})
    data = response.json()
    result = {"status": "completed", "parts_count": data["parts_count"], "parts_data": data["parts"]}
    update = generation._update_design if worker == "generation" else customization._update_customized_design
    if worker == "customization":
        assert (await customization._load_base_design(data["id"]))["parts_summary"]
    for _ in range(2):
        await update(data["id"], result)
    detail = (await client.get(f"/api/v1/designs/{data['id']}")).json()
    assert detail["parts"] == data["parts"]
