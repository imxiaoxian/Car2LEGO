"""Unit tests for io_validator — .io file + car geometry validation."""

import json
import zipfile
from pathlib import Path

import pytest

from app.services.io_validator import (
    SLOPE_PART_NUMBERS,
    TRANSPARENT_COLORS,
    WHEEL_PART_NUMBERS,
    ValidationReport,
    _parse_ldr,
    _validate_car_geometry,
    validate_io_file,
)


def _make_part(part_file="3020.dat", color=7, x=0, y=8, z=30):
    """Build a part dict matching _parse_ldr's output shape."""
    return {
        "line": 1,
        "color": color,
        "x": x,
        "y": y,
        "z": z,
        "part_file": part_file,
        "rotation": ["1", "0", "0", "0", "1", "0", "0", "0", "1"],
    }


class TestValidateCarGeometry:
    def test_valid_car_no_warnings(self):
        """A well-proportioned car with 4 wheels, slopes, windshield, good ratio."""
        parts = []
        # 4 wheels
        for x in [60, 60]:
            parts.append(_make_part("30382.dat", 0, x, 8, 60))
            parts.append(_make_part("30382.dat", 0, x, 8, 220))
        # 2 slope parts
        parts.append(_make_part("3298.dat", 4, 40, 40, 300))
        parts.append(_make_part("3297.dat", 4, 40, 40, 20))
        # Windshield (transparent, Y >= 64)
        parts.append(_make_part("3005.dat", 72, 20, 96, 200))
        # Body — X range 0-100, Z range 20-300 → ratio 280/100 = 2.8 (ok)
        parts.append(_make_part("3005.dat", 4, 0, 48, 150))
        parts.append(_make_part("3005.dat", 4, 100, 48, 20))
        parts.append(_make_part("3005.dat", 4, 100, 48, 300))
        # Height: Y range 8-96 = 88 (ok, >= 80)

        report = ValidationReport()
        _validate_car_geometry(parts, report, "model.ldr")
        # No geometry warnings
        geom_issues = [i for i in report.issues if i.category == "geometry"]
        warnings = [i for i in geom_issues if i.level == "warning"]
        assert len(warnings) == 0

    def test_missing_wheels_warning(self):
        """Fewer than 4 wheel parts → warning."""
        parts = [
            _make_part("30382.dat", 0, 60, 8, 60),
            _make_part("30382.dat", 0, 60, 8, 220),
            _make_part("3298.dat", 4, 40, 40, 300),
            _make_part("3297.dat", 4, 40, 40, 20),
            _make_part("3005.dat", 72, 20, 96, 200),
            _make_part("3005.dat", 4, 100, 48, 20),
            _make_part("3005.dat", 4, 100, 48, 300),
        ]
        report = ValidationReport()
        _validate_car_geometry(parts, report, "model.ldr")
        geom_warnings = [
            i for i in report.issues
            if i.category == "geometry" and i.level == "warning"
        ]
        assert any("wheel" in w.message.lower() for w in geom_warnings)

    def test_no_slope_parts_info(self):
        """No slope/curved parts → info."""
        parts = [
            _make_part("30382.dat", 0, 60, 8, 60),
            _make_part("30382.dat", 0, 60, 8, 220),
            _make_part("30382.dat", 0, 60, 8, 60),
            _make_part("30382.dat", 0, 60, 8, 220),
            _make_part("3005.dat", 72, 20, 96, 200),
            _make_part("3005.dat", 4, 100, 48, 20),
            _make_part("3005.dat", 4, 100, 48, 300),
        ]
        report = ValidationReport()
        _validate_car_geometry(parts, report, "model.ldr")
        geom_info = [
            i for i in report.issues
            if i.category == "geometry" and i.level == "info"
        ]
        assert any("slope" in i.message.lower() for i in geom_info)

    def test_no_windshield_info(self):
        """No transparent parts at roof level → info."""
        parts = [
            _make_part("30382.dat", 0, 60, 8, 60),
            _make_part("30382.dat", 0, 60, 8, 220),
            _make_part("30382.dat", 0, 60, 8, 60),
            _make_part("30382.dat", 0, 60, 8, 220),
            _make_part("3298.dat", 4, 40, 40, 300),
            _make_part("3297.dat", 4, 40, 40, 20),
            # No transparent parts at Y >= 64
            _make_part("3005.dat", 4, 100, 48, 20),
            _make_part("3005.dat", 4, 100, 48, 300),
        ]
        report = ValidationReport()
        _validate_car_geometry(parts, report, "model.ldr")
        geom_info = [
            i for i in report.issues
            if i.category == "geometry" and i.level == "info"
        ]
        assert any("windshield" in i.message.lower() for i in geom_info)

    def test_bad_ratio_warning(self):
        """Length/width ratio outside 1.5-3.0 → warning."""
        parts = []
        for z in [60, 220]:
            parts.append(_make_part("30382.dat", 0, 60, 8, z))
            parts.append(_make_part("30382.dat", 0, 60, 8, z))
        parts.append(_make_part("3298.dat", 4, 40, 40, 300))
        parts.append(_make_part("3297.dat", 4, 40, 40, 20))
        parts.append(_make_part("3005.dat", 72, 20, 96, 200))
        # X range 0-100, Z range 20-30 → ratio 10/100 = 0.1 (too low)
        parts.append(_make_part("3005.dat", 4, 100, 48, 20))
        parts.append(_make_part("3005.dat", 4, 100, 48, 30))
        report = ValidationReport()
        _validate_car_geometry(parts, report, "model.ldr")
        geom_warnings = [
            i for i in report.issues
            if i.category == "geometry" and i.level == "warning"
        ]
        assert any("ratio" in w.message.lower() for w in geom_warnings)

    def test_too_short_warning(self):
        """Height range < 80 LDU → warning."""
        parts = []
        for z in [60, 220]:
            parts.append(_make_part("30382.dat", 0, 60, 8, z))
            parts.append(_make_part("30382.dat", 0, 60, 8, z))
        parts.append(_make_part("3298.dat", 4, 40, 40, 300))
        parts.append(_make_part("3297.dat", 4, 40, 40, 20))
        parts.append(_make_part("3005.dat", 72, 20, 40, 200))
        # Y range 8-40 = 32 (too short)
        parts.append(_make_part("3005.dat", 4, 100, 40, 20))
        parts.append(_make_part("3005.dat", 4, 100, 40, 300))
        report = ValidationReport()
        _validate_car_geometry(parts, report, "model.ldr")
        geom_warnings = [
            i for i in report.issues
            if i.category == "geometry" and i.level == "warning"
        ]
        assert any("height" in w.message.lower() for w in geom_warnings)

    def test_empty_parts_no_crash(self):
        """Empty parts list should not crash."""
        report = ValidationReport()
        _validate_car_geometry([], report, "model.ldr")
        assert len(report.issues) == 0


