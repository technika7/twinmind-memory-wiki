"""
Application configuration via Pydantic Settings.

All values are loaded from environment variables (or .env file).
"""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # ── App ────────────────────────────────────────────────────
    app_env: str = "development"
    log_level: str = "INFO"

    # ── Database ───────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://memorywiki:memorywiki@postgres:5432/memorywiki"
    database_url_sync: str = "postgresql+psycopg2://memorywiki:memorywiki@postgres:5432/memorywiki"

    # ── Redis / Celery ─────────────────────────────────────────
    celery_broker_url: str = "redis://redis:6379/0"
    celery_result_backend: str = "redis://redis:6379/1"

    # ── MinIO (S3-compatible) ──────────────────────────────────
    s3_endpoint_url: str = "http://minio:9000"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket_name: str = "memories"
    s3_region: str = "us-east-1"

    # ── LLM ────────────────────────────────────────────────────
    openai_api_key: str = ""
    llm_model: str = "gpt-4o"

    model_config = {"env_file": ".env", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    """Cached settings singleton."""
    return Settings()
