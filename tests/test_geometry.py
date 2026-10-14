import numpy as np
import pytest
import torch
import trimesh
from PIL import Image

from car2lego3d.lego import Plate, convert, export, pack, validate, voxelize
from car2lego3d.reconstruction import marching_cubes, preprocess, upstream_model


def test_anisotropic_voxel_scale():
    mesh = trimesh.creation.box(extents=[24, 8, 9.6])
    cells, info = voxelize(mesh, length_studs=4, color=4)
    assert info["grid_shape"] == [4, 2, 4]
    assert info["cell_mm"] == [8, 8, 3.2]
    assert validate(pack(cells), cells)["coverage_exact"]


def test_pack_preserves_every_color_and_cell():
    cells = {(x, y, z): (4 if x < 3 else 0) for x in range(6) for y in range(4) for z in range(3)
             if (x, y, z) != (1, 1, 2)}
    plates = pack(cells)
    occupied = {p: plate.color for plate in plates for p in plate.cells()}
    assert occupied == cells
    assert validate(plates, cells)["coverage_exact"]


def test_contact_graph_requires_vertical_stud_connection():
    plates = [Plate("3024", 4, 0, 0, 0, 1, 1), Plate("3024", 4, 1, 0, 0, 1, 1)]
    cells = {p: plate.color for plate in plates for p in plate.cells()}
    assert validate(plates, cells)["stud_connected_components"] == 2
    bridge = Plate("3023", 4, 0, 0, 1, 2, 1)
    plates.append(bridge)
    cells.update({p: bridge.color for p in bridge.cells()})
    report = validate(plates, cells)
    assert report["stud_connected_components"] == 1
    assert report["unsupported_above_ground"] == []


def test_invalid_overlap_is_reported():
    plates = [Plate("3024", 4, 0, 0, 0, 1, 1)] * 2
    result = validate(plates, {(0, 0, 0): 4})
    assert not result["coverage_exact"]
    assert result["overlapping_voxels"] == 1


def test_ldraw_coordinates_rotation_and_layer_steps(tmp_path):
    plates = [Plate("3023", 4, 0, 0, 0, 1, 2, True), Plate("3024", 0, 0, 0, 1, 1, 1)]
    export(plates, tmp_path, [1, 2, 2])
    lines = (tmp_path / "model.ldr").read_text().splitlines()
    parts = [line.split() for line in lines if line.startswith("1 ")]
    assert all(len(tokens) == 15 for tokens in parts)
    assert list(map(float, parts[0][2:5])) == [0, -8, 0]
    assert list(map(float, parts[0][5:14])) == [0, 0, 1, 0, 1, 0, -1, 0, 0]
    assert list(map(float, parts[1][2:5])) == [0, -16, -10]
    assert lines.count("0 STEP") == 2
    proxy = trimesh.load(tmp_path / "lego.glb", force="mesh")
    assert proxy.bounds[:, 2].tolist() == pytest.approx([0, 6.4])


def test_marching_cubes_adapter_preserves_upstream_axis_order():
    shape = (12, 20, 28)
    volume = torch.ones(shape)
    volume[2:7, 3:15, 4:23] = -1
    vertices, faces = marching_cubes(volume, 0)
    # TripoSR performs this reversal after calling the torchmcubes interface.
    xyz = vertices[:, [2, 1, 0]].numpy()
    assert xyz.min(axis=0).tolist() == [1.5, 2.5, 3.5]
    assert xyz.max(axis=0).tolist() == [6.5, 14.5, 22.5]
    assert faces.shape[1] == 3


def test_transparent_foreground_is_cropped_inclusively(tmp_path):
    array = np.zeros((10, 20, 4), dtype=np.uint8)
    array[2:8, 4:16] = [255, 0, 0, 255]
    source = tmp_path / "source.png"
    Image.fromarray(array).save(source)
    prepared = preprocess(source, tmp_path)
    assert prepared.width == prepared.height
    assert np.asarray(prepared)[prepared.height // 2, prepared.width // 2].tolist() == [255, 0, 0]


def test_upstream_imports_without_native_torchmcubes():
    assert upstream_model().__name__ == "TSR"


def test_colored_glb_to_complete_deliverable(tmp_path):
    import json
    box = trimesh.creation.box(extents=[24, 8, 9.6])
    box.visual.vertex_colors = [201, 26, 9, 255]
    source = tmp_path / "input.glb"
    box.export(source)
    output = tmp_path / "result"
    convert(source, output, length_studs=4)
    report = json.loads((output / "validation.json").read_text())
    assert report["coverage_exact"]
    assert report["buildability"] == "unverified"
    assert (output / "model.ldr").is_file()
    assert (output / "lego-preview.png").stat().st_size > 1000
    assert all(p["color"] == 4 for p in json.loads((output / "assembly.json").read_text())["plates"])


def test_diagonal_car_keeps_its_long_axis_scale():
    mesh = trimesh.creation.box(extents=[24, 8, 9.6])
    mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 4, [0, 0, 1]))
    _, info = voxelize(mesh, length_studs=4, color=4)
    assert info["grid_shape"] == [4, 2, 4]
