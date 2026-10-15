"""Audited text/vision dialogue using the original project's API configuration."""
import base64
from io import BytesIO
import json
import os
import time

from dotenv import dotenv_values
from PIL import Image

from .common import ROOT, write_json
from .gpt_reference import configuration


def settings(model_key="OPENAI_MODEL", default_model="gpt-6.1-sol"):
    source, _ = configuration()
    inherited = dotenv_values(source / "backend/.env")
    local = dotenv_values(ROOT / ".env")
    def value(key, default=""):
        return os.environ.get(key) or local.get(key) or inherited.get(key) or default
    base = value("OPENAI_BASE_URL", "https://api.lundong.ai/v1").rstrip("/")
    return dict(api_key=value("OPENAI_API_KEY"), base_url=base if base.endswith("/v1") else base + "/v1",
                model=value(model_key, default_model))


def image_content(paths):
    content = []
    for label, path in paths.items():
        with Image.open(path) as image:
            image = image.convert("RGB")
            image.thumbnail((1200, 1200))
            stream = BytesIO()
            image.save(stream, format="JPEG", quality=92)
        content.extend([{"type": "text", "text": label}, {"type": "image_url", "image_url": {
            "url": "data:image/jpeg;base64," + base64.b64encode(stream.getvalue()).decode()}}])
    return content


def ask_json(messages, directory, name, max_tokens=16000, timeout=300, reuse_completed=False, *,
             model=None, stream=False, total_timeout=1800):
    from openai import OpenAI
    config = settings()
    if model is not None:
        config["model"] = model
    if not config["api_key"]:
        raise RuntimeError("OPENAI_API_KEY is missing from the original or experiment configuration.")
    # The gateway supports vision through Responses; validate plain JSON locally.
    inputs = []
    for message in messages:
        content = message["content"]
        if isinstance(content, list):
            content = [dict(type="input_text", text=c["text"]) if c["type"] == "text" else
                       dict(type="input_image", image_url=c["image_url"]["url"]) for c in content]
        inputs.append(dict(role=message["role"], content=content))
    request = dict(model=config["model"], input=inputs, max_output_tokens=max_tokens)
    if stream:
        request["stream"] = True
    directory.mkdir(parents=True, exist_ok=True)
    request_path = directory / f"{name}-request.json"
    response_path = directory / f"{name}-response.json"
    endpoint_path = directory / f"{name}-endpoint.json"
    endpoint = {"base_url": config["base_url"]}
    if reuse_completed and request_path.is_file() and response_path.is_file() and endpoint_path.is_file():
        from openai.types.responses import Response
        if (json.loads(request_path.read_text(encoding="utf-8")) == request
                and json.loads(endpoint_path.read_text(encoding="utf-8")) == endpoint):
            response = Response.model_validate(json.loads(response_path.read_text(encoding="utf-8")))
            if response.status == "completed":
                return parse_json(response.output_text)
    # A failed replacement request must never pair its inputs with an older completed reply.
    response_path.unlink(missing_ok=True)
    write_json(directory / f"{name}-request.json", request)
    write_json(endpoint_path, endpoint)
    if timeout <= 0 or total_timeout <= 0:
        raise ValueError("Model timeouts must be positive")
    with OpenAI(**{k: v for k, v in config.items() if k != "model"}, timeout=timeout, max_retries=0) as client:
        response = streamed_response(client, request, directory, name, total_timeout) if stream else client.responses.create(**request)
    raw = response.model_dump(mode="json")
    write_json(directory / f"{name}-response.json", raw)
    if response.status != "completed":
        raise ValueError(f"Model response did not complete: {response.status}.")
    return parse_json(response.output_text)


def streamed_response(client, request, directory, name, total_timeout):
    from openai.types.responses import Response
    started = time.monotonic()
    progress_path = directory / f"{name}-progress.json"
    progress = dict(status="connecting", model=request["model"], events=0, output_characters=0, seconds=0)
    write_json(progress_path, progress)
    response = None
    try:
        with (directory / f"{name}-events.jsonl").open("w", encoding="utf-8") as log:
            # Some compatible gateways omit response.created; require the authoritative terminal response.
            with client.responses.create(**request) as events:
                for event in events:
                    elapsed = time.monotonic() - started
                    progress.update(status="streaming", last_event=event.type, seconds=round(elapsed, 3),
                                    events=progress["events"] + 1)
                    if event.type == "response.output_text.delta":
                        progress["output_characters"] += len(event.delta)
                    if getattr(event, "response", None):
                        progress["response_id"] = event.response.id
                        if event.type in {"response.completed", "response.failed", "response.incomplete"}:
                            response = Response.model_validate(event.response.model_dump(mode="json"))
                    log.write(json.dumps(event.model_dump(mode="json"), ensure_ascii=False) + "\n")
                    log.flush()
                    write_json(progress_path, progress)
                    if elapsed > total_timeout:
                        raise TimeoutError(f"Model stream exceeded its {total_timeout}s total deadline")
                    if event.type == "error":
                        raise RuntimeError(f"Model stream error: {event.code}: {event.message}")
                    if response is not None:
                        break
        if response is None:
            raise RuntimeError("Model stream ended without a terminal response; partial output cannot be used")
        progress.update(status=response.status, seconds=round(time.monotonic() - started, 3))
        write_json(progress_path, progress)
        return response
    except Exception as error:
        progress.update(status="failed", error=type(error).__name__, seconds=round(time.monotonic() - started, 3))
        write_json(progress_path, progress)
        raise


def parse_json(content):
    content = content or ""
    if content.lstrip().startswith("```"):
        content = "\n".join(content.strip().splitlines()[1:-1])
    return json.loads(content)
