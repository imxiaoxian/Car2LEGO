"""Constructed specification documents; no model calls or live network access."""

import math
import httpx
import pytest
from pydantic import ValidationError

from app.services.vehicle_physics import PhysicalMeasurement, VehiclePhysicalProfile, load_profile, save_profile
from app.services.vehicle_research import parse_measurements, collect_physical_profile, fetch_document, document_text
from app.services.assembly_v3.specifications import specifications_from_profile, physical_layout_constraints, F40_SPEC


def measurement(name="length", value=4358, **kwargs):
    if name == "width":
        kwargs.setdefault("width_reference", "body")
    return PhysicalMeasurement(**dict(name=name, value=value, source_url="https://www.ferrari.com/en-EN/auto/f40",
        source_kind="manufacturer", source_status="fetched", vehicle_match="generation", year_start=1987,
        year_end=1992, confidence=.95, evidence="Constructed specification fixture", **kwargs))


def profile(*items, year=1990):
    return VehiclePhysicalProfile(make="Ferrari", model="F40", year=year, measurements=list(items))


@pytest.mark.parametrize("value,unit,expected", [(4.358,"m",4358), (435.8,"cm",4358), (100,"in",2540)])
def test_explicit_length_units(value, unit, expected):
    assert measurement(value=value, unit=unit).value == pytest.approx(expected)


def test_angles_have_explicit_datum_and_are_not_scaled():
    item = measurement("windshield_rake", math.pi/6, unit="rad", angle_reference="vertical")
    assert item.value == pytest.approx(60)
    assert item.angle_reference == "horizontal"
    result = profile(item).resolved("1:12")["measurements"]["windshield_rake"]
    assert result["value"] == 60 and result["target_ldu"] is None
    assert PhysicalMeasurement.model_validate(item.model_dump()).value == 60
    with pytest.raises(ValidationError):
        measurement("windshield_rake", 30, unit="deg")
    with pytest.raises(ValidationError):
        measurement("door_opening_angle", 65, unit="mm", angle_reference="closed")


def test_unsourced_unmatched_estimated_and_conflicting_data_do_not_become_grounded():
    item = measurement()
    for update in ({"source_url":None}, {"source_status":"provided"}, {"method":"estimated"},
                   {"year_start":None}, {"vehicle_match":"unconfirmed"}):
        result = profile(item.model_copy(update=update)).resolved()
        assert not result["measurements"]["length"]["grounded"]
    conflict = item.model_copy(update={"value":4430, "source_kind":"database"})
    result = profile(item, conflict).resolved()
    assert result["conflicts"] and not result["measurements"]["length"]["grounded"]
    assert not profile(item, year=2020).resolved()["measurements"]


def test_parse_separate_wheel_sizes_and_no_implicit_units_or_angles():
    parsed = parse_measurements("Length: 4,358 mm\nWidth: 77.56 in\nHeight: 1.124 m\nWheelbase: 245 cm\n"
        "Front tyres: 245/40 ZR17\nRear tires: 335/35 R17\nDoor length: 1100 mm\n"
        "Windscreen rake (from vertical): 30 deg\nDoor opening angle (closed): 65 deg\nSeat width: 420\n"
        "Windscreen inclination: 35 deg")
    values = {m.name: m.value for m in parsed}
    assert values["length"] == 4358 and values["height"] == 1124 and values["wheelbase"] == 2450
    assert values["width"] == pytest.approx(1970.024)
    assert values["front_tyre_diameter"] == pytest.approx(627.8)
    assert values["rear_tyre_diameter"] == pytest.approx(666.3)
    assert values["front_tyre_width"] == 245 and values["rear_tyre_width"] == 335
    assert values["door_length"] == 1100 and values["windshield_rake"] == 60
    assert values["door_opening_angle"] == 65 and "seat_width" not in values
    assert len([m for m in parsed if m.name == "length"]) == 1


