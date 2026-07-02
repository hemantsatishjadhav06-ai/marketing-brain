"""Single source of env truth. Pydantic-settings v2."""
from __future__ import annotations

from typing import List
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # core
    JWT_SECRET: str = "dev-secret-change-me-please-use-secrets-token_urlsafe-48"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRES_DAYS: int = 30

    # db / queue
    DATABASE_URL: str = "postgresql+psycopg://brain:brain@postgres:5432/marketing_brain"
    REDIS_URL: str = "redis://redis:6379/0"

    # llm gateway
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_MODEL_REASONING: str = "anthropic/claude-sonnet-4.5"
    OPENROUTER_MODEL_DRAFTING: str = "anthropic/claude-haiku-4.5"

    # media
    FAL_KEY: str = ""

    # storage
    STORAGE_BACKEND: str = "local"  # local | s3 | r2
    STORAGE_LOCAL_PATH: str = "/app/storage"
    PUBLIC_BASE_URL: str = "http://localhost:8001"

    # s3/r2 storage
    S3_BUCKET: str = ""
    S3_REGION: str = "auto"
    S3_ENDPOINT_URL: str = ""           # blank for AWS, full URL for R2/MinIO
    S3_ACCESS_KEY: str = ""
    S3_SECRET_KEY: str = ""
    S3_PUBLIC_BASE_URL: str = ""        # CDN front for the bucket

    # billing
    STRIPE_SECRET_KEY: str = ""
    STRIPE_PRICE_ID: str = ""           # default monthly price for new orgs
    STRIPE_WEBHOOK_SECRET: str = ""

    # ops
    CORS_ORIGINS: str = "http://localhost:3006,http://localhost:3005,http://localhost:3000"
    WORKER_CONCURRENCY: int = 2

    # seed
    DEFAULT_OWNER_EMAIL: str = "owner@marketing-brain.local"
    DEFAULT_OWNER_PASSWORD: str = "changeme"
    DEFAULT_ORG_NAME: str = "Racket Sports Group"
    DEFAULT_MONTHLY_COST_CAP_USD: float = 200.0

    # data-source keys (optional)
    SERPAPI_KEY: str = ""
    YOUTUBE_API_KEY: str = ""
    SHOPIFY_WEBHOOK_SECRET: str = ""

    @property
    def cors_origins_list(self) -> List[str]:
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
