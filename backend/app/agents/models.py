"""Shared OpenAI-compatible model for every language and vision workload."""

from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import RunnableLambda

from app.config import settings


class GatewayChatOpenAI(ChatOpenAI):
    """Validate structured JSON locally without gateway tool-call extensions.

    This gateway accepts text and images but returns an upstream 500 when tools
    are supplied. No hidden retry or different model is used by this adapter.
    Invalid JSON and schema violations remain explicit failures.
    """
    def with_structured_output(self, schema, *, method=None, include_raw=False, **kwargs):
        if include_raw or not hasattr(schema, "model_json_schema"):
            raise ValueError("Gateway structured output requires a Pydantic schema")
        parser = PydanticOutputParser(pydantic_object=schema)
        instructions = "Return only one JSON object. Follow this schema exactly. " + parser.get_format_instructions()
        def prepare(value):
            messages = value.to_messages() if hasattr(value, "to_messages") else self._convert_input(value).to_messages()
            return [SystemMessage(content=instructions), *messages]
        return RunnableLambda(prepare) | self | parser


def openai_base_url() -> str:
    """Accept either the gateway origin or its /v1 API root."""
    url = settings.openai_base_url.rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"


def _create_llm(max_tokens: int) -> BaseChatModel:
    if not settings.openai_api_key:
        raise ValueError("OPENAI_API_KEY not configured")
    return GatewayChatOpenAI(
        api_key=settings.openai_api_key,
        base_url=openai_base_url(),
        model=settings.openai_model,
        max_tokens=max_tokens,
        timeout=180,
        max_retries=0,
    )


def create_text_llm(max_tokens: int | None = None) -> BaseChatModel:
    return _create_llm(min(max_tokens, settings.text_max_tokens) if max_tokens else settings.text_max_tokens)


def create_vision_llm() -> BaseChatModel:
    return _create_llm(settings.vision_max_tokens)
