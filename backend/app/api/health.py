import redis.asyncio as redis
from fastapi import APIRouter
from sqlalchemy import text

from app.core.config import get_settings
from app.core.database import AsyncSessionLocal
from app.utils.db_errors import sanitize_db_error
from app.utils.logging import get_logger
from app.utils.metrics import render_metrics

router = APIRouter(tags=["health"])
logger = get_logger(__name__)
settings = get_settings()


@router.get("/health")
async def health():
    """Liveness probe: process is up. No dependency checks."""
    return {"status": "ok"}


@router.get("/metrics")
async def metrics():
    """Prometheus scrape endpoint. Unauthenticated, like most metrics
    endpoints — restrict access at the reverse-proxy/network level in
    production (see README §16), not with app-level auth that a scraper
    can't easily present anyway."""
    return render_metrics()


@router.get("/ready")
async def ready():
    """Readiness probe: checks database and Redis connectivity.
    On failure, `errors` includes the sanitized root cause for debugging
    (e.g. Vercel ↔ Neon connection issues)."""
    checks: dict[str, str] = {}
    errors: dict[str, str] = {}

    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception as exc:  # noqa: BLE001
        logger.warning("readiness_check_failed", dependency="database", error=str(exc))
        checks["database"] = "unavailable"
        errors["database"] = sanitize_db_error(exc)

    redis_url = settings.REDIS_URL or ""
    local_redis = "localhost" in redis_url or "127.0.0.1" in redis_url
    if not redis_url or (local_redis and settings.ENVIRONMENT in {"production", "staging"}):
        checks["redis"] = "skipped"
    else:
        try:
            client = redis.from_url(redis_url)
            await client.ping()
            await client.aclose()
            checks["redis"] = "ok"
        except Exception as exc:  # noqa: BLE001
            logger.warning("readiness_check_failed", dependency="redis", error=str(exc))
            checks["redis"] = "unavailable"
            errors["redis"] = sanitize_db_error(exc)

    # Redis is optional — only database must be healthy for readiness.
    overall_ok = checks.get("database") == "ok"
    body: dict = {"status": "ok" if overall_ok else "degraded", "checks": checks}
    if errors:
        body["errors"] = errors
    return body
