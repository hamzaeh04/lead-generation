"""Redis-backed fixed-window rate limiting (Phase 14).

Applied to auth endpoints (register/login/refresh) to slow down credential
stuffing / brute-force attempts. Keyed by client IP + endpoint scope, not
by account, so it can't be used to lock a legitimate user out by hammering
their email — the tradeoff is a shared IP (NAT, office network) shares one
budget, which is an acceptable default here, not a general-purpose API
gateway rate limiter.

When REDIS_URL is unset (typical on Vercel), limits are skipped so auth works.
"""
from __future__ import annotations

from typing import Protocol

import redis.asyncio as redis

from app.core.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)


class RateLimiter(Protocol):
    async def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Returns True if the call is allowed, False if the limit is exceeded."""
        ...


class RedisRateLimiter:
    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        redis_key = f"ratelimit:{key}"
        try:
            current = await self._client.incr(redis_key)
            if current == 1:
                await self._client.expire(redis_key, window_seconds)
            return current <= limit
        except Exception as exc:  # noqa: BLE001
            logger.warning("rate_limit_redis_unavailable", error=str(exc))
            return True


class AllowAllRateLimiter:
    async def check(self, key: str, *, limit: int, window_seconds: int) -> bool:
        return True


def _build_limiter() -> RateLimiter:
    settings = get_settings()
    redis_url = (settings.REDIS_URL or "").strip()
    local = "localhost" in redis_url or "127.0.0.1" in redis_url
    if not redis_url or (local and settings.ENVIRONMENT in {"production", "staging"}):
        logger.info("rate_limit_disabled", reason="redis_unset_or_local_in_production")
        return AllowAllRateLimiter()
    client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.5)
    return RedisRateLimiter(client)



_limiter: RateLimiter = _build_limiter()


async def get_rate_limiter() -> RateLimiter:
    return _limiter
