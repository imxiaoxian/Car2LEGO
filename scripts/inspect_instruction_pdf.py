"""Render selected official instruction pages for human structural review."""
import argparse
from pathlib import Path

import fitz
from PIL import Image, ImageDraw

parser = argparse.ArgumentParser()
parser.add_argument("pdf", type=Path)
parser.add_argument("--pages", type=int, nargs="*")
args = parser.parse_args()
document = fitz.open(args.pdf)
pages = args.pages or list(range(1, len(document)+1, max(1, len(document)//15)))
sheet = Image.new("RGB", (1200, ((len(pages)+3)//4)*260), "white")
draw = ImageDraw.Draw(sheet)
for index, page in enumerate(pages):
    pixmap = document[page-1].get_pixmap(matrix=fitz.Matrix(.65, .65), alpha=False)
    image = Image.frombytes("RGB", (pixmap.width, pixmap.height), pixmap.samples)
    image.thumbnail((295, 235))
    x, y = (index % 4)*300, (index//4)*260
    sheet.paste(image, (x, y+22))
    draw.text((x+6, y+4), f"PDF page {page}", fill="black")
target = args.pdf.with_name(args.pdf.stem + "-pages-" + "-".join(map(str,pages)) + ".jpg")
sheet.save(target)
print(f"{len(document)} pages: {target}")
