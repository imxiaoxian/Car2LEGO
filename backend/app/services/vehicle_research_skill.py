"""Search execution and evidence extraction for the vehicle research skill."""

import base64
import json
import re
from pathlib import Path
from typing import Literal
from urllib.parse import parse_qs, unquote, urlparse

import httpx
from langchain_core.messages import HumanMessage, SystemMessage
from lxml import etree, html
from pydantic import BaseModel, Field

from app.agents.models import create_text_llm
from .vehicle_physics import PhysicalMeasurement

SKILL_VERSION = "vehicle_research_skill_v2"
SKILL_PATH = Path(__file__).resolve().parents[1] / "skills" / "research-vehicle-specifications" / "SKILL.md"
GROUPS = [
    ("overall", {"length", "width", "height", "wheelbase"}, "technical specifications dimensions length width excluding mirrors height wheelbase"),
    ("wheels", {"front_track", "rear_track", "front_tyre_diameter", "rear_tyre_diameter", "front_tyre_width", "rear_tyre_width", "front_rim_diameter", "rear_rim_diameter"}, "front rear tyre tire sizes wheel rim diameter track technical specifications"),
    ("glass", {"windshield_width", "windshield_height", "windshield_rake"}, "windscreen windshield glass width height rake angle body repair drawing dimensions"),
    ("doors", {"door_length", "door_height", "door_opening_angle"}, "door dimensions aperture hinge opening angle workshop body repair manual"),
    ("seats", {"seat_width"}, "front seat width dimensions interior workshop drawing"),
    ("engine", {"engine_length", "engine_width", "engine_height"}, "engine envelope length width height engine bay dimensions workshop drawing"),
]


def research_queries(make: str, model: str, year: int | None, wanted: list[str], official: str | None) -> list[dict]:
    vehicle = f'"{make} {model}"' + (f" {year}" if year is not None else "")
    queries = []
    for purpose, fields, terms in GROUPS:
        targets = sorted(fields & set(wanted))
        if not targets:
            continue
        if official and purpose == "overall":
            queries.append({"query": f"site:{official} {vehicle} {terms}", "purpose": "manufacturer",
                            "targets": targets, "make": make, "model": model, "year": year})
        queries.append({"query": f"{vehicle} {terms}", "purpose": purpose, "targets": targets,
                        "make": make, "model": model, "year": year})
    return queries


def result_url(value: str) -> str:
    if value.startswith("//"):
        value = "https:" + value
    parsed = urlparse(value)
    params = parse_qs(parsed.query)
    if parsed.hostname and parsed.hostname.endswith("duckduckgo.com"):
        return params.get("uddg", [value])[0]
    if parsed.hostname and parsed.hostname.endswith("bing.com") and params.get("u"):
        encoded = params["u"][0]
        if encoded.startswith("a1"):
            try:
                return base64.urlsafe_b64decode(encoded[2:] + "=" * (-len(encoded[2:]) % 4)).decode()
            except (ValueError, UnicodeError):
                return ""
    return unquote(value)


async def search_web(client: httpx.AsyncClient, query: dict) -> dict:
    """Execute a query using public search endpoints, retaining failure evidence."""
    attempts = []
    bing_query = query["query"]
    if query.get("model"):
        # Some regional search endpoints over-weight the first brand token.
        terms = bing_query.replace(f'"{query["make"]} {query["model"]}"', "")
        if query.get("year") is not None:
            terms = terms.replace(str(query["year"]), "")
        bing_query = f'{query["model"]} {query["make"]} {terms}'.strip()
    for engine, url, params in (
        ("duckduckgo", "https://html.duckduckgo.com/html/", {"q": query["query"]}),
        ("bing", "https://www.bing.com/search", {"q": bing_query, "format": "rss"}),
    ):
        try:
            response = await client.get(url, params=params, follow_redirects=True)
            response.raise_for_status()
            if len(response.content) > 2_000_000:
                raise ValueError("Search response exceeds 2 MB")
            if engine == "bing":
                root = etree.fromstring(response.content, parser=etree.XMLParser(resolve_entities=False, no_network=True))
                results = [{"title": e.findtext("title") or "", "url": e.findtext("link") or ""}
                           for e in root.findall(".//item")]
            else:
                root = html.fromstring(response.text)
                results = [{"title": e.text_content().strip(), "url": result_url(e.get("href", ""))}
                           for e in root.xpath("//a[contains(concat(' ',normalize-space(@class),' '),' result__a ')]")]
            if not results:
                raise ValueError("Search returned no result links (possibly a challenge page)")
            if query.get("model"):
                model_pattern = r"(?<!\w)" + r"[\W_]*".join(map(re.escape, re.findall(r"\w+", query["model"].casefold()))) + r"(?!\w)"
                results = [r for r in results if re.search(model_pattern, r["title"].casefold() + " " + unquote(r["url"]).casefold())]
                if not results:
                    raise ValueError("Search results do not mention the requested vehicle model")
            return query | {"engine": engine, "executed_query": params["q"], "status": "searched", "results": results[:10], "attempts": attempts}
        except (httpx.HTTPError, ValueError, etree.LxmlError) as exc:
            attempts.append({"engine": engine, "error": (str(exc) or type(exc).__name__)[:250]})
    return query | {"status": "unavailable", "results": [], "attempts": attempts}


