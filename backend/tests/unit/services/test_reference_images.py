import base64
import io
from types import SimpleNamespace
from unittest.mock import AsyncMock

from PIL import Image
import pytest

from app.agents import models
from app.config import settings
from app.services import reference_images as refs
from tests.conftest import MockChatModel


@pytest.fixture
def image_api(monkeypatch):
    image = io.BytesIO()
    Image.new("RGB", (64, 48), "red").save(image, "PNG")
    response = SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(image.getvalue()).decode(), url=None)])
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.images.generate.return_value = response
    client.images.edit.return_value = response
    monkeypatch.setattr(refs, "AsyncOpenAI", lambda **kwargs: client)
    monkeypatch.setattr(settings, "openai_api_key", "test-placeholder")
    llm = MockChatModel(structured_output=refs.VehicleReferenceBrief(
        body_style="sports_car", paint="red", visual_description="Ferrari F40"))
    monkeypatch.setattr(refs, "create_text_llm", lambda **kwargs: llm)
    return client


@pytest.mark.parametrize("year", [1990, None])
async def test_generation_anchors_details_and_reuses_cached_images(tmp_path, image_api, year):
    state = {"design_id": "references-car", "storage_path": str(tmp_path), "make": "Ferrari", "model": "F40", "year": year}
    result = await refs.ReferenceImageService().generate(state)
    assert [r["view"] for r in result["reference_images"]] == list(refs.REFERENCE_VIEWS)
    assert image_api.images.generate.await_count == 1
    assert image_api.images.edit.await_count == 5
    prompt = image_api.images.generate.call_args.kwargs["prompt"]
    assert "None Ferrari" not in prompt
    assert ("1990 Ferrari F40" in prompt) == (year is not None)
    assert all(call.kwargs["model"] == "gpt-image-2.5-sunburst" and call.kwargs["quality"] == "high"
               for call in image_api.images.edit.await_args_list)
    await refs.ReferenceImageService().generate(state)
    assert image_api.images.generate.await_count == 1
    assert image_api.images.edit.await_count == 5
    content = refs.reference_content({**state, **result}, "Build front", "front")
    assert len([b for b in content if b["type"] == "image_url"]) == 2


async def test_vehicle_model_is_never_replaced_by_image_model(tmp_path, image_api, monkeypatch):
    import json
    seen = []
    class BriefModel:
        def with_structured_output(self, *args, **kwargs):
            return self
        async def ainvoke(self, messages):
            seen.append(json.loads(messages[-1].content))
            return refs.VehicleReferenceBrief(body_style="sports_car", paint="red", visual_description="F40")
    monkeypatch.setattr(refs, "create_text_llm", lambda **kwargs: BriefModel())
    await refs.ReferenceImageService().generate(dict(design_id="identity", storage_path=str(tmp_path), make="Ferrari", model="F40", year=1990))
    assert seen[0]["model"] == "F40"
    assert "image_model" not in seen[0]


async def test_photo_is_used_for_overview_and_details(tmp_path, image_api):
    source = tmp_path / "source.jpg"
    Image.new("RGB", (64, 48)).save(source)
    state = {"design_id": "photo-car", "storage_path": str(tmp_path), "make": "Ford", "model": "GT", "year": 2020,
             "source_image_path": str(source)}
    await refs.ReferenceImageService().generate(state)
    assert image_api.images.generate.await_count == 0
    assert image_api.images.edit.await_count == 6
    assert len(image_api.images.edit.await_args_list[0].kwargs["image"]) == 1
    assert len(image_api.images.edit.await_args_list[1].kwargs["image"]) == 2


