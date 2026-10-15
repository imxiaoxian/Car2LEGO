"""Audited text/vision dialogue using the original project's API configuration."""
import base64
from io import BytesIO
import json
import os

from dotenv import dotenv_values
from PIL import Image

from .common import ROOT, write_json
from .gpt_reference import configuration


def settings():
    source, _ = configuration()
    inherited = dotenv_values(source / "backend/.env")
    local = dotenv_values(ROOT / ".env")
    def value(key, default=""):
        return os.environ.get(key) or local.get(key) or inherited.get(key) or default
    base = value("OPENAI_BASE_URL", "https://api.lundong.ai/v1").rstrip("/")
    return dict(api_key=value("OPENAI_API_KEY"), base_url=base if base.endswith("/v1") else base + "/v1",
                model=value("OPENAI_MODEL", "gpt-6.1-sol"))


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


def ask_json(messages, directory, name, max_tokens=16000, timeout=300, reuse_completed=False):
    from openai import OpenAI
    config = settings()
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
    write_json(directory / f"{name}-request.json", request)
    write_json(endpoint_path, endpoint)
    with OpenAI(**{k: v for k, v in config.items() if k != "model"}, timeout=timeout, max_retries=0) as client:
        response = client.responses.create(**request)
    raw = response.model_dump(mode="json")
    write_json(directory / f"{name}-response.json", raw)
    if response.status != "completed":
        raise ValueError(f"Model response did not complete: {response.status}.")
    return parse_json(response.output_text)


def parse_json(content):
    content = content or ""
    if content.lstrip().startswith("```"):
        content = "\n".join(content.strip().splitlines()[1:-1])
    return json.loads(content)
