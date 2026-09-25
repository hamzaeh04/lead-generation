"""Application settings loaded from environment variables.

Never hard-code secrets here. All values come from the environment
(see .env.example) so credentials never end up in source control.
"""
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # App
    APP_NAME: str = "Lead Intelligence Platform"
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "development"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(..., description="Used to sign JWT access/refresh tokens")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = Field(..., description="postgresql+asyncpg://user:pass@host:port/db")

    # Redis / Celery
    REDIS_URL: str = "redis://localhost:6379/0"
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"

    # Provider credentials — all optional; a provider with no key is simply
    # unavailable (ProviderUnavailableError), never a hard startup failure.
    APOLLO_API_KEY: str | None = None
    SMARTLEAD_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    OPENAI_MODEL: str = "gpt-4o-mini"
    ANTHROPIC_API_KEY: str | None = None
    ANTHROPIC_MODEL: str = "claude-haiku-4-5-20251001"
    PROVIDER_HTTP_TIMEOUT_SECONDS: float = 15.0

    # SMTP (generic email-sending fallback — section 42)
    SMTP_HOST: str | None = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_USE_TLS: bool = True

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def ensure_asyncpg_driver(cls, v: str) -> str:
        """Hosts like Neon/Vercel often provide postgres:// or postgresql://
        which SQLAlchemy maps to sync psycopg2. This app uses create_async_engine,
        so force the asyncpg driver."""
        if not isinstance(v, str) or not v.strip():
            return v
        url = v.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        elif url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]
        # asyncpg uses `ssl=`, not libpq's sslmode=
        if "sslmode=" in url and "ssl=" not in url:
            url = url.replace("sslmode=require", "ssl=require").replace(
                "sslmode=verify-full", "ssl=require"
            )
        return url

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def default_broker(cls, v: str | None, info) -> str:
        return v or info.data.get("REDIS_URL", "redis://localhost:6379/0")

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def default_backend(cls, v: str | None, info) -> str:
        return v or info.data.get("REDIS_URL", "redis://localhost:6379/0")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
