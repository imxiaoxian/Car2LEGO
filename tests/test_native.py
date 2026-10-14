import json
from unittest.mock import patch

import pytest

from car2lego3d.native import configured_preview


def test_unconfigured_renderer_keeps_preview_unavailable(tmp_path, monkeypatch):
    monkeypatch.delenv("LDRAW_LIBRARY_PATH", raising=False)
    monkeypatch.delenv("LDRAW_MCP_BLENDER", raising=False)
    assert configured_preview(tmp_path / "model.ldr", tmp_path) is None
    assert json.loads((tmp_path / "native-render.json").read_text())["status"] == "unavailable"


def test_configured_renderer_failure_cannot_silently_deliver_mesh_thumbnail(tmp_path, monkeypatch):
    monkeypatch.setenv("LDRAW_LIBRARY_PATH", "configured-library")
    monkeypatch.setenv("LDRAW_MCP_BLENDER", "configured-blender")
    with patch("car2lego3d.native.render_native", side_effect=ValueError("Missing native parts")):
        with pytest.raises(RuntimeError, match="native preview failed"):
            configured_preview(tmp_path / "model.ldr", tmp_path)
    report = json.loads((tmp_path / "native-render.json").read_text())
    assert report["status"] == "failed" and not report["appearance_accepted"]


def test_native_preview_belongs_to_generated_assembly(tmp_path, monkeypatch):
    monkeypatch.setenv("LDRAW_LIBRARY_PATH", "configured-library")
    monkeypatch.setenv("LDRAW_MCP_BLENDER", "configured-blender")
    preview = tmp_path / "native-ldraw.png"
    preview.write_bytes(b"constructed test fixture")
    (tmp_path / "model.ldr").write_text("constructed test assembly")
    with patch("car2lego3d.native.render_native", return_value=preview) as renderer:
        assert configured_preview(tmp_path / "model.ldr", tmp_path) == preview
    assert renderer.call_args.args[0] == tmp_path / "model.ldr"
    report = json.loads((tmp_path / "native-render.json").read_text())
    assert report["status"] == "completed" and not report["appearance_accepted"]