class DocumentExtraction(BaseModel):
    vehicle_match: Literal["exact", "generation", "unconfirmed", "mismatch"]
    year_start: int | None = Field(default=None, ge=1886, le=2100)
    year_end: int | None = Field(default=None, ge=1886, le=2100)
    identity_evidence: str = Field(default="", max_length=1200)
    year_evidence: str = Field(default="", max_length=1200)
    measurements: list[PhysicalMeasurement] = Field(default_factory=list, max_length=40)


def _contains(text: str, quote: str) -> bool:
    normal = lambda value: re.sub(r"\s+", " ", value).strip().casefold()
    return bool(quote.strip()) and normal(quote) in normal(text)


async def extract_document(text: str, title: str, make: str, model: str, year: int | None,
                           source_url: str, source_kind: str, state: dict | None = None) -> DocumentExtraction:
    instructions = SKILL_PATH.read_text(encoding="utf-8")
    messages = [SystemMessage(content=instructions), HumanMessage(content=json.dumps({
        "vehicle": {"make": make, "model": model, "year": year}, "source_url": source_url,
        "title": title, "document": text[:45000],
    }, ensure_ascii=True))]
    factory = lambda: create_text_llm(max_tokens=6000).with_structured_output(DocumentExtraction).ainvoke(messages)
    if state is not None:
        from .reference_images import model_call
        result = await model_call(factory, state, "text", "vehicle_research", 2)
    else:
        result = await factory()
    # A model selects evidence; fetched text and the runtime establish provenance.
    from .vehicle_research import _matches_identity, NUMBER, UNITS, _unit
    matched = _contains(text, result.identity_evidence) and _matches_identity(result.identity_evidence, make, model)
    year_supported = bool(result.year_start and result.year_end and result.year_start <= result.year_end
                          and (year is None or result.year_start <= year <= result.year_end)
                          and _contains(text, result.year_evidence)
                          and str(result.year_start) in result.year_evidence and str(result.year_end) in result.year_evidence)
    trusted = matched and year_supported and result.vehicle_match in ("exact", "generation")
    values = []
    for measurement in result.measurements:
        if not _contains(text, measurement.evidence) or measurement.method == "estimated":
            continue
        # Reject quotes with no numeric evidence, including invented dimensions.
        if measurement.method == "derived":
            # Only the deterministic tyre parser establishes derived dimensions.
            continue
        quote = measurement.evidence
        if measurement.unit == "mm":
            pairs = re.findall(rf"({NUMBER})\s*({UNITS})\b", quote, re.I)
            # Tables may declare a unit in the label rather than after the value.
            labelled = re.search(rf"\(({UNITS})\)\s*[:=]?\s*({NUMBER})\b", quote, re.I)
            if labelled:
                pairs.append((labelled[2], labelled[1]))
            factors = {"mm": 1, "cm": 10, "m": 1000, "in": 25.4}
            numeric_match = any(abs(float(n.replace(",", "")) * factors[_unit(unit)] - measurement.value) < .02
                                for n, unit in pairs)
        else:
            pairs = re.findall(rf"({NUMBER})\s*(degrees?|deg|\u00b0|rad(?:ians)?|度)", quote, re.I)
            angle_values = [float(n.replace(",", "")) * (180 / 3.141592653589793 if unit.lower().startswith("rad") else 1)
                      for n, unit in pairs]
            if measurement.name == "windshield_rake":
                numeric_match = bool(re.search(r"horizontal|vertical|水平|垂直|竖直", quote, re.I)) and any(
                    abs((90 - value if re.search(r"vertical|垂直|竖直", quote, re.I) else value) - measurement.value) < .02 for value in angle_values)
            else:
                numeric_match = bool(re.search(r"closed|关闭|闭合", quote, re.I)) and any(abs(v - measurement.value) < .02 for v in angle_values)
        if not numeric_match:
            continue
        values.append(measurement.model_copy(update={"source_url": source_url, "source_kind": source_kind,
            "source_status": "fetched", "vehicle_match": result.vehicle_match if trusted else "unconfirmed",
            "year_start": result.year_start if year_supported else None,
            "year_end": result.year_end if year_supported else None,
            "confidence": min(measurement.confidence, .95 if source_kind == "manufacturer" else .8)}))
    return result.model_copy(update={"measurements": values, "vehicle_match": result.vehicle_match if trusted else "unconfirmed",
        "year_start": result.year_start if year_supported else None, "year_end": result.year_end if year_supported else None})
