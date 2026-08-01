from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    access_token_expire_minutes: int = 30        # 30 minutes — keep short
    refresh_token_expire_days: int = 7           # 7 days — stored in DB


    # Email Verification (Resend)
    resend_api_key: str = "re_KJWEqzRN_Hdv9Q4yGT1Z9S5SyCz18vGAx"           # Get from https://resend.com — leave empty to skip sending
    app_base_url: str = "https://praxis-ai-nine.vercel.app"  # Frontend origin for email verification link


    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
