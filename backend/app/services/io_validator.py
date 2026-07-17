"""Validate BrickLink Studio .io files against the official LDraw + Studio standard.

An .io file is a ZIP archive containing:
  - model.ldr     — Main LDraw model with 0 FILE sub-model structure
  - model2.ldr    — Self-contained model with all part geometry inlined
  - thumbnail.png — 256x256 preview image
  - .info         — JSON metadata (Author, Name, Description, Application, Version)

This validator checks:
  1. ZIP integrity and required entries
  2. LDraw format compliance (headers, part lines, color codes)
  3. Part number validity against the Studio LDraw library
  4. Studio metadata presence
  5. Structural soundness (non-zero parts, valid coordinates)

Usage:
    from app.services.io_validator import validate_io_file
    report = validate_io_file("path/to/model.io")
    if report.has_errors:
        for err in report.errors:
            print(f"ERROR: {err}")
"""

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

# Studio 2.0 LDraw library paths
STUDIO_LDRAW_PARTS = Path(r"D:\lego\Studio 2.0\ldraw\parts")
STUDIO_LDRAW_SUBPARTS = Path(r"D:\lego\Studio 2.0\ldraw\parts\s")
STUDIO_LDRAW_PRIMITIVES = Path(r"D:\lego\Studio 2.0\ldraw\p")
STUDIO_LDRAW_UNOFFICIAL = Path(r"D:\lego\Studio 2.0\ldraw\UnOfficial\parts")

# Standard LDraw color codes (subset — see full list at ldraw.org)
LDRAW_VALID_COLORS = {
    0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19,
    20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37,
    38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55,
    56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73,
    74, 75, 76, 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89, 90, 91,
    92, 93, 94, 95, 96, 97, 98, 99, 100, 101, 102, 103, 104, 105, 106, 107,
    108, 109, 110, 111, 112, 113, 114, 115, 116, 117, 118, 119, 120, 121,
    122, 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135,
    136, 137, 138, 139, 140, 141, 142, 143, 144, 145, 146, 147, 148, 149,
    150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 256, 272, 273,
    284, 288, 294, 300, 304, 313, 320, 321, 322, 323, 324, 326, 329, 334,
    335, 341, 342, 343, 351, 366, 373, 375, 378, 379, 383, 394, 398, 399,
    406, 449, 450, 462, 484, 490, 493, 494, 495, 496, 503, 504, 511, 512,
    513, 520, 521, 522, 537, 543, 549, 553, 556, 558, 570, 574, 575, 576,
    578, 580, 581, 583, 584, 590, 600, 601, 602, 604, 608, 611, 612, 613,
    614, 625, 626, 627, 628, 629, 634, 636, 637, 638, 639, 640, 663, 675,
    677, 680, 682, 687, 697, 698, 707, 709, 710, 711, 712, 714, 715, 717,
    718, 719, 722, 728, 731, 738, 746, 747, 748, 750, 757, 758, 759, 760,
    761, 762, 763, 775, 777, 780, 781, 782, 783, 784, 785, 786, 787, 788,
    789, 790, 791, 792, 793, 794, 795, 796, 798, 799, 800, 801, 802, 803,
    805, 806, 807, 808, 809, 810, 811, 812, 813, 814, 815, 816, 817, 818,
    819, 820, 821, 822, 823, 824, 825, 826, 827, 828, 829, 830, 831, 832,
    833, 834, 835, 836, 837, 838, 839, 840, 841, 842, 843, 844, 845, 846,
    847, 848, 849, 850, 851, 852, 853, 854, 855, 856, 857, 858, 859, 860,
    861, 862, 863, 864, 865, 866, 867, 868, 869, 870, 871, 872, 873, 874,
    875, 876, 877, 878, 879, 880, 881, 882, 883, 884, 885, 886, 887, 888,
    889, 890, 891, 892, 893, 894, 895, 896, 1000, 1001, 1002, 1003, 1004,
    1005, 1006, 1007, 1008, 1009, 1010, 1011, 1012, 1013, 1014, 1015, 1016,
    1017, 1018, 1019, 1020, 1021, 1022, 1023, 1024, 1025, 1026, 1027, 1028,
    1029, 1030, 1031, 1032, 1033, 1034, 1035, 1036, 1037, 1038, 1039, 1040,
    1041, 1042, 1043, 1044, 1045, 1046, 1047, 1048, 1049, 1050, 1051, 1052,
    1053, 1054, 1055, 1056, 1057, 1058, 1059, 1060, 1061, 1062, 1063, 1064,
    1065, 1066, 1067, 1068, 1069, 1070, 1071, 1072, 1073, 1074, 1075, 1076,
    1077, 1078, 1079, 1080, 2000, 2001, 2002, 2003, 2004, 2005, 2006, 2007,
    2008, 2009, 2010, 2011, 2012, 2013, 2014, 2015, 2016, 2017, 2018, 2019,
    2020, 2021, 2022, 2023, 2024, 2025, 2026, 2027, 2028, 2029, 2030, 2031,
    2032, 2033, 2034, 2035, 2036, 2037, 2038, 2039, 2040, 2041, 2042, 2043,
    2044, 2045, 2046, 2047, 2048, 2049, 2050, 2051, 2052, 2053, 2054, 2055,
    2056, 2057, 2058, 2059, 2060, 2061, 2062, 2063, 2064, 2065, 2066, 2067,
    2068, 2069, 2070, 2071, 2072, 2073, 2074, 2075, 2076, 2077, 2078, 2079,
    2080, 2081, 2082, 2083, 2084, 2085, 2086, 2087, 2088, 2089, 2090, 2091,
    2092, 2093, 2094, 2095, 2096, 2097, 2098, 2099,
}


