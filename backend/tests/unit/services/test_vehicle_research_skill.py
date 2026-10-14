"""Constructed web documents and search results; no paid provider calls."""

import io

import httpx
import pytest
from reportlab.pdfgen.canvas import Canvas

from app.services import vehicle_research_skill as skill
from app.services.vehicle_physics import PhysicalMeasurement, VehiclePhysicalProfile
from app.services.vehicle_research import collect_physical_profile, fetch_document, research_needed


def test_scale_targets_drive_queries_and_old_cache_is_searched():
    compact = skill.research_queries("Ferrari", "F40", 1990, ["length", "front_tyre_diameter"], "ferrari.com")
    assert {q["purpose"] for q in compact} == {"manufacturer", "overall", "wheels"}
    detailed = skill.research_queries("Ferrari", "F40", 1990,
        ["door_length", "windshield_rake", "seat_width", "engine_width"], "ferrari.com")
    assert {q["purpose"] for q in detailed} == {"doors", "glass", "seats", "engine"}
    profile = VehiclePhysicalProfile(make="Ferrari", model="F40", year=1990,
        sources=[{"url": "https://www.ferrari.com/en-EN/auto/f40", "status": "unavailable"}])
    assert research_needed(profile, "1:38")
    profile.research = {"version": skill.SKILL_VERSION, "status": "completed",
        "searched_fields": profile.resolved("1:38")["required_measurements"]}
    assert not research_needed(profile, "1:38")
    assert research_needed(profile, "1:12")
    profile.research["status"] = "searching"
    assert research_needed(profile, "1:38")


async def test_public_search_reads_links_and_falls_back_on_challenge():
    requests = []
    def respond(request):
        requests.append(request.url.host)
        if "duckduckgo" in request.url.host:
            return httpx.Response(200, text="<html>Challenge</html>")
        return httpx.Response(200, text='<rss><channel><item><title>Ferrari F40 specs</title>'
            '<link>https://www.ferrari.com/en-EN/auto/f40</link></item></channel></rss>')
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        result = await skill.search_web(client, {"query": "Ferrari F40 dimensions", "targets": ["length"]})
    assert result["status"] == "searched" and result["engine"] == "bing"
    assert result["results"][0]["url"].endswith("/auto/f40")
    assert requests == ["html.duckduckgo.com", "www.bing.com"]
    assert skill.result_url("//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.ferrari.com%2Fauto%2Ff40") == "https://www.ferrari.com/auto/f40"


async def test_discovered_document_supplies_dimensions_and_followup_targets_gaps(tmp_path):
    searches = []
    document = '<html><title>1990 Ferrari F40 technical dimensions</title><dl>'
    for label, value in [("Length", "4358 mm"), ("Width excluding mirrors", "1970 mm"),
                         ("Height", "1124 mm"), ("Wheelbase", "2450 mm")]:
        document += f"<dt>{label}</dt><dd>{value}</dd>"
    document += "</dl></html>"
    def respond(request):
        if "duckduckgo" in request.url.host:
            searches.append(request.url.params["q"])
            return httpx.Response(200, text='<a class="result__a" href="https://www.auto-data.net/en/ferrari-f40-1990">Ferrari F40 dimensions</a>')
        if request.url.host == "www.auto-data.net":
            return httpx.Response(200, text=document, headers={"content-type": "text/html"})
        return httpx.Response(403)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        profile = await collect_physical_profile("Ferrari", "F40", 1990, storage=tmp_path,
            scale="1:24", client=client, use_model=False)
    result = profile.resolved("1:24")
    assert result["overall_grounded"]
    assert result["measurements"]["length"]["source_url"].startswith("https://www.auto-data.net/")
    assert result["measurements"]["length"]["target_model_mm"] == pytest.approx(4358 / 24)
    assert profile.research["status"] == "completed"
    assert any("windscreen" in q for q in searches)
    assert any("door dimensions" in q for q in searches)
    followups = [q for q in searches if "technical drawing" in q]
    assert followups and not any("wheelbase" in q for q in followups)
    assert "windshield_rake" in profile.research["missing_fields"]


async def test_search_outage_is_retained_and_does_not_invent_data(tmp_path):
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
        profile = await collect_physical_profile("Ferrari", "F40", 1990, storage=tmp_path, client=client, use_model=False)
    assert profile.research["status"] == "unavailable"
    assert all(q["attempts"] and not q["results"] for q in profile.research["queries"])
    assert not profile.measurements


