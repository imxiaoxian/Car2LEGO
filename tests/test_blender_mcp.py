from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from car2lego3d import blender_mcp
from car2lego3d.common import write_json


def test_mcp_uses_isolated_interpreter_from_local_configuration(tmp_path, monkeypatch):
    monkeypatch.delenv("CAR2LEGO_MCP_PYTHON", raising=False)
    def run(command, **kwargs):
        assert command[0] == "isolated-python"
        write_json(tmp_path / "test-mcp-response.json", dict(result=dict(content=[dict(type="text", text="OK")])))
        return SimpleNamespace(returncode=0, stdout=b"", stderr=b"")
    with patch.object(blender_mcp, "configuration", return_value=(tmp_path, "shared-python")), \
            patch("dotenv.dotenv_values", return_value={"CAR2LEGO_MCP_PYTHON": "isolated-python"}), \
            patch.object(blender_mcp, "upstream", return_value=tmp_path), \
            patch.object(blender_mcp.subprocess, "run", side_effect=run):
        blender_mcp.call("test", {}, tmp_path, "test")


def test_blender_preferences_stay_in_run_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("CAR2LEGO_BLENDER", "test-blender")
    probe, process = MagicMock(), MagicMock()
    probe.__enter__.return_value = probe
    probe.connect_ex.side_effect = [1, 0]
    process.poll.return_value = None
    with patch.object(blender_mcp.socket, "socket", return_value=probe), \
            patch.object(blender_mcp, "upstream", return_value=tmp_path), \
            patch.object(blender_mcp.subprocess, "Popen", return_value=process) as launch:
        with blender_mcp.BlenderSession(tmp_path):
            assert launch.call_args.kwargs["env"]["BLENDER_USER_CONFIG"] == str((tmp_path / "blender-user-config").resolve())
        process.terminate.assert_called_once()


@pytest.mark.parametrize("code", ["import os", "from . import unsafe", "open('file')", "bpy.ops.wm.open_mainfile()"])
def test_generated_code_rejects_unsupported_host_operations(code):
    with pytest.raises(ValueError):
        blender_mcp.validate_code(code)