# Car geometry validation — part sets for Speed Champions 1:38 cars
WHEEL_PART_NUMBERS = {
    "30382.dat", "30383.dat",  # Speed Champions wheel assemblies
    "56145.dat", "56146.dat",  # tires
    "41896.dat",  # hub
    "30162.dat",  # small wheel
}

SLOPE_PART_NUMBERS = {
    "3297.dat", "3298.dat", "4286.dat", "4287.dat",
    "30363.dat", "3040.dat", "3041.dat", "3043.dat",
    "3665.dat", "3039.dat", "15068.dat", "50950.dat",
    "60481.dat", "11477.dat", "6153.dat", "6167.dat",
}

TRANSPARENT_COLORS = {47, 71, 72, 73, 74, 75, 76, 77, 78, 79, 80, 81, 82}


@dataclass
class ValidationIssue:
    level: str  # "error" | "warning" | "info"
    category: str  # "zip" | "ldraw" | "parts" | "color" | "metadata" | "geometry"
    message: str
    detail: str = ""


@dataclass
class ValidationReport:
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return any(i.level == "error" for i in self.issues)

    @property
    def has_warnings(self) -> bool:
        return any(i.level == "warning" for i in self.issues)

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "error"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.level == "warning"]

    def add(self, level: str, category: str, message: str, detail: str = ""):
        self.issues.append(
            ValidationIssue(level=level, category=category, message=message, detail=detail)
        )

    def summary(self) -> str:
        errs = len(self.errors)
        warns = len(self.warnings)
        status = "FAIL" if errs else "PASS"
        return f"{status} ({errs} errors, {warns} warnings)"


def _part_exists_in_library(part_file: str) -> bool:
    """Check if a .dat part file exists in Studio's LDraw library.

    Handles:
    - Official parts (ldraw/parts/)
    - Unofficial parts (ldraw/UnOfficial/parts/)
    - Subparts (ldraw/parts/s/)
    - Primitives (ldraw/p/)
    - Composite parts (e.g., 4624c00.dat → checks base part 4624.dat)
    """
    part_file = part_file.lower()

    # Official parts
    if STUDIO_LDRAW_PARTS.exists() and (STUDIO_LDRAW_PARTS / part_file).exists():
        return True

    # Unofficial parts
    if STUDIO_LDRAW_UNOFFICIAL.exists() and (STUDIO_LDRAW_UNOFFICIAL / part_file).exists():
        return True

    # Subparts
    if STUDIO_LDRAW_SUBPARTS.exists() and (STUDIO_LDRAW_SUBPARTS / part_file).exists():
        return True

    # Primitives
    if STUDIO_LDRAW_PRIMITIVES.exists() and (STUDIO_LDRAW_PRIMITIVES / part_file).exists():
        return True

    # Composite parts (e.g., 4624c00.dat) — check base part (4624.dat)
    if part_file.endswith(".dat") and "c" in part_file:
        base = part_file.replace(".dat", "").split("c")[0] + ".dat"
        if base != part_file:
            if STUDIO_LDRAW_PARTS.exists() and (STUDIO_LDRAW_PARTS / base).exists():
                return True
            if STUDIO_LDRAW_UNOFFICIAL.exists() and (STUDIO_LDRAW_UNOFFICIAL / base).exists():
                return True

    return False


