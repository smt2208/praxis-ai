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

    # Supabase (optional — for future auth/REST integration)
    supabase_url: str = ""
    supabase_anon_key: str = ""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")




@lru_cache
def get_settings() -> Settings:
    return Settings()
