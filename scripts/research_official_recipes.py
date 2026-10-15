"""Collect public LEGO instruction metadata; preserve official evidence locally."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from bs4 import BeautifulSoup
from car2lego3d.common import ROOT, digest, write_json

SETS = ("76934", "76909", "76922", "76924", "75885", "10242", "10295", "10290",
        "10279", "42110", "42141", "42115", "75828", "10317", "31108", "42128", "10258")


def collect(number):
    directory = ROOT / "runs/official-lego" / number
    directory.mkdir(parents=True, exist_ok=True)
    page = directory / "instructions.html"
    url = f"https://www.lego.com/en-gb/service/buildinginstructions/{number}"
    if not page.exists():
        subprocess.run(["curl", "--fail", "-sS", "-L", "--max-time", "60", "--retry", "2",
                        url, "-o", str(page)], check=True)
    soup = BeautifulSoup(page.read_text(encoding="utf-8"), "html.parser")
    data = json.loads(soup.select_one("script#__NEXT_DATA__").get_text())
    found = []

    def walk(value):
        if isinstance(value, dict):
            if value.get("__typename") == "CS_BuildingInstructionData" and value.get("setNumber") == number:
                found.append(value)
            for child in value.values():
                walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)
    walk(data)
    if not found:
        raise ValueError(f"Official instructions not found: {number}")
    links = sorted({a["href"] for a in soup.select("a[href]")
                    if a["href"].startswith("https://www.lego.com/cdn/product-assets/product.bi.core.pdf/")})
    result = {"set": number, "url": url, "retrieved_at": datetime.now(timezone.utc).isoformat(),
              "source_sha256": digest(page), "metadata": found[0], "instruction_pdfs": links,
              "verification": "official set metadata and PDF links retrieved; structural review pending"}
    write_json(directory / "source.json", result)
    print(f"{number}: {found[0]['name']} ({len(links)} instruction PDFs)", flush=True)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sets", nargs="*", default=SETS)
    parser.add_argument("--download", nargs="*", default=[])
    args = parser.parse_args()
    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(collect, args.sets))
    target = ROOT / "data/recipes/official-sources.json"
    existing = json.loads(target.read_text(encoding="utf-8"))["sets"] if target.exists() else {}
    existing.update({x["set"]: x for x in results})
    write_json(target, {"sets": existing})
    for result in results:
        if result["set"] in args.download:
            for url in result["instruction_pdfs"]:
                destination = ROOT / "runs/official-lego" / result["set"] / url.rsplit("/", 1)[1]
                if not destination.exists():
                    subprocess.run(["curl", "--fail", "-sS", "-L", "--max-time", "180", "--retry", "2",
                                    url, "-o", str(destination)], check=True)
                print(destination, flush=True)


if __name__ == "__main__":
    main()
