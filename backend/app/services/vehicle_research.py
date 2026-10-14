"""Fetch public vehicle documents; extract explicitly labelled physical data only."""

import asyncio
import hashlib
import io
import re
from datetime import datetime, timezone
from html import escape
from urllib.parse import quote, urljoin, urlparse

import httpx
from lxml import html
from lxml.etree import LxmlError

from app.config import settings
from .car_research import CarResearchService
from .vehicle_physics import PhysicalMeasurement, VehiclePhysicalProfile, FIELDS, load_profile, save_profile
from .vehicle_research_skill import SKILL_VERSION, research_queries, search_web, extract_document


LABELS = {
    "length": r"(?:overall length|length|车长|长度)",
    "width": r"(?:width excluding mirrors|width without mirrors|overall width|width|车宽|宽度)",
    "height": r"(?:overall height|height|车高|高度)",
    "wheelbase": r"(?:wheelbase|wheel base|轴距)",
    "front_track": r"(?:front track|track front|前轮距)",
    "rear_track": r"(?:rear track|track rear|后轮距)",
    "door_length": r"(?:front door length|door length|车门长度)",
    "door_height": r"(?:front door height including glass|door height including glass|车门高度含玻璃)",
    "windshield_width": r"(?:windshield width|windscreen width|前风挡宽度)",
    "windshield_height": r"(?:windshield slant height|windscreen slant height|前风挡斜高)",
    "seat_width": r"(?:front seat width|seat width|座椅宽度)",
    "engine_length": r"(?:engine length|发动机长度)",
    "engine_width": r"(?:engine width|发动机宽度)",
    "engine_height": r"(?:engine height|发动机高度)",
}
NUMBER = r"\d{1,3}(?:,\d{3})+(?:\.\d+)?|\d+(?:\.\d+)?"
UNITS = r"millimet(?:er|re)s?|centimet(?:er|re)s?|met(?:er|re)s?|inches|inch|mm|cm|in|m|毫米|厘米|米|英寸"
UNIT_MAP = {"毫米": "mm", "厘米": "cm", "米": "m", "英寸": "in"}
KNOWN_SOURCES = {("ferrari", "f40"): ("https://www.ferrari.com/en-EN/auto/f40", 1987, 1992)}
KNOWN_BRAND_SOURCES = {"ferrari": "https://www.ferrari.com/zh-CN"}


def _normal(value: str) -> str:
    return re.sub(r"[^\w]", "", value.casefold())


def _matches_identity(title: str, make: str, model: str) -> bool:
    def present(value):
        tokens = re.findall(r"\w+", value.casefold())
        return bool(tokens and re.search(r"(?<!\w)" + r"[\W_]*".join(map(re.escape, tokens)) + r"(?!\w)", title.casefold()))
    return present(make) and present(model)


def _unit(value: str) -> str:
    value = value.casefold()
    if value in UNIT_MAP:
        return UNIT_MAP[value]
    for prefix, result in (("milli", "mm"), ("centi", "cm"), ("met", "m"), ("inch", "in")):
        if value.startswith(prefix):
            return result
    return value


