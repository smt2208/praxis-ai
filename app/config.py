"""
app/config.py

Centralized application settings loaded from environment variables / .env file.
All secrets and external service keys live here — never hardcoded in business logic.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


# Default LLM model used across all agents — change once here to update everywhere
DEFAULT_MODEL = "gpt-5.4-mini-2026-03-17"


class Settings(BaseSettings):
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # PostgreSQL
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str

    # Qdrant
    qdrant_url: str
    qdrant_api_key: str
    qdrant_collection_name: str = "collection"

    # OpenAI
    openai_api_key: str

    # Tavily
    tavily_api_key: str

    # LlamaCloud
    llama_cloud_api_key: str

    # JWT
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # LangSmith Tracing (optional — leave blank to disable)
    langchain_tracing_v2: str = "true"
    langchain_api_key: str = ""
    langchain_project: str = "praxis-ai"

    # Email Verification (Resend)
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@praxisapp.online"
    resend_from_name: str = "Praxis"
    app_base_url: str = "https://praxisapp.online"

    # Context Limits
    max_context_chars: int = 120000

    # Mem0 Long-Term Memory
    mem0_collection_name: str = "praxis_memories"

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
