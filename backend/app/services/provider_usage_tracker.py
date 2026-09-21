"""Records one ProviderUsage row per provider call: duration, success/
failure, error, and (when known) records returned / estimated cost. This
is the shared instrumentation point for cost tracking (section 50) and
provider health (section 53) — every real provider call in the codebase
should go through this, not just some.

Usage:
    async with ProviderUsageRecorder(
        session, provider="apollo", category=ProviderCategory.PERSON_DISCOVERY,
        operation="discover_people", workspace_id=workspace_id,
    ) as usage:
        result = await provider.discover_people(...)
        usage.records_returned = len(result)

On success, records success=True with duration measured across the block.
On a raised exception, records success=False with the exception message,
then re-raises — the caller decides whether that's fatal or a fallback
trigger.
"""
from __future__ import annotations

import time
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.providers.base import ProviderCategory
from app.repositories.provider_usage_repository import ProviderUsageRepository


class ProviderUsageRecorder:
    def __init__(
        self,
        session: AsyncSession,
        *,
        provider: str,
        category: ProviderCategory,
        operation: str,
        workspace_id: uuid.UUID | None = None,
        estimated_cost: float | None = None,
    ) -> None:
        self._session = session
        self._provider = provider
        self._category = category
        self._operation = operation
        self._workspace_id = workspace_id
        self.estimated_cost = estimated_cost
        self.records_returned: int | None = None
        self._start: float = 0.0

    async def __aenter__(self) -> "ProviderUsageRecorder":
        self._start = time.perf_counter()
        return self

    async def __aexit__(self, exc_type, exc_value, _traceback) -> bool:
        duration_ms = (time.perf_counter() - self._start) * 1000
        repo = ProviderUsageRepository(self._session)
        repo.create(
            provider=self._provider,
            category=self._category,
            operation=self._operation,
            workspace_id=self._workspace_id,
            success=exc_type is None,
            error=str(exc_value) if exc_value else None,
            duration_ms=duration_ms,
            records_returned=self.records_returned,
            estimated_cost=self.estimated_cost,
        )
        await self._session.flush()
        return False  # never suppress the exception
