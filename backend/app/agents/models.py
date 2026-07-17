"""LangChain ChatModel factory.

Replaces the custom `BaseLLMProvider` abstraction with idiomatic LangChain
ChatModel instances. Each call site picks a provider via env var:

- `AI_TEXT_PROVIDER`  → `create_text_llm()`  (used by design + customization graphs)
- `AI_VISION_PROVIDER` → `create_vision_llm()` (used by vision graph)

DeepSeek and Doubao are OpenAI-API-compatible, so they reuse `ChatOpenAI`
with a custom `base_url`. Anthropic is the legacy fallback via `ChatAnthropic`.

The previously-dead `deepseek_reasoning_effort` setting (config.py:44) is
now plumbed through via `model_kwargs`, fixing Phase 0 bug #4.
"""

from langchain_core.language_models import BaseChatModel
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI

from app.config import settings


def create_text_llm() -> BaseChatModel:
    """Build the text-generation ChatModel (DeepSeek default).

    Raises ValueError if the selected provider has no API key configured.
    """
    provider = settings.ai_text_provider.lower()

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            raise ValueError("DEEPSEEK_API_KEY not configured")
        base_url = settings.deepseek_base_url.rstrip("/")
        if not base_url.endswith("/v1"):
            base_url = base_url + "/v1"
        kwargs = {
            "api_key": settings.deepseek_api_key,
            "base_url": base_url,
            "model": settings.deepseek_model,
            "max_tokens": 32768,
        }
        if settings.deepseek_reasoning_effort:
            kwargs["reasoning_effort"] = settings.deepseek_reasoning_effort
        return ChatOpenAI(**kwargs)

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_text_model,
            max_tokens=16384,
        )

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
            max_tokens=16384,
        )

    raise ValueError(f"Unknown AI_TEXT_PROVIDER: {provider!r}")


def create_vision_llm() -> BaseChatModel:
    """Build the vision-analysis ChatModel (Doubao default).

    Raises ValueError if the selected provider has no API key configured.
    """
    provider = settings.ai_vision_provider.lower()

    if provider == "doubao":
        if not settings.doubao_api_key:
            raise ValueError("DOUBAO_API_KEY not configured")
        return ChatOpenAI(
            api_key=settings.doubao_api_key,
            base_url=settings.doubao_base_url,
            model=settings.doubao_vision_model,
            max_tokens=8192,
        )

    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("OPENAI_API_KEY not configured")
        return ChatOpenAI(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.openai_vision_model,
            max_tokens=8192,
        )

    if provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError("ANTHROPIC_API_KEY not configured")
        return ChatAnthropic(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_vision_model,
            max_tokens=8192,
        )

    raise ValueError(f"Unknown AI_VISION_PROVIDER: {provider!r}")