def test_missing_values_and_conflicts_are_preserved_in_plan(tmp_path):
    data = profile(*(measurement(name, F40_SPEC[name]) for name in ("length","width","height","wheelbase")),
                   measurement("windshield_height", 700), measurement("windshield_rake", 60, unit="deg", angle_reference="horizontal"))
    save_profile(data, tmp_path)
    loaded = load_profile("Ferrari", "F40", 1990, tmp_path).resolved("1:24")
    assert loaded["overall_grounded"] and "door_length" in loaded["missing"]
    spec = specifications_from_profile(loaded)
    assert not spec["estimated"] and spec["length"] == 4358
    constraints = physical_layout_constraints(loaded)["targets"]
    assert constraints["windshield_height"]["value"] == pytest.approx(700/24/.4, abs=.0001)
    assert constraints["windshield_vertical_rise"]["value"] == pytest.approx(700/24/.4*math.sin(math.pi/3), abs=.0001)
    assert constraints["windshield_rake"]["value"] == 60
    missing = VehiclePhysicalProfile(make="Unknown",model="Car",year=2000).resolved()
    with pytest.raises(ValueError, match="dimensions unavailable"):
        specifications_from_profile(missing)
    assert specifications_from_profile(missing,F40_SPEC)["estimated"]


HTML = """<html><title>Ferrari F40</title><table class="infobox"><tr><th>Production</th><td>1987–1992</td></tr>
<tr><th>Length</th><td>4,358 mm</td></tr><tr><th>Width excluding mirrors</th><td>1,970 mm</td></tr>
<tr><th>Height</th><td>1,124 mm</td></tr><tr><th>Wheelbase</th><td>2,450 mm</td></tr>
<tr><th>Front tyres</th><td>245/40 ZR17</td></tr></table></html>"""


async def test_fetch_persist_and_match_year_with_constructed_documents(tmp_path):
    def respond(request):
        return httpx.Response(200, text=HTML, headers={"content-type":"text/html"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        data = await collect_physical_profile("Ferrari","F40",1990,storage=tmp_path,client=client)
        resolved = data.resolved("1:16")
        assert resolved["overall_grounded"] and resolved["measurements"]["length"]["target_ldu"] == pytest.approx(4358/16/.4, abs=.0001)
        assert resolved["measurements"]["front_tyre_diameter"]["method"] == "derived"
        assert all(s["status"] == "fetched" and s["sha256"] for s in data.sources)
        wrong_year = await collect_physical_profile("Ferrari","F40",2024,storage=tmp_path,client=client)
        assert not wrong_year.resolved()["measurements"]


async def test_blocked_sources_and_wrong_models_cannot_supply_dimensions(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(403))) as client:
        data = await collect_physical_profile("Ferrari","F40",1990,storage=tmp_path,client=client)
    assert not data.measurements and all(s["status"] == "unavailable" for s in data.sources)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200,text=HTML.replace("Ferrari F40","Ferrari F400"),headers={"content-type":"text/html"}))) as client:
        data = await collect_physical_profile("Ferrari","F40",1990,storage=tmp_path,client=client)
    assert not data.measurements