def _parse_ldr(content: str) -> dict:
    """Parse LDraw content and return structured data."""
    parts: list[dict] = []
    sub_models: list[str] = []
    step_count = 0
    has_file_header = False
    for line_num, line in enumerate(content.split("\n"), 1):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith("0 FILE "):
            has_file_header = True
            sub_models.append(stripped[7:].strip())
        elif stripped.startswith("0 NOFILE"):
            continue
        elif stripped.startswith("0 STEP"):
            step_count += 1
        elif stripped.startswith("1 "):
            tokens = stripped.split()
            if len(tokens) < 15:
                continue
            try:
                color = int(tokens[1])
                x, y, z = float(tokens[2]), float(tokens[3]), float(tokens[4])
                part_file = tokens[14]
                parts.append({
                    "line": line_num,
                    "color": color,
                    "x": x,
                    "y": y,
                    "z": z,
                    "part_file": part_file,
                    "rotation": tokens[5:14],
                })
            except (ValueError, IndexError):
                pass
    return {
        "parts": parts,
        "sub_models": sub_models,
        "step_count": step_count,
        "has_file_header": has_file_header,
    }


def validate_io_file(io_path: Path | str) -> ValidationReport:
    """Validate a .io file against Studio + LDraw standards.

    Returns a ValidationReport with errors and warnings.
    """
    report = ValidationReport()
    io_path = Path(io_path)

    if not io_path.exists():
        report.add("error", "zip", f"File not found: {io_path}")
        return report

    if not io_path.suffix == ".io":
        report.add("warning", "zip", f"File extension is '{io_path.suffix}', expected '.io'")

    try:
        with zipfile.ZipFile(io_path, "r") as zf:
            names = zf.namelist()

            required = {"model.ldr", "model2.ldr", ".info"}
            missing = required - set(names)
            if missing:
                for m in sorted(missing):
                    report.add("error", "zip", f"Missing required entry: {m}")

            has_thumbnail = "thumbnail.png" in names
            if not has_thumbnail:
                report.add("warning", "zip", "Missing thumbnail.png")

            if "model.ldr" in names:
                model_ldr_content = zf.read("model.ldr").decode("utf-8", errors="replace")
                _validate_ldr_content(model_ldr_content, "model.ldr", report)
                model_parsed = _parse_ldr(model_ldr_content)
                _validate_car_geometry(model_parsed["parts"], report, "model.ldr")

            if "model2.ldr" in names:
                _validate_ldr_content(
                    zf.read("model2.ldr").decode("utf-8", errors="replace"),
                    "model2.ldr",
                    report,
                )

            if ".info" in names:
                _validate_info(zf.read(".info").decode("utf-8", errors="replace"), report)

    except zipfile.BadZipFile:
        report.add("error", "zip", "Not a valid ZIP archive")
    except Exception as exc:
        report.add("error", "zip", f"Failed to read .io file: {exc}")

    return report


