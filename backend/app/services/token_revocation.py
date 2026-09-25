"""Server-side JWT revocation (Phase 14).

JWTs are stateless by design, so "logging out" previously did nothing
server-side (see README §16, prior gap). Every access/refresh token now
carries a unique `jti`; revoking one records that `jti` here until its
original expiry, after which the record is dropped automatically — never
grown unbounded.

When REDIS_URL is unset, revocation is a no-op so auth still works on Vercel.
"""
from __future__ import annotations

from typing import Protocol

import redis.asyncio as redis

from app.core.config import get_settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

_KEY_PREFIX = "revoked_jti:"


class TokenRevocationStore(Protocol):
    async def revoke(self, jti: str, ttl_seconds: int) -> None: ...

    async def is_revoked(self, jti: str) -> bool: ...


class RedisTokenRevocationStore:
    def __init__(self, client: "redis.Redis") -> None:
        self._client = client

    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        try:
            await self._client.set(f"{_KEY_PREFIX}{jti}", "1", ex=ttl_seconds)
        except Exception as exc:  # noqa: BLE001
            logger.warning("token_revoke_redis_unavailable", error=str(exc))

    async def is_revoked(self, jti: str) -> bool:
        try:
            return bool(await self._client.exists(f"{_KEY_PREFIX}{jti}"))
        except Exception as exc:  # noqa: BLE001
            logger.warning("token_revocation_check_redis_unavailable", error=str(exc))
            return False


class NoOpTokenRevocationStore:
    async def revoke(self, jti: str, ttl_seconds: int) -> None:
        return None

    async def is_revoked(self, jti: str) -> bool:
        return False


def _build_store() -> TokenRevocationStore:
    settings = get_settings()
    redis_url = (settings.REDIS_URL or "").strip()
    local = "localhost" in redis_url or "127.0.0.1" in redis_url
    if not redis_url or (local and settings.ENVIRONMENT in {"production", "staging"}):
        logger.info("token_revocation_disabled", reason="redis_unset_or_local_in_production")
        return NoOpTokenRevocationStore()
    client = redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=0.5)
    return RedisTokenRevocationStore(client)



_store: TokenRevocationStore = _build_store()


async def get_token_revocation_store() -> TokenRevocationStore:
    return _store
