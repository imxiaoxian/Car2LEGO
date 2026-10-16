"""Guard the repository's deployment and backend boundaries."""
import sys

import pytest

from car2lego3d.common import ROOT
from car2lego3d.project import PROJECT_NAME, DEFAULT_BACKEND, FRONTEND_PORT, API_PORT, desktop_backend


def test_desktop_backend_is_llm_blender_only():
    assert PROJECT_NAME == "Car2LGEO_3D_LLM"
    assert desktop_backend() == DEFAULT_BACKEND == "gpt-blender"
    assert desktop_backend("gpt-blender") == DEFAULT_BACKEND
    with pytest.raises(ValueError, match="Car2LEGO_3D"):
        desktop_backend("hunyuan-mv")
    assert (FRONTEND_PORT, API_PORT) == (8778, 8777)


def test_cli_default_setup_routes_to_blender(monkeypatch, capsys):
    from car2lego3d import cli, blender_mcp
    monkeypatch.setattr(blender_mcp, "upstream", lambda: "blender-source")
    monkeypatch.setattr(sys, "argv", ["car2lego3d", "setup"])
    cli.main()
    assert capsys.readouterr().out.strip() == "blender-source"


def test_frontend_proxy_matches_project_api():
    assert f"http://127.0.0.1:{API_PORT}" in (ROOT / "frontend/next.config.mjs").read_text()
