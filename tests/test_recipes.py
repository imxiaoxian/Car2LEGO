import copy
import json

import numpy as np
import pytest
import trimesh

from car2lego3d.carfit import fit_mesh, design
from car2lego3d.common import ROOT
from car2lego3d.recipes import catalog, classify, selection_record
from car2lego3d.vehicle import load_spec


def spec():
    return copy.deepcopy(load_spec(ROOT / "data/vehicles/ferrari_f40_1987.json"))


def mesh():
    body = trimesh.creation.box((16, 6, 2))
    cabin = trimesh.creation.box((7, 4, 2))
    cabin.apply_translation((2, 0, 2))
    return trimesh.util.concatenate((body, cabin))


@pytest.mark.parametrize("name,family", [
    ("Lotus For Me", "suv"), ("BMW M4 G82 Coupe", "coupe"), ("Mercedes F1 W12", "f1_race"),
    ("BMW M Hybrid V8", "prototype_race"), ("Audi RS6 Avant", "wagon"),
    ("Ford F150 Pickup", "pickup"), ("MINI Cooper", "hatchback"),
    ("Mercedes G63", "offroad"), ("Mercedes SL63 Roadster", "convertible"),
    ("Toyota MPV", "mpv"), ("Unknown", "other")])
def test_identity_selects_distinct_architectures(name, family):
    assert classify({"model": name})["family"] == family


def test_official_references_are_real_retrieved_sets():
    sources = json.loads((ROOT / "data/recipes/official-sources.json").read_text(encoding="utf-8"))["sets"]
    for name, family in catalog()["families"].items():
        record = selection_record({"family": name})
        assert not record["official_replica"]
        for number in family["official_sets"]:
            assert sources[number]["metadata"]["setNumber"] == number
            assert sources[number]["instruction_pdfs"]


@pytest.mark.parametrize("family", ["sports_car", "f1_race", "coupe", "sedan", "hatchback", "wagon", "suv", "crossover", "offroad", "convertible", "pickup"])
def test_each_supported_architecture_exports_rigid_parts(family):
    fitted = fit_mesh(mesh(), specifications=spec(), scale="1:24", body_style=family)
    car = design(fitted)
    assert car.parts and fitted["recipe_selection"]["selection"]["family"] == family
    for part in car.parts:
        rotation = np.array(part.rotation).reshape(3, 3)
        np.testing.assert_allclose(rotation.T @ rotation, np.eye(3))
        assert np.linalg.det(rotation) == pytest.approx(1)
    modules = [part.module for part in car.parts]
    if family == "f1_race":
        assert "front wing" in modules and "rear wing" in modules
        assert not any("arch" in m or "windscreen" in m for m in modules)
        assert modules.count("single cockpit seat") == 1
    if family == "convertible":
        assert "front windscreen" in modules and "rear windscreen" not in modules
        assert not any("roof" in m or "window frames" in m for m in modules)
    if family == "pickup":
        assert "cargo bed" in modules and "opaque trunk" not in modules


def test_unimplemented_architecture_is_not_silently_changed_to_sports_car():
    with pytest.raises(ValueError, match="no implemented recipe"):
        fit_mesh(mesh(), specifications=spec(), scale="1:24", body_style="truck")


def test_image_brief_roof_paint_and_four_door_layout():
    fitted = fit_mesh(mesh(), specifications=spec(), scale="1:24", body_style="sedan",
                     reference_brief={"paint": "orange with black roof", "body_style": "sedan"})
    car = design(fitted)
    assert len([p for p in car.parts if p.module == "door skin"]) == 4
    assert all(p.color == 0 for p in car.parts if "roof" in p.module)