def parse_measurements(text: str, **provenance) -> list[PhysicalMeasurement]:
    """No unit guessing, unlabeled angles or cross-document identity inference."""
    result = []
    for name, label in LABELS.items():
        # Line boundaries keep 'door length' from becoming the car's length.
        pattern = rf"(?:^|\n)\s*{label}\s*[:=]\s*({NUMBER})\s*({UNITS})\b"
        for match in re.finditer(pattern, text, re.I):
            tail = text[match.end():].split("\n", 1)[0]
            if re.search(rf"(?:{NUMBER})\s*(?:{UNITS})\b", tail, re.I):
                continue
            reference = {"width_reference": "body" if re.search(r"(?:excluding|without) mirrors", match[0], re.I) else "unspecified"} if name == "width" else {}
            result.append(PhysicalMeasurement(name=name, value=float(match[1].replace(",", "")),
                unit=_unit(match[2]), evidence=match[0].strip(), **reference, **provenance))
    for name, label, datum in (("windshield_rake", r"(?:windshield|windscreen) (?:rake|inclination)", r"horizontal|vertical"),
                               ("door_opening_angle", r"door opening angle", r"closed")):
        pattern = rf"(?:^|\n)\s*{label}\s*\((?:from |above |to )?({datum})\)\s*[:=]\s*({NUMBER})\s*(deg(?:rees)?|°|rad)"
        for match in re.finditer(pattern, text, re.I):
            result.append(PhysicalMeasurement(name=name, value=float(match[2]), unit="rad" if match[3].lower() == "rad" else "deg",
                angle_reference=match[1].lower(), evidence=match[0].strip(), **provenance))
    for axle in ("front", "rear"):
        pattern = rf"(?:^|\n)\s*(?:{axle} (?:tyres?|tires?)|(?:tyres?|tires?) {axle})\s*[:=]\s*(\d{{3}})\s*/\s*(\d{{2}})\s*(?:Z\s*)?R\s*(\d{{2}})\b"
        for match in re.finditer(pattern, text, re.I):
            width, aspect, rim = map(int, match.groups())
            if not (100 <= width <= 500 and 15 <= aspect <= 95 and 10 <= rim <= 30):
                continue
            evidence = match[0].strip()
            result.append(PhysicalMeasurement(name=axle + "_tyre_width", value=width, evidence=evidence, **provenance))
            derived = provenance | {"method": "derived"}
            result.append(PhysicalMeasurement(name=axle + "_rim_diameter", value=rim * 25.4, evidence=evidence,
                derivation="rim_inches * 25.4", **derived))
            result.append(PhysicalMeasurement(name=axle + "_tyre_diameter", value=rim * 25.4 + 2 * width * aspect / 100,
                evidence=evidence, derivation="rim_inches * 25.4 + 2 * section_width_mm * aspect_ratio / 100; nominal unloaded diameter, not rolling radius", **derived))
    return result


def document_text(document: str) -> tuple[str, str, bool]:
    root = html.fromstring(document)
    for element in root.xpath("//script|//style|//nav|//footer|//sup"):
        element.drop_tree()
    title = " ".join(root.xpath("//title/text()|//h1//text()"))
    infoboxes = root.xpath("//table[contains(concat(' ', normalize-space(@class), ' '), ' infobox ')]")
    ambiguous = len(infoboxes) > 1
    scopes = infoboxes[:1] or [root]
    lines = []
    for scope in scopes:
        for row in scope.xpath(".//tr"):
            cells = row.xpath("./th|./td")
            if len(cells) == 2:
                label, value = (" ".join(c.itertext()).strip() for c in cells)
                # Multiple dimension values (variants/markets) need disambiguation.
                if len(re.findall(rf"(?:{NUMBER})\s*(?:{UNITS})\b", value, re.I)) <= 1:
                    lines.append(f"{label}: {value}")
        for label in scope.xpath(".//dt"):
            value = label.getnext()
            if value is not None and value.tag == "dd":
                lines.append(f"{' '.join(label.itertext())}: {' '.join(value.itertext())}")
        lines.extend(scope.text_content().splitlines())
    return title, "\n".join(lines), ambiguous


def _allowed(url: str, make: str) -> bool:
    try:
        parsed = urlparse(url)
        port = parsed.port
    except ValueError:
        return False
    hosts = ["en.wikipedia.org", *CarResearchService.REVIEW_SITES,
             "automobile-catalog.com", "auto-data.net", "cars-data.com", "carsized.com",
             "press.bmwgroup.com", "media.ford.com", "media.stellantis.com",
             "media.mclaren.com", "newsroom.porsche.com", "media.mercedes-benz.com",
             "media.toyota.co.uk", "media.astonmartin.com", "media.lotuscars.com",
             "dongchedi.com", "autohome.com.cn", "carnewschina.com"]
    official = CarResearchService.get_official_domain(make)
    if official:
        hosts.append(official)
    host = (parsed.hostname or "").lower()
    return bool(parsed.scheme == "https" and not parsed.username and not parsed.password
                and port in (None, 443) and any(host == h or host.endswith("." + h) for h in hosts))


