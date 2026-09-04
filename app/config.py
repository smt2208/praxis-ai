"""
app/config.py

Centralized application configuration loaded from environment variables and .env.
Structured into logical domains: Server, Database, AI Providers, Auth, Email & Observability.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


# Global Model Identifiers
DEFAULT_MODEL: str = "gpt-5.4-mini-2026-03-17"  # Primary multi-agent reasoning model
FAST_MODEL: str = "gpt-5.4-nano"                # Lightweight evaluator / quality gate model


class Settings(BaseSettings):
    # ── Server & Runtime ──────────────────────────────────────────────────────
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    app_base_url: str = "https://praxisapp.online"
    max_context_chars: int = 120000

    # ── Security & Authentication (JWT) ───────────────────────────────────────
    secret_key: str
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # ── PostgreSQL Database (AWS RDS) ─────────────────────────────────────────
    postgres_user: str
    postgres_password: str
    postgres_host: str
    postgres_port: int = 5432
    postgres_db: str

    # ── Vector Database (Qdrant) ──────────────────────────────────────────────
    qdrant_url: str
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "collection"

    # ── AI & Agent Providers ──────────────────────────────────────────────────
    openai_api_key: str
    llama_cloud_api_key: str = ""
    mem0_collection_name: str = "praxis_memories"

    # ── Email Service (Resend) ────────────────────────────────────────────────
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@praxisapp.online"
    resend_from_name: str = "Praxis"

    # ── Observability & Tracing (LangSmith) ────────────────────────────────────
    langchain_tracing_v2: str = "false"
    langchain_api_key: str = ""
    langchain_project: str = "praxis-ai"

    # ── Legacy / Optional ─────────────────────────────────────────────────────
    tavily_api_key: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()

