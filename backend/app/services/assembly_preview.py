"""Render the exported placements from real LDraw geometry, not generated pictures."""

from functools import lru_cache
from pathlib import Path

import numpy as np
from PIL import Image

from app.services.assembly_geometry import expanded_placements
from app.services.io_validator import STUDIO_LDRAW_PARTS
from app.services.ldraw_service import LDrawService


@lru_cache(maxsize=512)
def part_triangles(name: str) -> np.ndarray:
    relative = Path(name.replace("\\", "/"))
    root = STUDIO_LDRAW_PARTS.parent
    candidates = [root / "parts" / relative, root / "p" / relative,
                  root / "UnOfficial" / "parts" / relative, root / "UnOfficial" / "p" / relative]
    path = next((p for p in candidates if p.is_file()), None)
    if path is None:
        raise ValueError(f"Missing LDraw preview geometry: {name}")
    faces = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] == "1" and len(tokens) >= 15:
            origin = np.array(tokens[2:5], dtype=float)
            matrix = np.array(tokens[5:14], dtype=float).reshape(3, 3)
            child = part_triangles(" ".join(tokens[14:]))
            if len(child):
                faces.append(child @ matrix.T + origin)
        elif tokens[0] in ("3", "4"):
            count = int(tokens[0])
            vertices = np.array(tokens[2:2 + count * 3], dtype=float).reshape(count, 3)
            faces.append(vertices[:3][None])
            if count == 4:
                faces.append(vertices[[0, 2, 3]][None])
    return np.concatenate(faces) if faces else np.empty((0, 3, 3))


def render_preview(parts: list[dict], output: Path, view: str = "front", size: tuple = (1600, 1000)) -> None:
    if not parts:
        return
    triangles, colors = [], []
    palette = {47: "#526e7f", 36: "#bf2328", 46: "#ec8820"}
    for placement in expanded_placements(parts):
        part = placement["part"]
        mesh = part_triangles(part["part_num"]) @ placement["matrix"].T + placement["origin"]
        color = palette.get(part["color_id"], LDrawService.get_color_hex(part["color_id"]))
        rgb = tuple(int(color[i:i + 2], 16) for i in (1, 3, 5))
        triangles.append(mesh)
        colors.append(np.tile(rgb, (len(mesh), 1)))
    mesh, rgb = np.concatenate(triangles), np.concatenate(colors)
    right = np.array([.85, 0., .53])
    up = np.array([.22, -.91, -.36])
    if view == "rear":
        right *= np.array([-1, 1, -1])
        up *= np.array([-1, 1, -1])
    elif view in ("left", "right"):
        right = np.array([0., 0., 1. if view == "left" else -1.])
        up = np.array([0., -1., 0.])
    elif view in ("top", "bottom"):
        right = np.array([1., 0., 0.])
        up = np.array([0., 0., -1. if view == "top" else 1.])
    depth = np.cross(right, up)
    projection = np.array([right, up, depth])
    projected = mesh @ projection.T
    low = projected[:, :, :2].min(axis=(0, 1))
    high = projected[:, :, :2].max(axis=(0, 1))
    scale = min((size[0] - size[0] * .1) / max(high[0] - low[0], 1), (size[1] - size[1] * .12) / max(high[1] - low[1], 1))
    points = (projected[:, :, :2] - (low + high) / 2) * scale
    points[:, :, 0] += size[0] / 2
    points[:, :, 1] = size[1] / 2 - points[:, :, 1]
    normal = np.cross(mesh[:, 1] - mesh[:, 0], mesh[:, 2] - mesh[:, 0])
    length = np.linalg.norm(normal, axis=1)
    normal /= np.maximum(length[:, None], 1e-9)
    light = np.abs(normal @ np.array([.3, -.8, .5]))
    rgb = np.clip(rgb * (.55 + .4 * light[:, None]), 0, 255).astype(np.uint8)
    image = rasterize_triangles(points, projected[:, :, 2], rgb, size)
    image.resize((round(size[0] * .75), round(size[1] * .75)), Image.Resampling.LANCZOS).save(output, "PNG")


def geometry_bounds(parts: list[dict]) -> list[dict]:
    bounds = []
    for placement in expanded_placements(parts):
        mesh = part_triangles(placement["part"]["part_num"]) @ placement["matrix"].T + placement["origin"]
        low, high = mesh.min(axis=(0, 1)), mesh.max(axis=(0, 1))
        bounds.append(dict(index=placement["index"], part_num=placement["part"]["part_num"],
                           x=[round(float(low[0]), 2), round(float(high[0]), 2)],
                           height=[round(float(-high[1]), 2), round(float(-low[1]), 2)],
                           z=[round(float(low[2]), 2), round(float(high[2]), 2)]))
    return bounds


def rasterize_triangles(points: np.ndarray, depths_by_vertex: np.ndarray, colors: np.ndarray, size: tuple) -> Image.Image:
    pixels = np.full((size[1], size[0], 3), (245, 245, 247), dtype=np.uint8)
    z_buffer = np.full((size[1], size[0]), np.inf)
    # Interpolate depth at each pixel; centroid sorting breaks overlapping LEGO faces.
    for index, triangle in enumerate(points):
        x0, y0 = triangle[0]
        x1, y1 = triangle[1]
        x2, y2 = triangle[2]
        denominator = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        if abs(denominator) < 1e-8:
            continue
        left, top = np.maximum(np.floor(triangle.min(axis=0)).astype(int), 0)
        right_edge, bottom = np.minimum(np.ceil(triangle.max(axis=0)).astype(int), (size[0] - 1, size[1] - 1))
        if right_edge < left or bottom < top:
            continue
        yy, xx = np.mgrid[top:bottom + 1, left:right_edge + 1]
        xx, yy = xx + .5, yy + .5
        a = ((y1 - y2) * (xx - x2) + (x2 - x1) * (yy - y2)) / denominator
        b = ((y2 - y0) * (xx - x2) + (x0 - x2) * (yy - y2)) / denominator
        c = 1 - a - b
        depths = a * depths_by_vertex[index, 0] + b * depths_by_vertex[index, 1] + c * depths_by_vertex[index, 2]
        window = z_buffer[top:bottom + 1, left:right_edge + 1]
        visible = (a >= -1e-7) & (b >= -1e-7) & (c >= -1e-7) & (depths < window)
        window[visible] = depths[visible]
        pixels[top:bottom + 1, left:right_edge + 1][visible] = colors[index]
    return Image.fromarray(pixels)