async def fetch_document(client: httpx.AsyncClient, url: str, make: str) -> tuple[str, str]:
    for _ in range(5):
        if not _allowed(url, make):
            raise ValueError("Source URL must use an approved public manufacturer or automotive reference domain")
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            pdf = "application/pdf" in content_type
            if not pdf and not any(t in content_type for t in ("text/html", "text/plain", "application/xhtml")):
                raise ValueError("Source is not an HTML/text/PDF document")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > (8_000_000 if pdf else 2_000_000):
                    raise ValueError("Source document exceeds size limit")
            if pdf:
                from pypdf import PdfReader
                from pypdf.errors import PdfReadError
                def read_pdf():
                    try:
                        reader = PdfReader(io.BytesIO(data))
                    except PdfReadError as exc:
                        raise ValueError("Unreadable source PDF") from exc
                    title = str((reader.metadata or {}).get("/Title", ""))
                    pages = []
                    size = 0
                    for index, page in enumerate(reader.pages[:80], 1):
                        text = page.extract_text() or ""
                        if text.strip():
                            pages.append(f"Page {index}\n{text}")
                        size += len(text)
                        if size > 120000:
                            break
                    if not pages:
                        raise ValueError("PDF requires OCR; no extractable numeric text")
                    return f"<html><title>{escape(title)}</title><pre>{escape(chr(10).join(pages))}</pre></html>"
                return url, await asyncio.to_thread(read_pdf)
            return url, data.decode(response.encoding or "utf-8", errors="replace")
    raise ValueError("Too many document redirects")


def research_needed(profile: VehiclePhysicalProfile, scale: str) -> bool:
    required = profile.resolved(scale)["required_measurements"]
    return (profile.research.get("version") != SKILL_VERSION
            or profile.research.get("status") != "completed"
            or not set(required).issubset(profile.research.get("searched_fields", [])))


