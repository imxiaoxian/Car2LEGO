"""Fetch public vehicle documents; extract explicitly labelled physical data only."""

import hashlib
import re
from datetime import datetime, timezone
from urllib.parse import quote, urljoin, urlparse

import httpx
from lxml import html
from lxml.etree import LxmlError

from .car_research import CarResearchService
from .vehicle_physics import PhysicalMeasurement, VehiclePhysicalProfile, FIELDS, load_profile, save_profile


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
    parsed = urlparse(url)
    hosts = ["en.wikipedia.org", *CarResearchService.REVIEW_SITES]
    official = CarResearchService.get_official_domain(make)
    if official:
        hosts.append(official)
    host = (parsed.hostname or "").lower()
    return bool(parsed.scheme == "https" and not parsed.username and not parsed.password
                and parsed.port in (None, 443) and any(host == h or host.endswith("." + h) for h in hosts))


async def fetch_document(client: httpx.AsyncClient, url: str, make: str) -> tuple[str, str]:
    for _ in range(5):
        if not _allowed(url, make):
            raise ValueError("Source URL must use an approved public manufacturer or automotive reference domain")
        async with client.stream("GET", url) as response:
            if response.is_redirect:
                url = urljoin(url, response.headers["location"])
                continue
            response.raise_for_status()
            if not any(t in response.headers.get("content-type", "") for t in ("text/html", "text/plain", "application/xhtml")):
                raise ValueError("Source is not an HTML/text document; supply explicit measurements for drawings/PDFs")
            data = bytearray()
            async for chunk in response.aiter_bytes():
                data.extend(chunk)
                if len(data) > 2_000_000:
                    raise ValueError("Source document exceeds 2 MB")
            return url, data.decode(response.encoding or "utf-8", errors="replace")
    raise ValueError("Too many document redirects")


async def collect_physical_profile(make: str, model: str, year: int, *, storage=None,
                                   source_urls: list[str] | None = None,
                                   client: httpx.AsyncClient | None = None) -> VehiclePhysicalProfile:
    if client is None:
        async with httpx.AsyncClient(timeout=httpx.Timeout(12, connect=5), headers={"User-Agent": "Car2LEGO/3.0 vehicle-specification-research"}, follow_redirects=False) as session:
            return await collect_physical_profile(make, model, year, storage=storage, source_urls=source_urls, client=session)
    profile = load_profile(make, model, year, storage)
    known = KNOWN_SOURCES.get((_normal(make), _normal(model)))
    wiki = "https://en.wikipedia.org/wiki/" + quote(f"{make} {model}".replace(" ", "_"), safe="_")
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
    urls = list(dict.fromkeys([*(source_urls or []), *([known[0]] if known else []), wiki]))[:8]
    for url in urls:
        stamp = datetime.now(timezone.utc).isoformat()
        try:
            final_url, document = await fetch_document(client, url, make)
            title, text, ambiguous = document_text(document)
            matched = _matches_identity(title, make, model)
            interval = re.search(r"(?:Production|Model years)\s*:\s*((?:19|20)\d{2})\s*[-–—]\s*((?:19|20)\d{2})", text, re.I)
            start, end = (int(interval[1]), int(interval[2])) if interval else (None, None)
            if known and url == known[0]:
                start, end = known[1:]
            if start is None and re.search(rf"\b{year}\b", title):
                start = end = year
            match = "generation" if matched and start is not None and start <= year <= end else "unconfirmed"
            if start is not None and not start <= year <= end:
                match = "mismatch"
            official = CarResearchService.get_official_domain(make)
            host = urlparse(final_url).hostname or ""
            kind = "manufacturer" if official and (host == official or host.endswith("." + official)) else "database"
            measurements = [] if ambiguous or not matched else parse_measurements(text, source_url=final_url,
                source_kind=kind, source_status="fetched", vehicle_match=match,
                year_start=start, year_end=end, confidence=.95 if kind == "manufacturer" else .8)
            record = {"url": final_url, "requested_url": url, "title": title, "status": "fetched", "retrieved_at": stamp,
                      "sha256": hashlib.sha256(document.encode()).hexdigest(), "measurement_count": len(measurements),
                      "vehicle_match": match, "note": "Multiple vehicle infoboxes; measurements require variant selection" if ambiguous else ""}
            if not ambiguous and match not in ("exact", "generation"):
                record["note"] = "Vehicle identity or model-year scope could not be established"
            profile.measurements = [m for m in profile.measurements if m.source_status != "fetched" or m.source_url not in (url, final_url)] + measurements
        except (httpx.HTTPError, ValueError, LxmlError) as exc:
            record = {"url": url, "status": "unavailable", "retrieved_at": stamp, "error": str(exc)[:350]}
        profile.sources = [s for s in profile.sources if s.get("requested_url", s.get("url")) != url] + [record]
    save_profile(profile, storage)
    return profile
