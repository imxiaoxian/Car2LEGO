import json
import base64
from types import SimpleNamespace

from PIL import Image

from app.config import settings
from app.services.assembly_v3.exports import ldraw
import app.services.assembly_v3.external_quality as external_quality
from app.services.assembly_v3.external_quality import _tool_paths, run_external_checks
from app.services.assembly_v3.recipes import build_f40
from tasks.ldraw_mcp_quality import _compare_bom, _detail_groups, _write_images


def test_independent_bom_requires_exact_parts_colors_and_library_coverage():
    scene = {"parts": [{"part_num": "3001.dat", "color_id": 4},
                       {"part_num": "3001.dat", "color_id": 0}]}
    valid = {"rows": [{"part": "3001.dat", "color_code": 4, "quantity": 1},
                      {"part": "3001.dat", "color_code": 0, "quantity": 1}],
             "total_parts": 2, "parts_not_in_library": [], "unknown_color_codes": []}
    assert _compare_bom(scene, valid)["status"] == "passed"

    missing_geometry = valid | {"parts_not_in_library": ["3001.dat"]}
    result = _compare_bom(scene, missing_geometry)
    assert result["quantities_and_colors_match"]
    assert result["status"] == "failed"

    wrong_color = valid | {"rows": [{"part": "3001.dat", "color_code": 4, "quantity": 2}]}
    assert _compare_bom(scene, wrong_color)["status"] == "failed"


def test_missing_external_runtimes_are_indeterminate_and_do_not_mutate_scene(tmp_path, monkeypatch):
    scene = build_f40("external-tools-missing", "1:24")
    design_dir = tmp_path / scene.design_id
    design_dir.mkdir()
    (design_dir / "model.mpd").write_text(ldraw(scene, submodels=True), encoding="utf-8")
    (design_dir / "scene.json").write_text(scene.model_dump_json(), encoding="utf-8")
    monkeypatch.setattr(settings, "storage_path", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "assembly_external_checks_enabled", True)

    report = run_external_checks(scene, design_dir)

    assert report["scene_hash"] == scene.digest()
    assert report["status"] == "indeterminate"
    assert all(item["status"] == "indeterminate" for item in report["checks"].values())
    assert not scene.connections
    assert json.loads((design_dir / "external/report.json").read_text(encoding="utf-8"))["scene_hash"] == scene.digest()


def test_external_worker_paths_resolve_from_backend_root():
    paths = _tool_paths()
    assert paths["ldraw_worker"].name == "ldraw_mcp_quality.py"
    assert paths["ldraw_worker"].parent.name == "tasks"
    assert paths["legolization_worker"].is_file()


def test_external_checks_disabled_are_explicit(tmp_path, monkeypatch):
    scene = build_f40("external-tools-disabled", "1:24")
    monkeypatch.setattr(settings, "assembly_external_checks_enabled", False)
    report = run_external_checks(scene, tmp_path)
    assert report["status"] == "indeterminate"
    assert report["checks"] == {}


def test_external_rerun_does_not_reuse_previous_pass_report(tmp_path, monkeypatch):
    scene = build_f40("external-tools-stale-report", "1:24")
    design_dir = tmp_path / scene.design_id
    design_dir.mkdir()
    (design_dir / "model.mpd").write_text(ldraw(scene, submodels=True), encoding="utf-8")
    stale = {
        "root": tmp_path / "tools",
        "ldraw_python": tmp_path / "tools" / "ldraw-python.exe",
        "ldraw_command": tmp_path / "tools" / "ldraw-mcp.exe",
        "blender": tmp_path / "tools" / "blender.exe",
        "legolization_python": tmp_path / "tools" / "legolization-python.exe",
        "ldraw_worker": tmp_path / "ldraw_worker.py",
        "legolization_worker": tmp_path / "legolization_worker.py",
    }
    for path in stale.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
    for tool in ("ldraw_mcp", "legolization"):
        report_path = design_dir / "external" / tool / "report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({"status": "passed"}), encoding="utf-8")

    monkeypatch.setattr(settings, "storage_path", str(tmp_path / "storage"))
    monkeypatch.setattr(settings, "assembly_external_checks_enabled", True)
    monkeypatch.setattr(external_quality, "_tool_paths", lambda: stale)
    monkeypatch.setattr(external_quality, "_run_process", lambda *_args, **_kwargs: (0, "", "", None))

    report = run_external_checks(scene, design_dir)

    assert report["status"] == "indeterminate"
    assert all(check["status"] == "indeterminate" for check in report["checks"].values())
    assert all("final report" in check["error"] for check in report["checks"].values())
    assert all(list((design_dir / "external" / tool).glob("report.previous-*.json"))
               for tool in ("ldraw_mcp", "legolization"))


def test_external_render_contact_sheet_is_split_by_azimuth(tmp_path):
    sheet = Image.new("RGB", (60, 10))
    colors = [(255, 0, 0), (0, 255, 0), (0, 0, 255)]
    for index, color in enumerate(colors):
        sheet.paste(color, (index * 20, 0, (index + 1) * 20, 10))
    from io import BytesIO
    encoded = BytesIO()
    sheet.save(encoded, format="PNG")
    result = SimpleNamespace(content=[SimpleNamespace(type="image", data=base64.b64encode(encoded.getvalue()).decode())])

    artifacts = _write_images(result, tmp_path, "exterior", [-90, 0, 90])

    assert artifacts == ["exterior-azimuth-m90.png", "exterior-azimuth-p0.png", "exterior-azimuth-p90.png"]
    actual = [Image.open(tmp_path / artifact).getpixel((0, 0)) for artifact in artifacts]
    assert actual == colors


def test_timed_out_worker_report_does_not_expose_internal_pending_marker(tmp_path):
    report_path = tmp_path / "report.json"
    external_quality._prepare_worker_report(report_path, "ldraw-mcp", "scene-hash")

    report = external_quality._load_worker_report(report_path, None, "", "Timed out after 1 second")

    assert report["status"] == "indeterminate"
    assert report["error"] == "Timed out after 1 second"
    assert "_pending" not in report


def test_seat_detail_group_uses_seat_and_mount_parts_only():
    scene = {"parts": [
        {"module": "cockpit", "feature": "bucket_seat", "part_num": "4079.dat"},
        {"module": "cockpit", "feature": "seat_mount", "part_num": "3794b.dat"},
        {"module": "cockpit", "feature": "dashboard", "part_num": "3069b.dat"},
    ]}

    groups = dict(_detail_groups(scene))

    assert [part["feature"] for part in groups["seats"]] == ["bucket_seat", "seat_mount"]
