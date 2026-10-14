"""Refresh the bundled brand catalog and logos without runtime web requests.

Run from backend: python -m tasks.sync_vehicle_brands
Source names are pinned; translations are reviewed in data/vehicle-brand-*.tsv.
"""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import date
import hashlib
import io
import json
from pathlib import Path
import re
import time
from urllib.parse import urljoin
from xml.etree import ElementTree

import httpx
from bs4 import BeautifulSoup
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
REVISION = "bb2d661f28ce617dba8a51bdfc2069a3381a23b0"
REPOSITORY = "https://github.com/filippofilip95/car-logos-dataset"
# Vehicle families and performance divisions belong to their parent makes.
EXCLUDED = {
    "audi-sport", "bmw-m", "chevrolet-corvette", "dodge-viper", "ford-mustang",
    "nissan-gt-r", "nissan-nismo", "toyota-alphard", "toyota-century", "toyota-crown",
    "brammo", "jawa",  # Motorcycle manufacturers.
}
POPULAR = [
    "ferrari", "porsche", "mclaren", "lamborghini", "bmw", "mercedes-benz",
    "audi", "toyota", "honda", "nissan", "volkswagen", "ford", "tesla", "byd",
    "xiaomi", "geely", "nio", "xpeng", "li-auto", "zeekr", "aito", "avatr",
    "chevrolet", "aston-martin",
]


def rows(name):
    return [line.split("\t") for line in (ROOT / "data" / name).read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


def fetch(client, url):
    for attempt in range(3):
        try:
            response = client.get(url)
            response.raise_for_status()
            return response
        except (httpx.HTTPError, OSError):
            if attempt == 2:
                raise
            time.sleep(attempt + 1)


def validated_svg(data):
    root = ElementTree.fromstring(data)
    if root.tag.rsplit("}", 1)[-1] != "svg":
        raise ValueError("Not an SVG logo")
    for node in root.iter():
        if node.tag.rsplit("}", 1)[-1] in {"script", "foreignObject", "image", "use"}:
            raise ValueError("Active or externally referenced SVG content")
        if any(key.lower().startswith("on") or key.rsplit("}", 1)[-1] == "href" for key in node.attrib):
            raise ValueError("Active SVG attributes")
    return data


def sync(revision=REVISION):
    translations = {r[0]: r[1:] for r in rows("vehicle-brand-names.tsv")}
    output = ROOT / "frontend" / "public" / "brands"
    output.mkdir(parents=True, exist_ok=True)
    with httpx.Client(timeout=45, follow_redirects=True, headers={"User-Agent": "Car2LEGO-brand-catalog/1.0"}) as client:
        source = f"https://raw.githubusercontent.com/filippofilip95/car-logos-dataset/{revision}/logos/data.json"
        brands = []
        for item in fetch(client, source).json():
            slug = item["slug"]
            if slug in EXCLUDED:
                continue
            localized = translations[slug]  # Fail instead of silently losing Chinese names.
            source_url = item["image"]["source"]
            if not source_url.startswith(("https://", "http://")):
                source_url = f"{REPOSITORY}/blob/{revision}/local-logos/{slug}.png"
            brands.append(dict(id=slug, name="MINI" if slug == "mini" else item["name"], name_zh=localized[0],
                               aliases=localized[1].split("|") if len(localized) > 1 else [],
                               source_url=source_url,
                               download_url=item["image"]["thumb"].replace("/master/", f"/{revision}/")))
        for row in rows("vehicle-brand-extras.tsv"):
            slug, name, chinese, page = row[:4]
            asset = row[4] if len(row) > 4 else ""
            if asset and not asset.startswith("svg:"):
                brands.append(dict(id=slug, name=name, name_zh=chinese, aliases=[], source_url=page,
                                   download_url=asset))
                continue
            soup = BeautifulSoup(fetch(client, page).text, "html.parser")
            if asset.startswith("svg:"):
                svg = soup.select_one(asset.removeprefix("svg:"))
                if svg is None:
                    raise ValueError(f"No logo matching {asset} on {page}")
                # HTML parsers lowercase SVG names; restore the SVG XML spelling.
                svg["viewBox"] = svg.attrs.pop("viewbox")
                for node in svg.select("clippath"):
                    node.name = "clipPath"
                brands.append(dict(id=slug, name=name, name_zh=chinese, aliases=[], source_url=page,
                                   download_url=page, svg_data=validated_svg(str(svg).encode("utf-8"))))
                continue
            page_slug = page.rsplit("/", 1)[-1].removesuffix("-logo.html")
            image = next((i for i in soup.select("img[src]")
                          if re.search(rf"/{re.escape(page_slug)}-logo(?:-\d[^/]*)?\.png$", i["src"])), None)
            if image is None:
                raise ValueError(f"No matching logo on {page}")
            brands.append(dict(id=slug, name=name, name_zh=chinese, aliases=[], source_url=page,
                               download_url=urljoin(page, image["src"])))

        def download(brand):
            is_svg = "svg_data" in brand or brand["download_url"].endswith(".svg")
            path = output / f"{brand['id']}.{'svg' if is_svg else 'png'}"
            if not path.is_file():
                data = brand.get("svg_data") or fetch(client, brand["download_url"]).content
                temporary = path.with_suffix(".tmp")
                if is_svg:
                    temporary.write_bytes(validated_svg(data))
                else:
                    with Image.open(io.BytesIO(data)) as image:
                        image = image.convert("RGBA")
                        image.thumbnail((160, 100), Image.Resampling.LANCZOS)
                        image.save(temporary, format="PNG", optimize=True)
                temporary.replace(path)
            if is_svg:
                validated_svg(path.read_bytes())
            else:
                with Image.open(path) as image:
                    image.verify()
            return {k: v for k, v in brand.items() if k not in {"download_url", "svg_data"}} | {
                "logo_source_url": brand["download_url"],
                "logo": f"/brands/{path.name}", "logo_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                "popular_rank": POPULAR.index(brand["id"]) if brand["id"] in POPULAR else None,
            }

        with ThreadPoolExecutor(max_workers=8) as executor:
            complete = list(executor.map(download, brands))
    complete.sort(key=lambda b: b["name"].casefold())
    if len({b["id"] for b in complete}) != len(complete):
        raise ValueError("Duplicate brand IDs")
    catalog = dict(version=1, updated_at=date.today().isoformat(), source_revision=revision,
                   sources=[REPOSITORY, "https://www.carlogos.org/"], brands=complete)
    target = ROOT / "frontend" / "lib" / "data" / "vehicle-brands.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(".tmp")
    temporary.write_text(json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    print(f"Saved {len(complete)} brands and verified local logos to {target}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--revision", default=REVISION, help="Dataset commit or branch; default is a pinned commit")
    sync(parser.parse_args().revision)
