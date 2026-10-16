import importlib.util
from types import SimpleNamespace

import numpy as np
import pytest

from car2lego3d.carfit import Car
from car2lego3d.common import ROOT
from car2lego3d.glazing import side_window_plan, place_side_windows, place_split_headlamps, place_tail_light_bar


@pytest.mark.parametrize("count", range(2, 18))
@pytest.mark.parametrize("four_doors", [True, False])
def test_window_partition_has_no_gaps_overlap_or_out_of_bounds_panes(count, four_doors):
    plan = side_window_plan(10, 10+count-1, four_doors)
    occupied = [x for item in plan for x in range(item["start"], item["start"]+item["span"])]
    assert occupied == list(range(10, 10+count))
    assert all(item["span"] == 2 for item in plan if item["kind"] != "pillar")
    if count >= 7:
        assert plan[-1] == dict(kind="quarter", start=10+count-2, span=2)


def test_quarter_window_and_surround_share_a_native_connection_plane():
    car = Car(dict(length_studs=27, width_studs=10))
    place_side_windows(car, 11, 19, [2, 7], 20, 14, four_doors=True)
    quarter = [p for p in car.parts if p.module == "rear quarter glazing"]
    slopes = [p for p in car.parts if p.module == "raked window surround"]
    assert len(quarter) == len(slopes) == 2
    for q, slope in zip(quarter, slopes):
        assert q.position[1]+24 == pytest.approx(-14*8)  # panel bottom on sill
        # Slope underside and pane upper edge meet at glass_top - 3 plates.
        assert slope.position[1]+24 == q.position[1]
    assert car.fit["glazing_layout"]["part_scaling"] is False


@pytest.mark.parametrize("width", [8, 10, 12])
def test_split_lamps_use_real_mount_socket_positions_and_rigid_transforms(width):
    car = Car(dict(length_studs=27, width_studs=width, styling_prior="lotus-for-me"))
    place_split_headlamps(car, 10, width)
    lenses = [p for p in car.parts if p.module == "recessed main headlamps"]
    mounts = [p for p in car.parts if p.module == "projector mounts"]
    assert len(lenses) == 2 and len(mounts) == 4
    for lens in lenses:
        for x in (-10,10):
            socket = np.array(lens.position)+np.array(lens.rotation).reshape(3, 3) @ (x, 8, 0)
            assert any(np.allclose(socket, np.array(mount.position)+np.array(mount.rotation).reshape(3, 3) @ (0, 10, -10))
                       for mount in mounts)
    assert len([p for p in car.parts if p.module == "slim split headlamps"]) == 2
    for p in car.parts:
        matrix = np.array(p.rotation).reshape(3, 3)
        np.testing.assert_allclose(matrix.T @ matrix, np.eye(3))
        assert np.linalg.det(matrix) == pytest.approx(1)


def test_split_lamp_identity_is_not_applied_to_every_suv():
    car = Car(dict(length_studs=27, width_studs=10))
    place_split_headlamps(car, 10, 10)
    assert not any(p.module == "recessed main headlamps" for p in car.parts)


@pytest.mark.parametrize("width", [8, 10, 12])
def test_tail_bar_covers_belt_with_edge_on_lenses_and_solid_backing(width):
    car = Car(dict(length_studs=27, width_studs=width, body_color=25))
    place_tail_light_bar(car, 12, width, 27)
    lenses = car.parts
    assert sum(4 if p.part == "2431" else 2 for p in lenses) == width-2
    for p in lenses:
        matrix = np.array(p.rotation).reshape(3, 3)
        # Plate depth, not stud width, is the visible height of the light bar.
        np.testing.assert_allclose(matrix @ (0, 8, 0), (0, 8, 0))
    assert all(car.cells[26, y, 11] == 0 for y in range(1, width-1))


def test_preview_palette_keeps_smoke_glass_and_red_tail_lights_distinct(tmp_path):
    spec = importlib.util.spec_from_file_location("bridge", ROOT / "scripts/frontend_bridge_worker.py")
    bridge = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(bridge)
    directory = tmp_path / "Studio 2.0/data"
    directory.mkdir(parents=True)
    (directory / "StudioColorDefinition.txt").write_text(
        "LDraw Color Code\tRGB value\tLDraw Color Name\n"
        "40\t#635F52\tTrans_Black\n36\t#C91A09\tTrans_Red\n47\t#FBFBFB\tTrans_Clear\n",
        encoding="utf-8-sig")
    palette = SimpleNamespace(COLOR_MAP={0: ("Black", "#1B2A34")})
    bridge.configure_render_palette(tmp_path, palette)
    assert palette.COLOR_MAP[40][1] == "#635F52"
    assert palette.COLOR_MAP[36][1] == "#C91A09"
    assert palette.COLOR_MAP[47][1] == "#FBFBFB"
    assert palette.COLOR_MAP[0][1] == "#1B2A34"
