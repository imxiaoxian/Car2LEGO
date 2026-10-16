import numpy as np
import pytest

from car2lego3d.carfit import Car
from car2lego3d.surfaces import SHELL_PARTS, fit_shell, place_shell


@pytest.mark.parametrize("width", [2, 4, 6, 8, 10])
@pytest.mark.parametrize("length", [1, 4, 7, 12])
def test_shell_covers_once_with_bilateral_modules_and_bounded_error(width, length):
    target = np.linspace(10, 12, length)
    plan = fit_shell(target, width)
    catalog = {(p, size, breadth): profile for p, size, breadth, profile, _ in SHELL_PARTS}
    rows = plan["bands"]
    assert rows == rows[::-1]
    covered = set()
    y = 0
    for breadth, pieces in rows:
        for part, index, size, _, origin, reverse in pieces:
            profile = catalog[part, size, breadth]
            actual = np.array(profile[::-1] if reverse else profile)+origin
            assert np.max(np.abs(actual-target[index:index+size])) <= 1.0
            cells = {(x, yy) for x in range(index, index+size) for yy in range(y, y+breadth)}
            assert not cells & covered
            covered |= cells
        y += breadth
    assert covered == {(x, y) for x in range(length) for y in range(width)}


def test_large_flat_panel_preserves_the_cabin_cavity():
    car = Car(dict(length_studs=16, width_studs=10))
    plan = place_shell(car, range(3, 9), range(2, 8), [21]*6, 0, "roof", 18, floor=19, flat_only=True)
    assert plan["part_count"] == 1
    assert car.parts[0].part == "6881b"
    assert all(z == 19 for _, _, z in car.cells)


@pytest.mark.parametrize("length,width", [(1, 2), (1, 4), (2, 4), (2, 6), (6, 2)])
def test_flat_tile_native_bounds_match_the_requested_rectangle(length, width):
    # Native LDraw bounds measured by native_audit_worker, in LDU.
    dimensions = {"3069b": (40, 20), "3068b": (40, 40), "2431": (80, 20),
                  "6636": (120, 20), "87079": (80, 40), "69729": (120, 40)}
    car = Car(dict(length_studs=16, width_studs=10))
    place_shell(car, range(3, 3+length), range(2, 2+width), [12]*length, 2, "shell", 14, flat_only=True)
    assert len(car.parts) == 1
    part = car.parts[0]
    x, z = dimensions[part.part]
    corners = np.array([[xx, 0, zz] for xx in (-x/2, x/2) for zz in (-z/2, z/2)])
    transformed = corners @ np.array(part.rotation).reshape(3, 3).T
    np.testing.assert_allclose(np.ptp(transformed, axis=0)[[0, 2]], [length*20, width*20])


@pytest.mark.parametrize("target,width", [([], 2), ([np.nan], 2), ([10], 3)])
def test_invalid_shell_is_rejected(target, width):
    with pytest.raises(ValueError):
        fit_shell(target, width)
