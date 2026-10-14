import json
import struct
from collections import Counter

import numpy as np
import pytest
from pydantic import ValidationError

from app.config import settings
from app.services.assembly_v3.catalog import parse_connections, Port, part_validity
from app.services.assembly_v3.connections import compatible, infer_connections, axle_match
from app.services.assembly_v3.exports import ldraw, read_ldraw, read_step_blocks
from app.services.assembly_v3.jobs import JobStore, JobStopped, BudgetExceeded
from app.services.assembly_v3.recipes import build_f40
from app.services.assembly_v3.scene import AssemblyScene, PartInstance, Module, Transform, BuildStep
from app.services.assembly_v3.validation import collisions
from app.services.studio_service import StudioService, StudioFile


def test_unofficial_geometry_does_not_bypass_connector_and_collider_checks(tmp_path, monkeypatch):
    import app.services.assembly_v3.catalog as catalogue
    root = tmp_path / "ldraw"
    (root / "UnOfficial" / "parts").mkdir(parents=True)
    (root / "UnOfficial" / "parts" / "fixture.dat").write_text("0 Fixture", encoding="utf-8")
    monkeypatch.setattr(settings, "studio_ldraw_path", str(root))
    def unavailable(_):
        raise ValueError("unavailable")
    monkeypatch.setattr(catalogue, "ports", unavailable)
    monkeypatch.setattr(catalogue, "local_boxes", unavailable)
    result = part_validity("fixture.dat")
    assert result["geometry"] and "UnOfficial" in result["geometry_source"]
    assert not result["connections"] and not result["collider"]


def test_f40_surface_has_complete_geometry_connected_load_path_and_wheel_clearance():
    from app.services.assembly_v3.validation import validate_scene
    scene = build_f40("surface-check", "1:24")
    report = validate_scene(scene)
    assert scene.planning["recipe"] == "f40-surface-5"
    for gate in ("parts", "transforms", "connections", "collisions", "dimensions"):
        assert report["gates"][gate] == "passed", report
    assert report["collision_coverage"]["status"] == "complete"
    wheels = [m for m in report["mechanisms"] if m["capability"] == "rolling_wheels"]
    assert len(wheels) == 4 and all(m["status"] == "passed" and len(m["samples"]) == 9 for m in wheels)
    assert report["gates"]["mechanisms"] == "failed"  # opening covers are still unimplemented
    assert not report["precision_verified"]


def test_f40_surface_recipe_does_not_route_other_vehicles_through_fixed_canopy():
    from app.services.assembly_v3.specifications import F40_SPEC
    spec = dict(F40_SPEC, width_mm=1800, height_mm=1300)
    scene = build_f40("other", "1:24", vehicle={"make": "Porsche", "model": "911", "year": 1990}, spec=spec)
    assert scene.planning["recipe"] != "f40-surface-5"


def test_unknown_collider_cannot_pass_static_or_motion_gates(monkeypatch):
    import app.services.assembly_v3.validation as validation
    real_validity, real_boxes = validation.part_validity, validation.local_boxes
    def validity(number):
        result = real_validity(number)
        if number == "50950.dat":
            result["collider"] = False
        return result
    def boxes(number):
        if number == "50950.dat":
            raise ValueError("missing fixture collision data")
        return real_boxes(number)
    monkeypatch.setattr(validation, "part_validity", validity)
    monkeypatch.setattr(validation, "local_boxes", boxes)
    report = validation.validate_scene(build_f40("coverage", "1:24"))
    assert report["gates"]["collisions"] == "unverified"
    assert report["collision_coverage"]["missing_part_numbers"] == ["50950.dat"]
    assert all(m["status"] != "passed" for m in report["mechanisms"])


def connected_fixture(offset=(0., -8., 0.)):
    parts = [PartInstance(id="a", part_num="3024.dat", color_id=4, module="base", transform=Transform()),
             PartInstance(id="b", part_num="3024.dat", color_id=4, module="top", transform=Transform(position=offset))]
    return AssemblyScene(design_id="fixture", vehicle={}, scale="1:24", specifications={}, target_ldu={}, parts=parts,
                         modules=[Module(id="base", structural=True),Module(id="top", depends_on=["base"])],
                         steps=[BuildStep(index=1,module="base",parts=["a"]),BuildStep(index=2,module="top",parts=["b"])])


@pytest.mark.parametrize("rotation", [(2.,0.,0.,0.,1.,0.,0.,0.,1.),(-1.,0.,0.,0.,1.,0.,0.,0.,1.),(1.,0.,0.,0.,1.,1.,0.,0.,1.)])
def test_no_scaling_or_reflection(rotation):
    with pytest.raises(ValidationError): Transform(rotation=rotation)


