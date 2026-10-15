from unittest.mock import MagicMock, patch

import pytest
from openai.types.responses import Response

from car2lego3d import dialogue
from car2lego3d.common import write_json


CONFIG = dict(api_key="test-only", base_url="https://api.example/v1", model="test-model")
MESSAGES = [dict(role="user", content="vehicle dimensions")]


def response(status="completed"):
    return Response.model_validate(dict(id="resp_test", created_at=1, model="test-model", object="response",
        status=status, output=[dict(id="msg_test", type="message", role="assistant", status="completed",
            content=[dict(type="output_text", text='{"length": 5103}', annotations=[])])],
        parallel_tool_calls=False, tool_choice="auto", tools=[]))


@pytest.mark.parametrize("change", [None, "endpoint", "model", "prompt", "incomplete"])
def test_resume_requires_identical_request_endpoint_and_completed_response(tmp_path, change):
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.create.return_value = response()
    with patch.object(dialogue, "settings", return_value=CONFIG.copy()) as settings, patch("openai.OpenAI", return_value=client):
        assert dialogue.ask_json(MESSAGES, tmp_path, "test") == {"length": 5103}
        assert "tools" not in client.responses.create.call_args.kwargs
        messages = MESSAGES
        if change == "endpoint": settings.return_value["base_url"] = "https://other.example/v1"
        if change == "model": settings.return_value["model"] = "other-model"
        if change == "prompt": messages = [dict(role="user", content="different vehicle")]
        if change == "incomplete": write_json(tmp_path / "test-response.json", response("incomplete").model_dump(mode="json"))
        assert dialogue.ask_json(messages, tmp_path, "test", reuse_completed=True) == {"length": 5103}
        assert client.responses.create.call_count == (1 if change is None else 2)


def test_incomplete_reply_is_retained_but_not_parsed(tmp_path):
    client = MagicMock()
    client.__enter__.return_value = client
    client.responses.create.return_value = response("incomplete")
    with patch.object(dialogue, "settings", return_value=CONFIG), patch("openai.OpenAI", return_value=client):
        with pytest.raises(ValueError, match="did not complete"):
            dialogue.ask_json(MESSAGES, tmp_path, "test")
    assert (tmp_path / "test-response.json").is_file()