async def collect_physical_profile(make: str, model: str, year: int | None = None, *, storage=None, scale: str = "1:38",
                                   source_urls: list[str] | None = None,
                                   client: httpx.AsyncClient | None = None, state: dict | None = None,
                                   use_model: bool | None = None) -> VehiclePhysicalProfile:
    if client is None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5), headers={"User-Agent": "Car2LEGO/3.0 vehicle-specification-research"}, follow_redirects=False) as session:
            return await collect_physical_profile(make, model, year, storage=storage, scale=scale,
                source_urls=source_urls, client=session, state=state, use_model=use_model)
    profile = load_profile(make, model, year, storage)
    policy = profile.resolved(scale)
    wanted = list(dict.fromkeys(policy["required_measurements"] + policy["recommended_measurements"]))
    use_model = settings.vehicle_research_model_extraction and bool(settings.openai_api_key) if use_model is None else use_model
    stamp = datetime.now(timezone.utc).isoformat()
    profile.research = {"version": SKILL_VERSION, "skill": "research-vehicle-specifications",
        "status": "searching", "scale": scale, "started_at": stamp,
        "searched_fields": list(dict.fromkeys(profile.research.get("searched_fields", []) + wanted)),
        "queries": [], "model_extraction": use_model}
    save_profile(profile, storage)
    official = CarResearchService.get_official_domain(make)
    known = KNOWN_SOURCES.get((_normal(make), _normal(model)))
    wiki = "https://en.wikipedia.org/wiki/" + quote(f"{make} {model}".replace(" ", "_"), safe="_")
    brand_home = KNOWN_BRAND_SOURCES.get(_normal(make))
    if not known:
        try:
            response = await client.get("https://en.wikipedia.org/w/api.php", params={"action":"opensearch",
                "search":f"{make} {model}","limit":3,"namespace":0,"format":"json"})
            response.raise_for_status()
            found = response.json()
            for title, url in zip(found[1], found[3]):
                if _matches_identity(title, make, model) and url.startswith("https://en.wikipedia.org/wiki/"):
                    wiki = url
                    break
        except (httpx.HTTPError, ValueError, IndexError, TypeError):
            pass
    tried = set()
    source_limit = max(2, min(settings.vehicle_research_source_limit, 30))

    async def collect_url(url):
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            final_url, document = await fetch_document(client, url, make)
            title, text, ambiguous = document_text(document)
            matched = _matches_identity(title, make, model)
            # A manufacturer home page is a discovery source only. It may expose
            # navigation or model links, but its generic content cannot establish
            # a vehicle measurement without an exact model identity.
            brand_home_only = bool(brand_home and final_url.rstrip("/") == brand_home.rstrip("/"))
            interval = re.search(r"(?:Production|Model years)\s*:\s*((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})", text, re.I)
            start, end = (int(interval[1]), int(interval[2])) if interval else (None, None)
            if known and url == known[0]:
                start, end = known[1:]
            if start is None and year is not None and re.search(rf"\b{year}\b", title):
                start = end = year
            match = "generation" if matched and start is not None and (year is None or start <= year <= end) else "unconfirmed"
            if start is not None and year is not None and not start <= year <= end:
                match = "mismatch"
            host = urlparse(final_url).hostname or ""
            kind = "manufacturer" if official and (host == official or host.endswith("." + official)) else "database"
            measurements = [] if ambiguous or not matched or brand_home_only else parse_measurements(text, source_url=final_url,
                source_kind=kind, source_status="fetched", vehicle_match=match,
                year_start=start, year_end=end, confidence=.95 if kind == "manufacturer" else .8)
            extraction_error = None
            if (use_model and not ambiguous and not brand_home_only and (matched or _matches_identity(text[:6000], make, model))
                    and len({m.name for m in measurements}) < len(wanted)):
                try:
                    extracted = await extract_document(text, title, make, model, year, final_url, kind, state)
                    measurements.extend(extracted.measurements)
                    if extracted.vehicle_match in ("exact", "generation"):
                        match = extracted.vehicle_match
                        # Derivations remain deterministic, using document-backed model-year evidence.
                        measurements.extend(parse_measurements(text, source_url=final_url, source_kind=kind,
                            source_status="fetched", vehicle_match=match, year_start=extracted.year_start,
                            year_end=extracted.year_end, confidence=.95 if kind == "manufacturer" else .8))
                except Exception as exc:
                    from .assembly_v3.jobs import JobStopped, BudgetExceeded
                    if isinstance(exc, (JobStopped, BudgetExceeded)):
                        raise
                    from .reference_images import failure_details
                    extraction_error = failure_details(exc, "vehicle_research", "text")["message"]
            unique = {m.model_dump_json(): m for m in measurements}
            measurements = list(unique.values())
            record = {"url": final_url, "requested_url": url, "title": title, "status": "fetched", "retrieved_at": stamp,
                      "sha256": hashlib.sha256(document.encode()).hexdigest(), "measurement_count": len(measurements),
                      "vehicle_match": match, "note": "Multiple vehicle infoboxes; measurements require variant selection" if ambiguous else ""}
            if extraction_error:
                record["extraction_error"] = extraction_error
            if not ambiguous and match not in ("exact", "generation"):
                record["note"] = "Vehicle identity or model-year scope could not be established"
            profile.measurements = [m for m in profile.measurements if m.source_status != "fetched" or m.source_url not in (url, final_url)] + measurements
        except (httpx.HTTPError, ValueError, LxmlError, ImportError) as exc:
            record = {"url": url, "status": "unavailable", "retrieved_at": stamp, "error": str(exc)[:350]}
        profile.sources = [s for s in profile.sources if s.get("requested_url", s.get("url")) != url] + [record]
        save_profile(profile, storage)

    # Search first, then read the discovered documents and established entry pages.
    for round_index in range(2):
        current = profile.resolved(scale)
        missing = [name for name in wanted if not current["measurements"].get(name, {}).get("grounded")]
        if (not missing and round_index) or len(tried) >= source_limit:
            break
        queries = research_queries(make, model, year, missing or wanted, official)
        if round_index:
            queries = [q | {"query": (q["query"].replace(f" {year} ", " ") if year is not None else q["query"]) + " filetype:pdf OR technical drawing"} for q in queries]
        reports = await asyncio.gather(*(search_web(client, query) for query in queries))
        profile.research["queries"].extend(reports)
        discovered = [r for report in reports for r in report["results"] if _allowed(r["url"], make)
                      and (_matches_identity(r["title"], make, model)
                           or _normal(model) in _normal(urlparse(r["url"]).path))]
        # Prioritize documents about the target model over generic brand homepages.
        discovered.sort(key=lambda r: (not _matches_identity(r["title"], make, model),
            not bool(official and (urlparse(r["url"]).hostname or "").endswith("." + official))))
        seeds = [*(source_urls or []), *([known[0]] if known else []), *([brand_home] if brand_home else []), wiki] if not round_index else []
        urls = list(dict.fromkeys(seeds + [r["url"] for r in discovered]))
        round_limit = max(2, source_limit - 4) if not round_index else source_limit
        for url in urls:
            if url in tried:
                continue
            if len(tried) >= round_limit:
                break
            tried.add(url)
            await collect_url(url)
        save_profile(profile, storage)
    result = profile.resolved(scale)
    searched = any(q["status"] == "searched" for q in profile.research["queries"])
    profile.research.update(status="completed" if searched else "unavailable", finished_at=datetime.now(timezone.utc).isoformat(),
        missing_fields=[name for name in wanted if not result["measurements"].get(name, {}).get("grounded")],
        documents_read=sum(s.get("status") == "fetched" for s in profile.sources))
    save_profile(profile, storage)
    return profile
