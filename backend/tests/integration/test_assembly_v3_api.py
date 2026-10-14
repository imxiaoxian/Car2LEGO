"""Constructed API cases: creation dispatch and durable controls, without paid model calls."""

import json
import uuid
from unittest.mock import AsyncMock
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import settings
from app.database import Base
from app.deps import get_db
from app.main import app
from app.models.car import Car
from app.models.design import Design
from app.models.lego_set import LegoSet
from app.services.assembly_v3.jobs import JobStore
from app.services.assembly_v3.recipes import build_f40


@pytest.fixture
async def v3client(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"storage_path",str(tmp_path))
    monkeypatch.setattr(settings,"design_workflow","assembly_v3")
    monkeypatch.setenv("GENERATION_MODE","sync");monkeypatch.setenv("REDIS_URL","")
    engine=create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection: await connection.run_sync(Base.metadata.create_all)
    sessions=async_sessionmaker(engine,expire_on_commit=False)
    async with sessions() as db:
        db.add(Car(make="Ferrari",model="F40",year=1990));await db.commit()
    async def database():
        async with sessions() as db:
            yield db
            await db.commit()
    app.dependency_overrides[get_db]=database
    from app.services.studio_design_generator import StudioDesignGenerator
    generate=AsyncMock(return_value=dict(status="draft",parts_count=0,parts_data=[],metadata={"workflow_version":"assembly_v3"}))
    monkeypatch.setattr(StudioDesignGenerator,"generate",generate)
    try:
        async with AsyncClient(transport=ASGITransport(app=app),base_url="http://test") as client:
            yield client,sessions,tmp_path,generate
    finally:
        app.dependency_overrides.pop(get_db,None);await engine.dispose()


@pytest.mark.parametrize("scale",["1:38","1:24","1:16","1:12"])
async def test_multiscale_always_dispatches_assembly(v3client,scale):
    client,_,_,generate=v3client
    response=await client.post("/api/v1/designs",json={"make":"Ferrari","model":"F40","year":1990,"scale":scale})
    assert response.status_code==201,response.text
    assert response.json()["status"]=="pending" # mock doesn't update durable state
    assert response.json()["requested_scale"]==scale
    assert generate.call_args.kwargs["scale"]==scale
    assert response.json()["workflow_version"]=="assembly_v3"


async def test_reserved_scales_are_closed_and_catalog_is_honest(v3client):
    client,_,_,_=v3client
    response=await client.post("/api/v1/designs",json={"make":"Ferrari","model":"F40","year":1990,"scale":"1:8"})
    assert response.status_code==422
    catalog=(await client.get("/api/v1/sets/vehicles")).json()["vehicles"]
    assert len(catalog)>=20 and len({v["make"] for v in catalog})>=12
    assert all(not v["precision_verified"] for v in catalog)
    scales=(await client.get("/api/v1/designs/scales?make=Porsche&model=911")).json()["scales"]
    assert all(not s["precision_supported"] and not s["recipe_available"] for s in scales)
    assert [len(s["requirements"]["reference_views"]) for s in scales] == [6,14,18,20]
    assert scales[-1]["requirements"]["mechanisms"][-1]["minimum_instances"] == 4


async def test_policy_snapshot_is_exposed_without_upgrading_legacy_designs(v3client):
    from app.services.assembly_v3.requirements import requirements_for_scale
    client,sessions,root,_=v3client
    id=uuid.uuid4()
    async with sessions() as db:
        db.add(Design(id=id,status="draft",match_level=4,scale="1:16"));await db.commit()
    detail=(await client.get(f"/api/v1/designs/{id}")).json()
    assert detail["scale_requirements"]["scale"] == "1:16"
    assert detail["scale_requirements"]["applied_to_design"] is False
    assert detail["quality_report"] is None and detail["status"] == "draft"
    jobs=JobStore(root);jobs.ensure(str(id),{});owner=jobs.claim(str(id))
    snapshot=requirements_for_scale("1:16") | {"label":"Stored policy snapshot"}
    jobs.checkpoint(str(id),owner,"starting",1,scale_requirements=snapshot)
    jobs.finish(str(id),owner,"paused")
    detail=(await client.get(f"/api/v1/designs/{id}")).json()
    assert detail["scale_requirements"]["label"] == "Stored policy snapshot"
    assert detail["scale_requirements"]["applied_to_design"] is True


async def test_job_control_scene_and_quality_routes(v3client,monkeypatch):
    client,sessions,root,_=v3client
    id=uuid.uuid4()
    async with sessions() as db:
        db.add(Design(id=id,status="pending",match_level=4,scale="1:24"));await db.commit()
    jobs=JobStore(root);jobs.ensure(str(id),{});owner=jobs.claim(str(id))
    jobs.checkpoint(str(id),owner,"validation",70)
    assert (await client.post(f"/api/v1/designs/{id}/control/pause")).json()["status"]=="paused"
    jobs.finish(str(id),owner,"paused")
    assert (await client.get(f"/api/v1/designs/{id}/status")).json()["status"]=="paused"
    assert (await client.post(f"/api/v1/designs/{id}/control/retry?module=unknown")).status_code==422
    assert (await client.post(f"/api/v1/designs/{id}/control/cancel")).json()["status"]=="cancelled"
    assert (await client.get(f"/api/v1/designs/{id}/renders/wrong")).status_code==404
    assert (await client.get(f"/api/v1/designs/{id}/scene")).status_code==404


