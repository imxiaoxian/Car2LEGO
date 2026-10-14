import json

import numpy as np
import pytest
import trimesh

from car2lego3d.carfit import convert_car, design, fit_mesh
from car2lego3d.studio import export_studio, verify_archive


def vehicle(roof_x=0.5, rgb=(201, 26, 9)):
    body = trimesh.creation.box((16, 6, 2))
    roof = trimesh.creation.box((3, 4, 2))
    roof.apply_translation((roof_x, 0, 2))
    mesh = trimesh.util.concatenate((body, roof))
    mesh.visual.vertex_colors = (*rgb, 255)
    return mesh


def test_fit_responds_to_geometry_and_paint_without_random_drift():
    first = fit_mesh(vehicle())
    shifted = fit_mesh(vehicle(3.5, (0, 85, 191)))
    assert shifted["roof_end_stud"] > first["roof_end_stud"]
    assert shifted["source_roof_interval_studs"] != first["source_roof_interval_studs"]
    assert first["body_color"] == 4 and shifted["body_color"] == 1
    assert fit_mesh(vehicle()) == first


def test_car_export_roundtrip_preserves_every_native_transform(tmp_path):
    mesh = tmp_path / "vehicle.glb"
    vehicle().export(mesh)
    source = convert_car(mesh, tmp_path / "lego")
    report = json.loads((source.parent / "validation.json").read_text())
    data = json.loads((source.parent / "assembly.json").read_text())["parts"]
    assert len(data) == report["part_count"]
    assert sum(p["part"] == "18977" for p in data) == 4
    assert sum(p["part"] == "65633" for p in data) == 1
    assert any(p["module"] == "recessed side intake" for p in data)
    assert not report["appearance_accepted"] and not report["physical_verified"]
    for part in data:
        rotation = np.array(part["rotation"]).reshape(3, 3)
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3))
        assert np.linalg.det(rotation) == pytest.approx(1)
    archive = export_studio(source, tmp_path / "studio")
    assert verify_archive(archive, source)["part_count"] == len(data)


def test_door_skin_sockets_align_with_native_side_studs():
    car = design(fit_mesh(vehicle()))
    skins = [p for p in car.parts if p.module == "door skin"]
    mounts = [p for p in car.parts if p.module == "door mounts"]
    for skin in skins:
        sockets = [np.array(skin.position) + np.array(skin.rotation).reshape(3, 3) @ np.array((x, 8, 0))
                   for x in (-30, 30)]
        for socket in sockets:
            assert any(np.allclose(socket, np.array(m.position) +
                       np.array(m.rotation).reshape(3, 3) @ np.array((0, 10, -10))) for m in mounts)


def test_fixed_part_family_rejects_too_small_scale_and_flat_mesh():
    with pytest.raises(ValueError, match="23..32"):
        fit_mesh(vehicle(), length=20)
    mesh = vehicle()
    mesh.vertices[:, 2] = 0
    with pytest.raises(ValueError, match="degenerate"):
        fit_mesh(mesh)
    assert not any("wing" in p.module for p in design(fit_mesh(vehicle()), rear_wing=False).parts)
