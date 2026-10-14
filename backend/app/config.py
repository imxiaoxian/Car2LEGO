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
    studio_ldraw_path: str = str(Path(__file__).resolve().parents[2] / "Studio 2.0" / "ldraw")

    # External APIs
    rebrickable_api_key: str = ""
    bricklink_api_key: str = ""
    bricklink_api_secret: str = ""

    # AI Providers
    ai_text_provider: str = "openai"
    ai_vision_provider: str = "openai"

    # Anthropic (backward compat)
    anthropic_api_key: str = ""
    anthropic_model: str = "claude-sonnet-4-6"
    anthropic_vision_model: str = "claude-sonnet-4-6"

    # Legacy provider settings retained for existing environment files.
    deepseek_api_key: str = ""
    deepseek_model: str = "deepseek-chat"
    # Both deepseek-chat and deepseek-v4-pro work. v4-pro needs:
    #   DEEPSEEK_MODEL=deepseek-v4-pro  (no tool_choice, auto-stripped by provider)
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_reasoning_effort: str = ""   # "high" | "medium" | "low" | "" — enables thinking mode (incompatible with structured output)

    # One OpenAI-compatible multimodal model for recognition, planning and design.
    openai_api_key: str = ""
    openai_model: str = "gpt-6.1-sol"
    openai_base_url: str = "https://api.lundong.ai/v1"
    openai_image_model: str = "gpt-image-2.5-sunburst"
    image_quality: str = "high"
    image_size: str = "1536x1024"
    image_timeout: float = 300.0

    # Legacy Doubao settings (generation uses the OpenAI factories).
    doubao_api_key: str = ""
    doubao_vision_model: str = "doubao-seed-2-1-pro-260628"
    doubao_base_url: str = "https://ark.cn-beijing.volces.com/api/v3"

    # LLM max output tokens (avoid hardcoding 8192 — let users tune per workload)
    text_max_tokens: int = 32768     # used by create_text_llm() across providers
    vision_max_tokens: int = 8192    # used by create_vision_llm() across providers

    # App
    app_name: str = "Car2LEGO API"
    debug: bool = True
    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # Design workflow version
    design_workflow: str = "assembly_v3"
    assembly_text_call_limit: int = 64
    assembly_text_retry_attempts: int = 3
    assembly_module_repair_limit: int = 3
    assembly_replan_limit: int = 2
    assembly_lease_seconds: int = 900
    assembly_external_checks_enabled: bool = True
    assembly_external_check_timeout_seconds: int = 300
    assembly_ldraw_mcp_python: str = ""
    assembly_ldraw_mcp_command: str = ""
    assembly_ldraw_mcp_blender: str = ""
    assembly_legolization_python: str = ""


settings = Settings()