async def test_external_render_gallery_is_registered_and_design_scoped(v3client):
    from PIL import Image

    client,sessions,root,_=v3client
    id=uuid.uuid4()
    async with sessions() as db:
        db.add(Design(id=id,status="draft",match_level=4,scale="1:24"));await db.commit()
    render_dir=root/str(id)/"external"/"ldraw_mcp"
    render_dir.mkdir(parents=True)
    Image.new("RGB",(4,4),(255,0,0)).save(render_dir/"exterior-azimuth-m90.png")
    Image.new("RGB",(4,4),(0,255,0)).save(render_dir/"detail-engine-azimuth-m45.png")
    Image.new("RGB",(4,4),(255,255,0)).save(render_dir/"detail-seats-azimuth-m45.png")
    Image.new("RGB",(4,4),(0,0,255)).save(render_dir/"unlisted.png")
    (root/str(id)/"external"/"report.json").write_text(json.dumps({"checks":{"ldraw_mcp":{"status":"failed","bom":{"status":"failed","expected_total":1,"actual_total":1,"missing_parts":["65633.dat"]}}}}),encoding="utf-8")
    (render_dir/"report.json").write_text(json.dumps({
        "renders":["exterior-azimuth-m90.png"],
        "render_views":[{"view":"azimuth_m90","azimuth":-90,"artifact":"exterior-azimuth-m90.png"}],
        "detail_renders":[{"module":"engine","artifacts":["detail-engine-azimuth-m45.png"],
                            "views":[{"azimuth":-45,"artifact":"detail-engine-azimuth-m45.png"}]},
                           {"module":"seats","artifacts":["detail-seats-azimuth-m45.png"],
                            "views":[{"azimuth":-45,"artifact":"detail-seats-azimuth-m45.png"}]}],
    }),encoding="utf-8")

    detail=await client.get(f"/api/v1/designs/{id}")
    assert detail.status_code==200,detail.text
    assert detail.json()["external_checks"]["ldraw_mcp"]["status"]=="failed"
    records=detail.json()["external_renders"]
    assert records[0]["label"]=="整车外观 · 方位 -90°"
    assert records[1]["label"]=="发动机细节 · 方位 -45°"
    assert records[2]["label"]=="座椅细节 · 方位 -45°"
    assert (await client.get(f"/api/v1/designs/{id}/external-renders/exterior-azimuth-m90.png")).status_code==200
    assert (await client.get(f"/api/v1/designs/{id}/external-renders/detail-engine-azimuth-m45.png")).status_code==200
    assert (await client.get(f"/api/v1/designs/{id}/external-renders/detail-seats-azimuth-m45.png")).status_code==200
    assert (await client.get(f"/api/v1/designs/{id}/external-renders/unlisted.png")).status_code==404


async def test_physical_specification_import_and_design_snapshot_do_not_forge_verification(v3client):
    client,sessions,root,generate=v3client
    observation={"name":"door_length","value":110,"unit":"cm","method":"measured",
        "source_url":"https://www.ferrari.com/en-EN/auto/f40","source_status":"fetched",
        "source_kind":"manufacturer","vehicle_match":"exact","year_start":1990,"year_end":1990,
        "confidence":.9,"evidence":"Constructed explicit measurement"}
    response=await client.post("/api/v1/research/physical-specifications",json={"make":"Ferrari","model":"F40",
        "year":1990,"scale":"1:24","collect_sources":False,"measurements":[observation]})
    assert response.status_code==200,response.text
    data=response.json()
    assert data["measurements"]["door_length"]["value"]==1100
    assert data["measurements"]["door_length"]["source_status"]=="provided"
    assert not data["measurements"]["door_length"]["grounded"]
    stored=await client.get("/api/v1/research/physical-specifications",params={"make":"Ferrari","model":"F40","year":1990,"scale":"1:16"})
    assert stored.json()["measurements"]["door_length"]["target_model_mm"]==68.75
    id=uuid.uuid4()
    async with sessions() as db:
        car=await db.scalar(select(Car).where(Car.model=="F40"))
        db.add(Design(id=id,car_id=car.id,status="failed",match_level=4,scale="1:24"));await db.commit()
    detail=(await client.get(f"/api/v1/designs/{id}")).json()
    assert detail["physical_specifications"]["applied_to_design"] is False
    directory=root/str(id);directory.mkdir()
    snapshot=data | {"measurements":{}}
    (directory/"physical_specifications.json").write_text(json.dumps(snapshot),encoding="utf-8")
    detail=(await client.get(f"/api/v1/designs/{id}")).json()
    assert detail["physical_specifications"]["applied_to_design"] is True
    assert detail["physical_specifications"]["measurements"]=={}
    assert generate.await_count==0
