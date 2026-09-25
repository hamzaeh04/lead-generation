"""Singleton workspace API-key settings (one row per workspace)."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace_api_keys import WorkspaceApiKeys
from app.repositories.workspace_api_keys_repository import WorkspaceApiKeysRepository, _KEY_FIELDS
from app.schemas.workspace_api_keys import (
    WorkspaceApiKeysDefaults,
    WorkspaceApiKeysRead,
    WorkspaceApiKeysUpsert,
)


def get_defaults() -> WorkspaceApiKeysDefaults:
    return WorkspaceApiKeysDefaults()


def to_read(row: WorkspaceApiKeys) -> WorkspaceApiKeysRead:
    return WorkspaceApiKeysRead(
        id=row.id,
        workspace_id=row.workspace_id,
        has_apollo_api_key=bool(row.apollo_api_key),
        has_smartlead_api_key=bool(row.smartlead_api_key),
        has_anthropic_api_key=bool(row.anthropic_api_key),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _normalize_incoming(payload: WorkspaceApiKeysUpsert) -> dict[str, str]:
    """Only apply non-empty values the client sent — blank keeps the stored key."""
    data = payload.model_dump(exclude_unset=True)
    out: dict[str, str] = {}
    for field in _KEY_FIELDS:
        if field not in data:
            continue
        value = data[field]
        if value is None:
            continue
        trimmed = value.strip()
        if trimmed:
            out[field] = trimmed
    return out


class WorkspaceApiKeysService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = WorkspaceApiKeysRepository(session)

    async def get(self, workspace_id: uuid.UUID) -> WorkspaceApiKeys | None:
        return await self.repo.get_for_workspace(workspace_id)

    async def upsert(self, workspace_id: uuid.UUID, payload: WorkspaceApiKeysUpsert) -> WorkspaceApiKeys:
        fields = _normalize_incoming(payload)
        existing = await self.repo.get_for_workspace(workspace_id)
        if existing is None:
            return self.repo.create(
                workspace_id=workspace_id,
                **{f: fields.get(f) for f in _KEY_FIELDS},
            )

        for field_name, value in fields.items():
            setattr(existing, field_name, value)
        return existing
