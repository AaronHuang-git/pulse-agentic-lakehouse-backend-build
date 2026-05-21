"""Centralized settings loaded from environment variables."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Postgres
    postgres_user: str = Field(default="pulse")
    postgres_password: str = Field(default="pulse_dev_password")
    postgres_db: str = Field(default="pulse")
    postgres_host: str = Field(default="postgres")
    postgres_port: int = Field(default=5432)

    # MinIO
    minio_endpoint: str = Field(default="minio:9000")
    minio_root_user: str = Field(default="pulse")
    minio_root_password: str = Field(default="pulse_dev_password")
    minio_bucket: str = Field(default="pulse")

    # App
    pulse_env: str = Field(default="development")
    pulse_log_level: str = Field(default="INFO")

    # Agent
    anthropic_api_key: str = Field(default="")
    pulse_agent_provider: str = Field(default="mock")  # "anthropic" or "mock"
    pulse_agent_model: str = Field(default="claude-haiku-4-5-20251001")

    # Inter-service URLs (used by agent to call query)
    query_service_url: str = Field(default="http://query:8002")

    @property
    def postgres_dsn_async(self) -> str:
        return (
            f"postgresql+asyncpg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    @property
    def postgres_dsn_sync(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
