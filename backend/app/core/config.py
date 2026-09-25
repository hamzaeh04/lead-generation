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
    ENVIRONMENT: Literal["development", "test", "staging", "production"] = "production"
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = Field(..., description="Used to sign JWT access/refresh tokens")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    JWT_ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = Field(..., description="postgresql+asyncpg://user:pass@host:port/db")

    # Redis / Celery — optional. Leave unset on Vercel unless you attach Upstash/Redis.
    REDIS_URL: str | None = None
    CELERY_BROKER_URL: str | None = None
    CELERY_RESULT_BACKEND: str | None = None

    # CORS — comma-separated exact origins. Vercel *.vercel.app also allowed via regex in main.py.
    CORS_ORIGINS: str = "http://localhost:3000,https://lead-generation-backend-nu.vercel.app"

    # Publicly reachable base URL for this backend — required for Apollo's
    # phone-reveal webhook (see app/api/v1/webhooks.py), since Apollo must
    # be able to POST back to us from the outside. Locally this is
    # whatever ngrok (or similar) URL is currently proxying to this app;
    # unset means phone enrichment is unavailable, not a startup failure.
    PUBLIC_BASE_URL: str | None = None
    # Shared secret appended to the phone-reveal webhook URL as ?secret=
    # so a stranger who finds the endpoint can't POST fabricated phone
    # numbers onto real contacts. Unset means the webhook accepts anyone —
    # fine for a quick local test, not for anything public-facing.
    APOLLO_WEBHOOK_SECRET: str | None = None

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
        so force the asyncpg driver and strip libpq-only query params asyncpg
        rejects (e.g. channel_binding, sslmode)."""
        if not isinstance(v, str) or not v.strip():
            return v

        from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

        url = v.strip()
        if url.startswith("postgres://"):
            url = "postgresql://" + url[len("postgres://") :]
        if url.startswith("postgresql://"):
            url = "postgresql+asyncpg://" + url[len("postgresql://") :]
        elif url.startswith("postgresql+psycopg2://"):
            url = "postgresql+asyncpg://" + url[len("postgresql+psycopg2://") :]

        parsed = urlparse(url)
        query: list[tuple[str, str]] = []
        has_ssl = False
        for key, value in parse_qsl(parsed.query, keep_blank_values=True):
            lowered = key.lower()
            if lowered in {"channel_binding"}:
                continue
            if lowered == "sslmode":
                query.append(("ssl", "require" if value in {"require", "verify-full", "verify-ca"} else value))
                has_ssl = True
                continue
            if lowered == "ssl":
                has_ssl = True
            query.append((key, value))
        if not has_ssl and "neon.tech" in (parsed.hostname or ""):
            query.append(("ssl", "require"))

        return urlunparse(parsed._replace(query=urlencode(query)))

    @field_validator("CELERY_BROKER_URL", mode="before")
    @classmethod
    def default_broker(cls, v: str | None, info) -> str | None:
        return v or info.data.get("REDIS_URL")

    @field_validator("CELERY_RESULT_BACKEND", mode="before")
    @classmethod
    def default_backend(cls, v: str | None, info) -> str | None:
        return v or info.data.get("REDIS_URL")

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
