"""
Configuration management using Pydantic settings.
Loads environment variables and provides validated config access.
"""
from pydantic_settings import BaseSettings
from pydantic import SecretStr
from pathlib import Path
from typing import Optional
from urllib.parse import quote_plus

BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    """Application settings with environment variable support."""
    
    # API Configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_reload: bool = False
    
    # PostgreSQL Configuration
    postgres_user: str = "postgres"
    postgres_password: SecretStr = SecretStr("password")  # SecretStr safely handles special chars like $
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "multimodal_rag"
    
    # JWT Auth Configuration
    secret_key: str = "super-secret-key-please-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days
    
    # Qdrant Configuration
    qdrant_url: str = ""
    qdrant_api_key: str = ""
    qdrant_collection_name: str = "multimodal_collection"
    
    # External APIs
    openai_api_key: str = ""
    google_api_key: str = ""
    tavily_api_key: str = ""
    llama_cloud_api_key: str = ""
    
    # AWS S3 Configuration
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_region_name: str = "us-east-1"
    s3_bucket_name: str = "multimodal-rag-docs"
    
    @property
    def database_url(self) -> str:
        """
        Construct the asyncpg database URL.
        URL-encodes the password to safely handle special characters
        like #, $, @, % that would otherwise break the connection string.
        """
        password = quote_plus(self.postgres_password.get_secret_value())
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    model_config = {
        # Look for .env in project root (works locally and in Docker via --env-file)
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",  # Don't crash if .env has extra variables
    }

# Global settings instance
settings = Settings()
