import json
from unittest.mock import patch

import pytest

from car2lego3d import common


def test_atomic_json_retries_a_brief_windows_reader_lock(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text('{"status":"old"}')
    replace = common.os.replace
    calls = []
    def locked_then_available(source, target):
        calls.append(1)
        assert json.loads(path.read_text())["status"] == "old"
        if len(calls) < 3:
            raise PermissionError("Constructed Windows sharing violation")
        replace(source, target)
    with patch.object(common.os, "replace", side_effect=locked_then_available), patch.object(common.time, "sleep"):
        common.write_json(path, dict(status="new"))
    assert len(calls) == 3
    assert json.loads(path.read_text())["status"] == "new"


def test_persistent_write_denial_keeps_original_and_stops_retrying(tmp_path):
    path = tmp_path / "progress.json"
    path.write_text('{"status":"old"}')
    with patch.object(common.os, "replace", side_effect=PermissionError("Constructed denial")) as replace, \
            patch.object(common.time, "sleep"):
        with pytest.raises(PermissionError):
            common.write_json(path, dict(status="new"))
    assert replace.call_count == 8
    assert json.loads(path.read_text())["status"] == "old"
