from copy import deepcopy
from threading import Event

import pytest

from car2lego3d.vehicle import UNITS
from car2lego3d.vehicle_dialogue import compile_dialogue
from car2lego3d.desktop import physical
from unittest.mock import patch


def answer():
    values = dict(length=5103, width=2019, height=1636, wheelbase=3019,
                  front_overhang=1000, rear_overhang=1084)
    return dict(status="ready", model="Lotus For Me", variant="representative, year unspecified",
        width_reference="excluding_mirrors", questions=[], notes=["Constructed test estimates"],
        measurements=[dict(field=k, value=values.get(k), unit=u,
            status="estimated" if k in values else "unknown", confidence=.6 if k in values else 0,
            note="Constructed engineering estimate" if k in values else "Unknown") for k,u in UNITS.items()])


AUDIT = dict(mode="model_dialogue", model="gpt-6.1-sol", dialogue_file="dialogue.json", dialogue_sha256="test")
IDENTITY = dict(brand="Lotus", model="For Me", variant="")


def test_model_estimates_remain_unverified_and_year_is_optional():
    result = compile_dialogue(answer(), IDENTITY, AUDIT)
    assert result["status"] == "ready"
    assert not result["spec"]["manufacturer_verified"]
    assert result["spec"]["measurements"]["door_length"]["value"] is None
    ui = physical(result["spec"], {**IDENTITY, "scale": "1:24"}, audit=AUDIT)
    assert not ui["overall_grounded"]
    assert ui["measurements"]["length"]["source_status"] == "model_estimated"
    assert ui["research"]["skill"] == "vehicle-dialogue"
    assert ui["research"]["queries"] == []


@pytest.mark.parametrize("fault", ["lego_size", "overhang", "duplicate", "missing", "unit", "tyre_partial", "unknown_confidence"])
def test_invalid_model_values_rejected(fault):
    data = deepcopy(answer())
    fields = {m["field"]: m for m in data["measurements"]}
    if fault == "lego_size": fields["length"]["value"] = 200
    if fault == "overhang": fields["rear_overhang"]["value"] = 1200
    if fault == "duplicate": data["measurements"].append(fields["length"])
    if fault == "missing": data["measurements"].pop()
    if fault == "unit": fields["length"]["unit"] = "inch"
    if fault == "tyre_partial": fields["front_tyre_width"].update(value=265, status="estimated", confidence=.5)
    if fault == "unknown_confidence": fields["door_length"]["confidence"] = .5
    with pytest.raises(ValueError):
        compile_dialogue(data, IDENTITY, AUDIT)


def test_default_acquisition_is_dialogue_and_never_enters_web_route(tmp_path):
    from car2lego3d.research import research_vehicle
    with patch("car2lego3d.vehicle_dialogue.ask_json", return_value=answer()) as ask, \
            patch("car2lego3d.vehicle_dialogue.settings", return_value=dict(model="gpt-6.1-sol", base_url="https://example.test/v1")), \
            patch("car2lego3d.research.research_vehicle_web", side_effect=AssertionError("web route entered")):
        result = research_vehicle(IDENTITY, tmp_path)
    assert result["audit"]["web_search_calls"] == 0
    assert result["audit"]["mode"] == "model_dialogue"
    assert ask.call_count == 1
    assert (tmp_path / "spec.json").is_file()


def test_dialogue_cache_excludes_legacy_web_results(ready_research):
    from car2lego3d.common import write_json
    store, old_id = ready_research()
    identity = dict(brand="Ferrari", model="F40", variant="")
    write_json(store.directory / old_id / "result.json", dict(status="ready", request=identity, audit=dict(mode="live")))
    with patch("car2lego3d.research.research_vehicle", return_value=dict(status="not_found", request=identity)):
        current = store.start(identity)
        store.close()
    assert current["id"] != old_id


def test_cached_vehicle_remains_available_during_other_dialogue(ready_research):
    store, cached_id = ready_research()
    started, release = Event(), Event()

    def work(identity, directory):
        started.set()
        release.wait(5)
        return dict(status="not_found", request=identity)

    try:
        with patch("car2lego3d.research.research_vehicle", side_effect=work):
            store.start(IDENTITY)
            assert started.wait(2)
            cached = store.start(dict(brand="Ferrari", model="F40", variant=""))
            assert cached["cached"] and cached["id"] == cached_id
            assert store.active != cached_id
    finally:
        release.set()
        store.close()
