"""Application configuration loaded from environment variables."""

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql+asyncpg://car2lego:car2lego@localhost:5432/car2lego"
    database_url_sync: str = "postgresql://car2lego:car2lego@localhost:5432/car2lego"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Storage
    storage_path: str = str(Path(__file__).parent.parent / "storage")

    # External APIs
    rebrickable_api_key: str = ""
    bricklink_api_key: str = ""
    bricklink_api_secret: str = ""

    # AI Providers
    ai_text_provider: str = "deepseek"       # "deepseek" | "anthropic" | "openai"
    ai_vision_provider: str = "doubao"        # "doubao" | "openai" | "anthropic"

    # Anthropic (backward compat)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_vision_model: str = "claude-sonnet-4-6"

    # DeepSeek (default for text generation)
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    # Both deepseek-chat and deepseek-v4-pro work. v4-pro needs:
    #   DEEPSEEK_MODEL=deepseek-v4-pro  (no tool_choice, auto-stripped by provider)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_reasoning_effort: str = ""   # "high" | "medium" | "low" | "" — enables thinking mode (incompatible with structured output)

    # OpenAI (for vision analysis)
    openai_api_key: str = ""
    openai_vision_model: str = "gpt-4o"
    openai_text_model: str = "gpt-4o-mini"
    openai_base_url: str = "https://api.openai.com/v1"

    # Doubao / ByteDance Volcano Engine (for vision analysis)
    doubao_api_key: str = ""
    doubao_vision_model: str = "doubao-seed-2-1-pro-260628"
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # App
    app_name: str = "Car2LEGO API"
    debug: bool = True
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]


settings = Settings()