def test_connector_graph_accepts_stack_rejects_misalignment_and_floating():
    scene=connected_fixture()
    scene.connections, report=infer_connections(scene)
    assert report["status"] == "passed"
    assert collisions(scene) == []
    assert infer_connections(connected_fixture((4.,-8.,0.)))[1]["status"] == "failed"
    assert infer_connections(connected_fixture((0.,-80.,0.)))[1]["disconnected_parts"] == ["b"]


def test_local_motion_checks_match_full_pairs_without_static_interferences():
    scene=connected_fixture((0.,0.,0.))
    for identifier,module in (("c","base"),("d","top")):
        scene.parts.append(PartInstance(id=identifier,part_num="3024.dat",color_id=4,module=module,
            transform=Transform(position=(100.,0.,0.))))
        scene.steps.append(BuildStep(index=len(scene.steps)+1,module=module,parts=[identifier]))
    AssemblyScene.model_validate(scene.model_dump())
    all_pairs={frozenset(i["parts"]) for i in collisions(scene)}
    assert {frozenset(("a","b")),frozenset(("c","d"))} <= all_pairs
    for moving in ({"a"},{"b"},{"a","b"}):
        assert {frozenset(i["parts"]) for i in collisions(scene,moving_ids=moving)} == {p for p in all_pairs if p & moving}
    stack=connected_fixture()
    all_edges,_=infer_connections(stack)
    local_edges,local_report=infer_connections(stack,part_ids={"a","b"})
    assert local_edges==all_edges and local_report["status"]=="passed"
    assert infer_connections(stack,part_ids={"a"})[0]==[]