def test_language_and_vision_use_the_same_openai_model(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-placeholder")
    monkeypatch.setattr(settings, "openai_base_url", "https://api.lundong.ai/")
    monkeypatch.setattr(models, "GatewayChatOpenAI", lambda **kwargs: kwargs)
    for llm in (models.create_text_llm(), models.create_vision_llm()):
        assert llm["model"] == "gpt-6.1-sol"
        assert llm["base_url"] == "https://api.lundong.ai/v1"


async def test_empty_image_response_fails_instead_of_continuing(tmp_path, image_api):
    image_api.images.generate.return_value = SimpleNamespace(data=[])
    with pytest.raises(ValueError, match="no image"):
        await refs.ReferenceImageService().generate({"design_id": "no-image", "storage_path": str(tmp_path),
                                                   "make": "Ford", "model": "GT", "year": 2020})


@pytest.mark.parametrize("scale,extra,count,body_count", [("1:24","hood_hinges",14,5),("1:16","steering",18,8),("1:12","suspension",20,8)])
async def test_precision_plan_includes_interiors_and_panel_states(tmp_path,image_api,scale,extra,count,body_count):
    state=dict(design_id="details",storage_path=str(tmp_path),make="Ferrari",model="F40",year=1990,
               workflow_version="assembly_v3",scale=scale)
    result=await refs.ReferenceImageService().generate(state)
    views={r["view"] for r in result["reference_images"]}
    assert len(views)==count and {"engine_bay","cockpit","seats","hood_opening",extra}<=views
    assert ("doors" in views) == (scale in ("1:16","1:12"))
    assert image_api.images.generate.await_count==1 and image_api.images.edit.await_count==count-1
    await refs.ReferenceImageService().generate(state)
    assert image_api.images.edit.await_count==count-1
    relevant=refs.reference_content({**state,**result},"Build cabin","body")
    assert len([b for b in relevant if b["type"]=="image_url"])==body_count
    assert all(b["image_url"]["url"].startswith("data:image/jpeg;") for b in relevant if b["type"]=="image_url")


async def test_gateway_json_adapter_uses_schema_validation_without_tools(monkeypatch):
    from langchain_core.messages import AIMessage
    from langchain_core.outputs import ChatResult, ChatGeneration
    from langchain_core.exceptions import OutputParserException
    calls=[]
    async def respond(self,messages,**kwargs):
        calls.append((messages,kwargs))
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content='{"body_style":"sports_car","paint":"red","visual_description":"F40"}'))])
    monkeypatch.setattr(models.GatewayChatOpenAI,"_agenerate",respond)
    monkeypatch.setattr(settings,"openai_api_key","test-placeholder")
    result=await models.create_text_llm().with_structured_output(refs.VehicleReferenceBrief).ainvoke("Inspect this car")
    assert result.body_style=="sports_car" and "tools" not in calls[0][1]
    assert "schema" in calls[0][0][0].content
    async def invalid(self,messages,**kwargs):
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content='{"body_style":"invalid","paint":"red"}'))])
    monkeypatch.setattr(models.GatewayChatOpenAI,"_agenerate",invalid)
    with pytest.raises(OutputParserException):
        await models.create_text_llm().with_structured_output(refs.VehicleReferenceBrief).ainvoke("Inspect this car")


async def test_targeted_angle_changes_only_requested_sheet_and_retains_history(tmp_path, image_api):
    state=dict(design_id="targeted", storage_path=str(tmp_path), make="Ferrari", model="F40", year=1990,
               workflow_version="assembly_v3", scale="1:24")
    baseline=await refs.ReferenceImageService().generate(state)
    shot=dict(view="door_hinges", focus="Visible front door pivot and sill clearance", angles=["inside jamb", "low side", "half open"],
              reason="Hinge is hidden in the existing sheet", modules=["doors"])
    state["requested_reference_shots"]=[shot]
    result=await refs.ReferenceImageService().generate(state, only={"door_hinges"})
    assert len(result["reference_images"])==15
    assert image_api.images.edit.await_count==14
    prompt=image_api.images.edit.await_args.kwargs["prompt"]
    assert "inside jamb" in prompt and "clamshell" in prompt and "front-hinged doors" in prompt
    await refs.ReferenceImageService().generate(state, only={"door_hinges"})
    assert image_api.images.edit.await_count==14
    shot["angles"]=["outside jamb", "fully open"]
    result=await refs.ReferenceImageService().generate(state, only={"door_hinges"})
    assert image_api.images.edit.await_count==15
    assert list((tmp_path/"targeted"/"references"/"history").glob("door_hinges-*.png"))
    for old in baseline["reference_images"]:
        assert next(r for r in result["reference_images"] if r["view"]==old["view"])["sha256"]==old["sha256"]
    content=refs.reference_content({**state, **result}, "Design door hinge", "doors")
    assert any("door_hinges" in b.get("text", "") for b in content)


async def test_targeted_reference_budget_keeps_original_and_reports_missing_views(tmp_path, image_api, monkeypatch):
    from app.services.assembly_v3.jobs import BudgetExceeded
    from app.services.assembly_v3.pipeline import refine_references
    state=dict(design_id="budget", storage_path=str(tmp_path), make="Ferrari", model="F40", year=1990,
               workflow_version="assembly_v3", scale="1:24")
    state.update(await refs.ReferenceImageService().generate(state))
    def exhausted(kind):
        raise BudgetExceeded("image call budget exhausted")
    state["consume_call"]=exhausted
    intent={"reference_conflicts":["hood_opening"], "reference_conflict_notes":["Window opens separately"],
            "detail_reference_requests":[dict(view="door_hinges",focus="Door pivot",angles=["inside"],modules=["doors"])]}
    result=await refine_references(state, {}, intent)
    assert result["unresolved_reference_views"]==["door_hinges","hood_opening"]
    assert result["reference_budget_issue"] and result["supplemented_views"]==[]
    assert len(state["reference_images"])==14
    assert image_api.images.edit.await_count==13


async def test_new_scale_can_correct_optional_view_inherited_from_previous_scale(tmp_path, image_api):
    state=dict(design_id="inherited",storage_path=str(tmp_path),make="Ferrari",model="F40",year=1990,
               workflow_version="assembly_v3",scale="1:24")
    await refs.ReferenceImageService().generate(state)
    state.update(scale="1:12",reference_corrections={"engine_details":"Reconcile engine trim with the overview"})
    result=await refs.ReferenceImageService().generate(state,only={"engine_details"})
    assert image_api.images.edit.await_count==14
    assert next(r for r in result["reference_images"] if r["view"]=="engine_details")["correction"]
    assert "suspension" not in {r["view"] for r in result["reference_images"]}
