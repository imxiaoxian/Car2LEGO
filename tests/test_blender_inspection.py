"""Host-side provenance and artifact lifecycle; Blender geometry is verified in separate real runs."""
import json
import runpy
import sys
from unittest.mock import MagicMock

import pytest

from car2lego3d.common import ROOT, digest, write_json


def test_inspection_keeps_detail_report_separate_from_stage_record(tmp_path, monkeypatch):
    source = tmp_path / "source.blend"
    source.write_bytes(b"constructed scene fixture")
    output = tmp_path / "inspection"
    main = runpy.run_path(str(ROOT / "scripts/inspect_blender_details.py"))["main"]
    session = MagicMock()
    session.__enter__.return_value = session

    def execute(code, name):
        if name == "inspect-details":
            write_json(output / "detail-inspection.json", dict(source_sha256=digest(source), sampled_objects=1,
                issues=[dict(kind="constructed local occlusion", object="fixture")]))
            (output / "inspected.blend").write_bytes(b"constructed annotated fixture")

    session.execute.side_effect = execute
    monkeypatch.setitem(main.__globals__, "BlenderSession", MagicMock(return_value=session))
    monkeypatch.setattr(sys, "argv", ["inspect", "--blend", str(source), "--output", str(output)])
    main()
    report = json.loads((output / "detail-inspection.json").read_text(encoding="utf-8"))
    record = json.loads((output / "detail-inspection-run.json").read_text(encoding="utf-8"))
    assert report["issues"][0]["object"] == "fixture"
    assert record["status"] == "completed" and record["issues"] == 1
    assert record["inputs"]["new_model_calls"] == 0
    assert record["source_preserved"] is True
    assert record["outputs"]["detail-inspection.json"] == digest(output / "detail-inspection.json")
    assert source.read_bytes() == b"constructed scene fixture"


def test_refinement_rejects_inspection_from_a_different_scene_before_requesting_a_patch(tmp_path, monkeypatch):
    source = tmp_path / "source"
    source.mkdir()
    (source / "model.blend").write_bytes(b"constructed scene fixture")
    details = tmp_path / "details.json"
    write_json(details, dict(source_sha256="different-scene-hash"))
    main = runpy.run_path(str(ROOT / "scripts/refine_blender_model.py"))["main"]
    for name, value in (("load_spec", {}), ("load_views", ({}, {})), ("modelling_model", "gpt-6-astra")):
        monkeypatch.setitem(main.__globals__, name, MagicMock(return_value=value))
    ask = MagicMock()
    monkeypatch.setitem(main.__globals__, "ask_json", ask)
    output = tmp_path / "output"
    monkeypatch.setattr(sys, "argv", ["refine", "--source", str(source), "--spec", "unused-spec",
        "--views", "unused-views", "--output", str(output), "--focus", "fixture", "--details", str(details)])
    with pytest.raises(SystemExit):
        main()
    ask.assert_not_called()
    assert not output.exists()
