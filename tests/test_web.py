import hashlib
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from functools import partial
import json
from threading import Thread
from unittest.mock import patch

import pytest

from car2lego3d.common import ROOT, write_json
from car2lego3d.web import FILES, Handler, JobStore, catalog_brands, prepare_request, write_status


def request(**changes):
    return {"brand": "Ferrari", "custom": False, "model": "F40", "scale": "1:24", **changes}


def test_catalog_has_local_chinese_names_and_verified_logos():
    brands = catalog_brands()
    assert len(brands) >= 396
    assert len({b["id"] for b in brands}) == len(brands)
    assert len({b["name"] for b in brands}) == len(brands)
    for brand in brands:
        assert brand["name_zh"] and brand["source_url"] and brand["logo_source_url"]
        path = ROOT / "frontend/public" / brand["logo"].lstrip("/")
        assert path.resolve().is_relative_to((ROOT / "frontend/public/brands").resolve())
        assert hashlib.sha256(path.read_bytes()).hexdigest() == brand["logo_sha256"]


def test_catalog_brand_enters_prompt_and_exact_scale_preflight():
    data, args, plan = prepare_request(request())
    assert data["brand_id"] == "ferrari"
    assert data["brand_zh"] == "法拉利"
    assert "Ferrari F40" in args[args.index("--prompt") + 1]
    assert args[args.index("--scale") + 1] == "1:24"
    assert plan["generation"]["draft_recipe_available"]


def test_other_preserves_custom_brand_without_borrowing_specs():
    data, args, plan = prepare_request(request(brand="自定义汽车", custom=True, model="X", scale="custom"))
    assert data["brand"] == "自定义汽车" and data["brand_id"] is None
    assert "自定义汽车 X" in data["prompt"]
    assert "--vehicle-specs" not in args and plan is None


@pytest.mark.parametrize("changes", [
    {"brand": "unknown"}, {"brand": " "}, {"custom": "false"}, {"custom": True},
    {"brand": "Tesla"}, {"model": "Testarossa"}, {"scale": "1:38"}, {"scale": "1:16"},
    {"scale": "1:12"}, {"scale": "1:8"}, {"color": True}, {"seed": -1},
    {"scale": "custom", "length_studs": 22}, {"scale": "custom", "length_studs": True},
    {"description": "\n"}, {"brand": "X" * 101, "custom": True},
])
def test_invalid_or_unsupported_requests_fail_before_model_call(changes):
    with pytest.raises(ValueError):
        prepare_request(request(**changes))


def test_generic_brand_uses_catalog_name_and_only_nominal_size():
    data, args, plan = prepare_request(request(brand="Tesla", model="Roadster", scale="custom", length_studs=28))
    assert data["brand_id"] == "tesla" and "Tesla Roadster" in data["prompt"]
    assert args[args.index("--length-studs") + 1] == "28"
    assert "--scale" not in args and "--vehicle-specs" not in args


def test_job_persists_request_exports_and_archive_downloads(tmp_path):
    store = JobStore(tmp_path)

    def simulated_pipeline(args, **kwargs):
        output = tmp_path / store.active / "artifacts"
        write_json(output / "pipeline.json", {"status": "completed"})
        studio = output / FILES["studio"]
        studio.parent.mkdir(parents=True)
        studio.write_bytes(b"test archive")
        return type("Result", (), {"returncode": 0})()

    with patch("car2lego3d.web.subprocess.run", side_effect=simulated_pipeline) as run:
        initial = store.start(request())
        store.worker.join(timeout=5)
    job = store.get(initial["id"])
    assert job["status"] == "completed" and job["delivery_accepted"] is False
    assert "studio" in job["files"]
    assert store.file(initial["id"], "request").is_file()
    assert run.call_args.args[0][1:5] == ["-u", "-m", "car2lego3d", "run"]
    assert JobStore(tmp_path).get(initial["id"])["status"] == "completed"
    for kind in ("../../status.json", "log", "status"):
        with pytest.raises(FileNotFoundError):
            store.file(initial["id"], kind)
    with pytest.raises(FileNotFoundError):
        store.get("../../frontend")


def test_failed_pipeline_is_not_marked_completed(tmp_path):
    store = JobStore(tmp_path)
    with patch("car2lego3d.web.subprocess.run", side_effect=OSError("test failure")):
        job = store.start(request())
        store.worker.join(timeout=5)
    assert store.get(job["id"])["status"] == "failed"
    assert "studio" not in store.get(job["id"])["files"]


def test_restart_does_not_misreport_running_job(tmp_path):
    job_id = "a" * 32
    write_json(tmp_path / job_id / "request.json", request())
    write_json(tmp_path / job_id / "status.json", {"status": "running"})
    assert JobStore(tmp_path).get(job_id)["status"] == "interrupted"


def test_status_write_retries_temporary_windows_file_lock(tmp_path):
    target = tmp_path / "status.json"
    with patch("car2lego3d.web.write_json", side_effect=[PermissionError("locked"), None]) as write:
        write_status(target, {"status": "completed"})
    assert write.call_count == 2


def test_http_rejects_foreign_origin_bad_hosts_and_unknown_routes(tmp_path):
    handler = partial(Handler, directory=str(tmp_path), jobs=JobStore(tmp_path))
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        worker = Thread(target=server.serve_forever)
        worker.start()
        try:
            connection = HTTPConnection("127.0.0.1", server.server_port, timeout=5)
            connection.request("GET", "/api/config")
            response = connection.getresponse()
            assert response.status == 200
            assert len(json.loads(response.read())["scales"]) == 4
            connection.request("POST", "/api/jobs", json.dumps(request()),
                               {"Content-Type": "application/json", "Origin": "https://external.test"})
            response = connection.getresponse()
            assert response.status == 403
            response.read()
            connection.request("GET", "/api/config", headers={"Host": "external.test"})
            response = connection.getresponse()
            assert response.status == 403
            response.read()
            connection.request("GET", "/api/unknown")
            response = connection.getresponse()
            assert response.status == 404
            response.read()
            connection.request("POST", "/api/jobs", json.dumps(request(brand="unknown")),
                               {"Content-Type": "application/json", "Origin": f"http://127.0.0.1:{server.server_port}"})
            response = connection.getresponse()
            assert response.status == 400
            response.read()
            connection.close()
        finally:
            server.shutdown()
            worker.join(timeout=5)