class TestValidateIoFileEndToEnd:
    @pytest.mark.skipif(
        not Path(r"D:\lego\Studio 2.0\ldraw\parts").exists(),
        reason="Studio LDraw parts library not installed (CI environment)",
    )
    def test_valid_io_file_passes(self, tmp_path):
        """Create a minimal valid .io file and verify validation passes."""
        ldr = """0 FILE model.ldr
0 Name: Test Car
0 Author: Test
0 STEP
1 7 0 8 60 1 0 0 0 1 0 0 0 1 3020.dat
1 0 60 8 60 1 0 0 0 1 0 0 0 1 30382.dat
1 0 60 8 220 1 0 0 0 1 0 0 0 1 30382.dat
1 0 60 8 60 1 0 0 0 1 0 0 0 1 30382.dat
1 0 60 8 220 1 0 0 0 1 0 0 0 1 30382.dat
1 4 40 40 300 1 0 0 0 1 0 0 0 1 3298.dat
1 4 40 40 20 1 0 0 0 1 0 0 0 1 3297.dat
1 72 20 96 200 1 0 0 0 1 0 0 0 1 3005.dat
1 4 100 48 20 1 0 0 0 1 0 0 0 1 3005.dat
1 4 100 48 300 1 0 0 0 1 0 0 0 1 3005.dat
0
"""
        info = json.dumps({
            "Author": "Test",
            "Name": "Test Car",
            "Description": "Test",
            "Application": "Studio 2.0",
            "Version": 1,
        })

        io_path = tmp_path / "test.io"
        with zipfile.ZipFile(io_path, "w") as zf:
            zf.writestr("model.ldr", ldr)
            zf.writestr("model2.ldr", ldr)
            zf.writestr(".info", info)

        report = validate_io_file(io_path)
        # Should not have errors (geometry warnings are ok)
        errors = [i for i in report.issues if i.level == "error"]
        assert len(errors) == 0

    def test_nonexistent_file_error(self):
        """Nonexistent file → error."""
        report = validate_io_file("nonexistent.io")
        assert report.has_errors