def test_official_guides_keep_provenance_and_reject_tampered_pages(tmp_path):
    import hashlib
    from PIL import Image
    from app.services.assembly_v3.official_guides import guide_records, guide_content
    root=tmp_path/"official_references";root.mkdir()
    path=root/"page.png";Image.new("RGB",(32,32),"red").save(path)
    manifest={"10248":{"pdf":"source.pdf","pages":[48],"representative_pages":[dict(
        page=48,module="cockpit",path=path.name,sha256=hashlib.sha256(path.read_bytes()).hexdigest())]}}
    (root/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    request=dict(make="Ferrari",model="F40",scale="1:24")
    records=guide_records(tmp_path,request)
    assert len(records)==1 and records[0]["accepted_for_target_scale"] is False
    assert records[0]["synthetic"] is False
    content=guide_content(tmp_path,request)
    assert len([b for b in content if b["type"]=="image_url"])==1
    assert "PDF page 48" in content[1]["text"]
    path.write_bytes(b"tampered")
    assert len(guide_content(tmp_path,request))==1
    manifest["10248"]["representative_pages"][0]["path"]="../outside.png"
    (root/"manifest.json").write_text(json.dumps(manifest),encoding="utf-8")
    with pytest.raises(ValueError,match="Invalid official reference path"):
        guide_content(tmp_path,request)


@pytest.mark.parametrize("version", [0,1])
def test_binary_grid_versions(version):
    integer="i" if version else "h"
    header=b"!!HS"+struct.pack("<ii",1,0)+b"!!DS" if version else b""
    data=struct.pack("<"+integer*2,8192 if version else 3,23)+struct.pack("<12f",1,0,0,0,1,0,0,0,1,0,0,0)+struct.pack("<hh",2,2)
    data+=b"".join(struct.pack("<"+integer*2,10,4) for _ in range(9))
    data+=b"\x00" if version else b""
    ports=parse_connections(header+data)
    assert len(ports)==9 and ports[4].position==(10.,0.,-10.)
    with pytest.raises(ValueError): parse_connections(header+data[:-1])


def test_unknown_connectors_fail_closed():
    with pytest.raises(ValueError): parse_connections(struct.pack("<hh",77,1))
    assert not compatible(Port("a","ball",1,(0,0,0),(0,1,0)),Port("b","ball",2,(0,0,0),(0,1,0)))
    assert not compatible(Port("a","axle",6,(0,0,0),(0,1,0),semantic="axle_socket"),Port("b","axle",3,(0,0,0),(0,1,0),semantic="pin"))


@pytest.mark.parametrize("scale", ["1:38","1:24","1:16","1:12"])
def test_scale_layout_rigid_and_export_roundtrip(tmp_path,scale):
    scene=build_f40("fixture",scale)
    assert scene.planning["scale_requirements"]["scale"] == scale
    assert all(len(s.parts) <= scene.planning["scale_requirements"]["max_step_parts"] for s in scene.steps)
    assert all(np.isclose(np.linalg.det(np.array(p.transform.rotation).reshape(3,3)),1) for p in scene.parts)
    assert abs(scene.planning["grid"]["wheelbase"] / scene.target_ldu["wheelbase"]-1)<.03
    restored=AssemblyScene.model_validate_json(scene.model_dump_json())
    assert scene.digest()==restored.digest()
    mpd=ldraw(scene,True);flat=ldraw(scene)
    assert Counter(read_ldraw(mpd))==Counter(read_ldraw(flat))
    sf=StudioService.create_studio_file(mpd,"F40");sf.save(tmp_path/"f40.io")
    assert Counter(read_ldraw(StudioFile.from_path(tmp_path/"f40.io").model_ldr))==Counter(read_ldraw(flat))
    assert "0 FILE front_hood.ldr" in sf.model2_ldr
    blocks=read_step_blocks(sf.model_ldr)
    assert len(blocks)==len(scene.steps) and sum(len(b[1]) for b in blocks.values())==len(scene.parts)
    import zipfile
    with zipfile.ZipFile(tmp_path/"f40.io") as archive: assert "model.ins" not in archive.namelist()


def test_job_controls_budgets_and_durable_resume(tmp_path,monkeypatch):
    monkeypatch.setattr(settings,"assembly_text_call_limit",1)
    jobs=JobStore(tmp_path);jobs.ensure("car",{"scale":"1:24"});owner=jobs.claim("car")
    assert jobs.claim("car") is None
    jobs.consume("car",owner,"text")
    with pytest.raises(BudgetExceeded):jobs.consume("car",owner,"text")
    jobs.checkpoint("car",owner,"assembly",50,scene_hash="saved")
    jobs.control("car","pause")
    with pytest.raises(JobStopped):jobs.checkpoint("car",owner,"validation",70)
    jobs.finish("car",owner,"paused")
    assert JobStore(tmp_path).get("car")["data"]["checkpoint"]["scene_hash"]=="saved"
    jobs.control("car","resume");owner=jobs.claim("car")
    jobs.control("car","cancel");jobs.finish("car",owner,"completed")
    assert jobs.get("car")["state"]=="cancelled"


def test_repair_invalidates_dependents_only():
    scene=connected_fixture()
    assert scene.dependency_closure("top")=={"top"}
    assert scene.dependency_closure("base")=={"base","top"}


def shaft(port, position, direction=(1.,0.,0.), forward=(0.,0.,1.)):
    return (port.id, port, np.array(position), np.array(direction), np.array(forward))


def test_axles_require_inserted_segments_and_respect_caps_and_keying():
    axle=Port("axle","axle",7,(0,0,0),(1,0,0),length=80,semantic="axle",cross_type=True)
    socket=Port("socket","axle",6,(0,0,0),(1,0,0),length=20,semantic="axle_socket",cross_type=True)
    a=shaft(axle,(40,0,0))
    assert axle_match(a,shaft(socket,(20,0,0)))  # endpoints separated, shaft inserted
    assert axle_match(a,shaft(socket,(20,0,0),forward=(0.,1.,0.)))
    assert not axle_match(a,shaft(socket,(20,1,0)))
    assert not axle_match(a,shaft(socket,(60,0,0)))  # merely touches
    assert not axle_match(a,shaft(socket,(20,0,0),forward=(0.,2**-.5,2**-.5)))
    from dataclasses import replace
    assert not axle_match(a,shaft(replace(socket,start_capped=True),(20,0,0)))
    assert axle_match(a,shaft(replace(socket,start_capped=True),(40,0,0)))


def test_pin_and_clip_compatibility_and_hinge_fixture():
    pin=Port("pin","axle",3,(0,0,0),(1,0,0),length=20,semantic="pin",end_capped=True)
    hole=Port("hole","axle",2,(0,0,0),(1,0,0),length=20,semantic="pin_socket")
    assert axle_match(shaft(pin,(20,0,0)),shaft(hole,(20,0,0)))
    bar=Port("bar","axle",13,(0,0,0),(1,0,0),length=40,semantic="bar",grabbing_required=True)
    clip=Port("clip","axle",12,(0,0,0),(1,0,0),length=4,semantic="clip",grabbing=True)
    assert compatible(bar,clip) and axle_match(shaft(bar,(20,0,0)),shaft(clip,(0,0,0)))
    scene=connected_fixture((0.,0.,0.))
    scene.parts[0].part_num="3937.dat";scene.parts[1].part_num="3938.dat"
    scene.connections,report=infer_connections(scene)
    assert report["status"]=="passed" and any(c.kind=="hinge:hinge" for c in scene.connections)
    assert collisions(scene)==[]