def _validate_ldr_content(content: str, filename: str, report: ValidationReport):
    """Validate LDraw content structure and part references."""
    parsed = _parse_ldr(content)

    if not parsed["has_file_header"]:
        report.add("warning", "ldraw", f"{filename}: Missing '0 FILE' header")

    if not parsed["parts"]:
        report.add("error", "ldraw", f"{filename}: No part lines found")
        return

    if len(parsed["parts"]) < 3:
        report.add(
            "warning", "ldraw",
            f"{filename}: Only {len(parsed['parts'])} parts — typical Speed Champions car has 200-350",
        )

    if parsed["step_count"] == 0:
        report.add("warning", "ldraw", f"{filename}: No '0 STEP' markers found")

    seen_parts = set()
    for p in parsed["parts"]:
        part_file = p["part_file"]

        if not part_file.endswith(".dat"):
            report.add(
                "error", "parts",
                f"{filename}:L{p['line']}: Part file '{part_file}' missing .dat extension",
            )
            continue

        if part_file not in seen_parts:
            if not _part_exists_in_library(part_file):
                report.add(
                    "error", "parts",
                    f"{filename}:L{p['line']}: Part '{part_file}' not found in Studio LDraw library",
                )
            seen_parts.add(part_file)

        if p["color"] not in LDRAW_VALID_COLORS:
            report.add(
                "error", "color",
                f"{filename}:L{p['line']}: Invalid LDraw color code {p['color']} for part '{part_file}'",
            )

        if not all(-10000 <= v <= 10000 for v in [p["x"], p["y"], p["z"]]):
            report.add(
                "warning", "ldraw",
                f"{filename}:L{p['line']}: Unusual coordinates ({p['x']}, {p['y']}, {p['z']}) for part '{part_file}'",
            )


def _validate_car_geometry(parts: list[dict], report: ValidationReport, filename: str):
    """Validate car-specific geometric properties (model.ldr only).

    Checks wheel count, slope/curved part presence, windshield transparency,
    body length/width ratio, and overall height range.
    """
    if not parts:
        return

    wheel_parts = [p for p in parts if p["part_file"] in WHEEL_PART_NUMBERS]
    if len(wheel_parts) < 4:
        report.add(
            "warning", "geometry",
            f"{filename}: Only {len(wheel_parts)} wheel parts found — "
            f"Speed Champions car needs >= 4 wheels",
        )

    slope_parts = [p for p in parts if p["part_file"] in SLOPE_PART_NUMBERS]
    if len(slope_parts) < 2:
        report.add(
            "info", "geometry",
            f"{filename}: Only {len(slope_parts)} slope/curved parts — "
            f"consider adding more for streamlined body shape",
        )

    windshield_parts = [
        p for p in parts
        if p["color"] in TRANSPARENT_COLORS and p["y"] >= 64
    ]
    if len(windshield_parts) == 0:
        report.add(
            "info", "geometry",
            f"{filename}: No transparent windshield parts found at roof level (Y >= 64)",
        )

    x_coords = [p["x"] for p in parts]
    z_coords = [p["z"] for p in parts]
    x_range = max(x_coords) - min(x_coords) if x_coords else 0
    z_range = max(z_coords) - min(z_coords) if z_coords else 0
    if x_range > 0 and z_range > 0:
        ratio = z_range / x_range
        if ratio < 1.5 or ratio > 3.0:
            report.add(
                "warning", "geometry",
                f"{filename}: Body length/width ratio = {ratio:.2f} — "
                f"Speed Champions cars typically have ratio 1.5-3.0",
            )

    y_coords = [p["y"] for p in parts]
    y_range = max(y_coords) - min(y_coords) if y_coords else 0
    if y_range < 80:
        report.add(
            "warning", "geometry",
            f"{filename}: Body height range = {y_range:.0f} LDU — "
            f"Speed Champions cars typically have 80-200 LDU height",
        )


def _validate_info(info_content: str, report: ValidationReport):
    """Validate Studio .info metadata."""
    try:
        info = json.loads(info_content)
    except json.JSONDecodeError as exc:
        report.add("error", "metadata", f".info is not valid JSON: {exc}")
        return

    required_fields = {"Author", "Name"}
    for field in required_fields:
        if field not in info:
            report.add("error", "metadata", f".info missing required field: '{field}'")
        elif not info[field]:
            report.add("warning", "metadata", f".info field '{field}' is empty")

    optional_fields = {"Description", "Application", "Version"}
    for field in optional_fields:
        if field not in info:
            report.add("info", "metadata", f".info missing optional field: '{field}'")