async def test_unapproved_and_redirected_urls_are_rejected_before_request():
    urls = []
    def respond(request):
        urls.append(str(request.url))
        return httpx.Response(302,headers={"location":"http://127.0.0.1/private"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        with pytest.raises(ValueError,match="approved public"):
            await fetch_document(client,"http://127.0.0.1/private","Ferrari")
        assert not urls
        with pytest.raises(ValueError,match="approved public"):
            await fetch_document(client,"https://www.ferrari.com/en-EN/auto/f40","Ferrari")
        assert len(urls) == 1


def test_variant_dimension_rows_and_multiple_infoboxes_require_disambiguation():
    _, text, ambiguous = document_text(HTML.replace("4,358 mm", "4,358 mm / 4,430 mm"))
    assert "length" not in {m.name for m in parse_measurements(text)}
    assert not ambiguous
    assert document_text(HTML + '<table class="infobox"><tr><th>Length</th><td>4430 mm</td></tr></table>')[2]
    assert not parse_measurements("Length: 4358 mm / 4430 mm")


def test_width_with_unknown_mirror_definition_cannot_become_grounded():
    item = measurement("width",1970).model_copy(update={"width_reference":"unspecified"})
    assert not item.grounded(1990)
    assert not item.model_copy(update={"width_reference":"including_mirrors"}).grounded(1990)


async def test_pipeline_freezes_source_snapshot_without_calling_models(tmp_path,monkeypatch):
    from app.services.assembly_v3.pipeline import AssemblyPipeline
    import app.services.assembly_v3.pipeline as pipeline_module
    from app.services.reference_images import ReferenceImageService
    received, collected = [], []
    first = profile(measurement())
    async def collect(*args, **kwargs):
        collected.append(args)
        return first
    async def stop_at_references(self,state):
        received.append(state["physical_specifications"])
        raise ValueError("Constructed stop before any model call")
    monkeypatch.setattr(pipeline_module,"collect_physical_profile",collect)
    monkeypatch.setattr(ReferenceImageService,"generate",stop_at_references)
    pipeline = AssemblyPipeline(tmp_path)
    result = await pipeline.generate("snapshot","Ferrari","F40",1990,"1:24")
    assert result["status"] == "failed" and len(collected) == 1
    save_profile(profile(measurement(value=4430)),tmp_path)
    await pipeline.generate("snapshot","Ferrari","F40",1990,"1:24")
    assert len(collected) == 1 and received[0] == received[1]
    assert received[1]["measurements"]["length"]["value"] == 4358
    assert pipeline.jobs.get("snapshot")["data"]["calls"] == {"text":0,"image":0}


async def test_empty_documents_are_recorded_as_unavailable(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: httpx.Response(200,text="",headers={"content-type":"text/html"}))) as client:
        data = await collect_physical_profile("Ferrari","F40",1990,storage=tmp_path,client=client)
    assert not data.measurements and all(s["status"] == "unavailable" for s in data.sources)


async def test_discovery_resolves_canonical_vehicle_title(tmp_path):
    requests = []
    def respond(request):
        requests.append(str(request.url))
        if request.url.path == "/w/api.php":
            return httpx.Response(200,json=["MCLAREN P1",["McLaren P1"],[""],["https://en.wikipedia.org/wiki/McLaren_P1"]])
        return httpx.Response(200,text=HTML.replace("Ferrari F40","McLaren P1").replace("1987–1992","2013–2015"),headers={"content-type":"text/html"})
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        data = await collect_physical_profile("MCLAREN","P1",2015,storage=tmp_path,client=client)
    assert requests[-1] == "https://en.wikipedia.org/wiki/McLaren_P1"
    assert data.resolved()["overall_grounded"]


def test_known_tyre_mismatch_fails_physical_gate_and_missing_glass_is_unverified(monkeypatch):
    import app.services.assembly_v3.physical_quality as quality
    from app.services.assembly_v3.scene import AssemblyScene, Module, PartInstance, Transform, BuildStep
    physical = profile(measurement("front_tyre_diameter",627.8), measurement("front_tyre_width",245),
                       measurement("windshield_width",1200)).resolved("1:24")
    scene = AssemblyScene(design_id="fixture",vehicle={},scale="1:24",specifications={"physical_data":physical},target_ldu={},
        parts=[PartInstance(id="t",part_num="18977.dat",color_id=0,module="wheel",feature="tyre",transform=Transform())],
        modules=[Module(id="wheel")],steps=[BuildStep(index=1,module="wheel",parts=["t"])])
    monkeypatch.setattr(quality,"geometry_bounds",lambda _: [{"x":[0,28],"z":[0,60]}])
    report = quality.physical_geometry_report(scene)
    assert report["status"] == "failed"
    assert any(c["name"] == "front_tyre_diameter" and c["status"] == "failed" for c in report["checks"])
    assert any(c["name"] == "windshield_width" and c["status"] == "unverified" for c in report["checks"])
