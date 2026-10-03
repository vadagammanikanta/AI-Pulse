"""
AI Pulse — application settings.

All values come from environment variables / .env file.
Nothing is hardcoded — model names, limits, and thresholds are all configurable.
"""
import json
from typing import Annotated, Any
from pydantic import Field, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Security ──────────────────────────────────────────────────────────────
    api_secret_key: str = Field(..., description="X-API-Key value for all protected endpoints")

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data/aipulse.db",
        description="SQLite URL. Format: sqlite+aiosqlite:///./relative/path.db",
    )

    # ── LLM providers ─────────────────────────────────────────────────────────
    # Provider priority order (comma-separated).  Providers with no API key
    # are skipped automatically.
    llm_provider_order: list[str] = Field(
        default=["groq", "gemini", "ollama"],
        description="Fallback order for LLM providers",
    )

    @field_validator("llm_provider_order", mode="before")
    @classmethod
    def parse_provider_order(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            v = v.strip()
            if v.startswith("[") and v.endswith("]"):
                try:
                    return json.loads(v)
                except Exception:
                    pass
            return [s.strip() for s in v.split(",") if s.strip()]
        return v

    # Groq
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_rpm: int = Field(default=30, description="Groq requests per minute limit")
    groq_daily_limit: int = Field(default=14400, description="Groq daily request budget")

    # Gemini
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.8-flash"
    gemini_rpm: int = Field(default=15, description="Gemini requests per minute limit")
    gemini_daily_limit: int = Field(default=1500, description="Gemini daily request budget")

    # Ollama (local — no key, effectively unlimited)
    ollama_base_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.2"
    ollama_rpm: int = Field(default=60, description="Ollama requests per minute limit")
    ollama_daily_limit: int = Field(default=999999, description="Ollama daily request budget")

    # ── Embeddings ────────────────────────────────────────────────────────────
    embedding_model: str = "all-MiniLM-L6-v2"
    embedding_dims: int = 384

    # ── Pipeline & Scheduler ──────────────────────────────────────────────────
    enable_in_process_scheduler: bool = Field(default=True, description="Enable internal APScheduler inside FastAPI process")
    top_n_per_run: int = Field(default=20, ge=1, le=500)
    pre_score_threshold: int = Field(default=40, ge=0, le=100)
    llm_batch_size: int = Field(default=4, ge=1, le=20)
    pipeline_interval_hours: int = Field(default=6, ge=1)
    prompt_reprocess_window_days: int = Field(default=14, ge=1)
    filtered_log_max_entries: int = Field(default=200, ge=1)
    feed_score_weight_importance: float = Field(default=0.6, ge=0.0, le=1.0)
    feed_score_weight_interest: float = Field(default=0.3, ge=0.0, le=1.0)
    feed_score_weight_recency: float = Field(default=0.1, ge=0.0, le=1.0)
    recency_half_life_hours: float = Field(default=48.0, gt=0.0)
    search_min_cosine_threshold: float = Field(default=0.20, ge=0.0, le=1.0)
    interest_keywords: list[str] = Field(
        default=[
            "gpt", "claude", "gemini", "llama", "mistral", "deepseek", "qwen",
            "phi", "gemma", "mcp", "fastapi", "vllm", "mlx", "speculative decoding",
            "quantization", "gguf", "dpo", "grpo", "fine tuning", "rag"
        ],
        description="Family names, tools, and technical topics that elevate arXiv paper score above 60",
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_digest_time: str = Field(default="08:00", description="Daily digest dispatch time in HH:MM format")
    telegram_digest_timezone: str = Field(default="Asia/Kolkata", description="Timezone for daily Telegram digest")

    # ── App ───────────────────────────────────────────────────────────────────
    log_level: str = "INFO"
    app_name: str = "AI Pulse"
    app_version: str = "0.1.0"

    # ── Derived ───────────────────────────────────────────────────────────────
    @computed_field
    @property
    def db_path(self) -> str:
        """Filesystem path extracted from DATABASE_URL."""
        prefix = "sqlite+aiosqlite:///"
        if not self.database_url.startswith(prefix):
            raise ValueError(f"Only SQLite is supported. Got: {self.database_url}")
        path = self.database_url[len(prefix):]
        return path if path else ":memory:"

    def provider_api_key(self, provider: str) -> str | None:
        return {"groq": self.groq_api_key, "gemini": self.gemini_api_key, "ollama": "local"}.get(provider)

    def active_providers(self) -> list[str]:
        """Return providers that have a key configured, in priority order."""
        return [p for p in self.llm_provider_order if self.provider_api_key(p) is not None]


# Module-level singleton — import this everywhere.
settings = Settings()