async def test_omitted_year_searches_model_and_switching_model_uses_new_cache(tmp_path):
    from app.services.vehicle_physics import load_profile
    searches = []
    document = '<html><title>Ferrari F40</title><dl><dt>Production</dt><dd>1987-1992</dd>'
    document += '<dt>Length</dt><dd>4358 mm</dd></dl></html>'
    def respond(request):
        if "duckduckgo" in request.url.host:
            searches.append(request.url.params["q"])
            return httpx.Response(200, text='<a class="result__a" href="https://www.ferrari.com/en-EN/auto/f40">Ferrari F40 specifications</a>')
        if request.url.path.endswith("/auto/f40"):
            return httpx.Response(200, text=document, headers={"content-type":"text/html"})
        return httpx.Response(403)
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        profile = await collect_physical_profile("Ferrari", "F40", storage=tmp_path, client=client, use_model=False)
    result = profile.resolved()
    assert result["vehicle"]["year"] is None
    assert result["measurements"]["length"]["grounded"]
    assert searches and all("None" not in query and "2024" not in query for query in searches)
    assert not research_needed(load_profile("Ferrari", "F40", None, tmp_path), "1:38")
    assert research_needed(load_profile("Ferrari", "F50", None, tmp_path), "1:38")
    assert research_needed(load_profile("Porsche", "F40", None, tmp_path), "1:38")
    assert research_needed(load_profile("Ferrari", "F40", 1990, tmp_path), "1:38")
    queries = skill.research_queries("Ferrari", "F50", None, ["length"], "ferrari.com")
    assert all('"Ferrari F50"' in query["query"] and "F40" not in query["query"] for query in queries)


async def test_pdf_technical_document_and_invalid_pdf():
    stream = io.BytesIO()
    canvas = Canvas(stream)
    canvas.setTitle("1990 Ferrari F40 specifications")
    canvas.drawString(20, 800, "Length: 4358 mm")
    canvas.drawString(20, 780, "Wheelbase: 2450 mm")
    canvas.save()
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,
        content=stream.getvalue(), headers={"content-type": "application/pdf"}))) as client:
        _, document = await fetch_document(client, "https://www.ferrari.com/f40-technical.pdf", "Ferrari")
    assert "Length: 4358 mm" in document and "1990 Ferrari F40" in document
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200,
        content=b"broken pdf", headers={"content-type": "application/pdf"}))) as client:
        with pytest.raises(ValueError, match="Unreadable"):
            await fetch_document(client, "https://www.ferrari.com/f40-technical.pdf", "Ferrari")


async def test_model_extraction_requires_verbatim_numeric_and_year_evidence(monkeypatch):
    text = "Ferrari F40. Production: 1987-1992. Overall length is 4.358 m. Door length: unknown. Seat width: 420. Windscreen rake (vertical): 30 deg."
    extracted = skill.DocumentExtraction(vehicle_match="generation", year_start=1987, year_end=1992,
        identity_evidence="Ferrari F40", year_evidence="Production: 1987-1992",
        measurements=[PhysicalMeasurement(name="length", value=4.358, unit="m", confidence=.95,
            evidence="Overall length is 4.358 m."),
            PhysicalMeasurement(name="door_length", value=1100, evidence="Door length: unknown."),
            PhysicalMeasurement(name="seat_width", value=420, evidence="Seat width: 420."),
            PhysicalMeasurement(name="windshield_rake", value=30, unit="deg", angle_reference="vertical", confidence=.95,
                evidence="Windscreen rake (vertical): 30 deg.")])
    class Model:
        def with_structured_output(self, schema):
            return self
        async def ainvoke(self, messages):
            assert "Vehicle Specification Research" in messages[0].content
            return extracted
    monkeypatch.setattr(skill, "create_text_llm", lambda **_: Model())
    result = await skill.extract_document(text, "Ferrari F40", "Ferrari", "F40", 1990,
        "https://www.ferrari.com/f40", "manufacturer")
    assert len(result.measurements) == 2 and result.measurements[0].value == 4358
    assert result.measurements[0].grounded(1990)
    assert result.measurements[1].value == 60 and result.measurements[1].grounded(1990)
    result = await skill.extract_document(text, "Ferrari F40", "Ferrari", "F40", None,
        "https://www.ferrari.com/f40", "manufacturer")
    assert result.measurements[0].grounded(None)
    assert result.year_start == 1987 and result.year_end == 1992
    extracted.year_evidence = "1990 (inferred from request)"
    result = await skill.extract_document(text, "Ferrari F40", "Ferrari", "F40", 1990,
        "https://www.ferrari.com/f40", "manufacturer")
    assert result.measurements and not result.measurements[0].grounded(1990)
    assert result.year_start is None and result.year_end is None
