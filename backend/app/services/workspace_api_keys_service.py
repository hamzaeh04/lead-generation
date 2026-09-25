"""Singleton workspace API-key settings (one row per workspace)."""
from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.models.workspace_api_keys import WorkspaceApiKeys
from app.repositories.workspace_api_keys_repository import WorkspaceApiKeysRepository, _KEY_FIELDS
from app.schemas.workspace_api_keys import (
    WorkspaceApiKeysDefaults,
    WorkspaceApiKeysRead,
    WorkspaceApiKeysUpsert,
)

# Maps workspace_api_keys columns → Settings / .env attribute names.
_ENV_ATTR_BY_FIELD: dict[str, str] = {
    "apollo_api_key": "APOLLO_API_KEY",
    "smartlead_api_key": "SMARTLEAD_API_KEY",
    "anthropic_api_key": "ANTHROPIC_API_KEY",
}


def get_defaults(settings: Settings | None = None) -> WorkspaceApiKeysDefaults:
    """Form placeholders: prefer live .env values when set, else generic hints."""
    settings = settings or get_settings()
    return WorkspaceApiKeysDefaults(
        apollo_api_key=(settings.APOLLO_API_KEY or "").strip() or "your-apollo-api-key",
        smartlead_api_key=(settings.SMARTLEAD_API_KEY or "").strip() or "your-smartlead-api-key",
        anthropic_api_key=(settings.ANTHROPIC_API_KEY or "").strip() or "your-anthropic-api-key",
    )


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


def _env_key_values(settings: Settings) -> dict[str, str]:
    out: dict[str, str] = {}
    for field, attr in _ENV_ATTR_BY_FIELD.items():
        value = getattr(settings, attr, None)
        if isinstance(value, str) and value.strip():
            out[field] = value.strip()
    return out


class WorkspaceApiKeysService:
    def __init__(self, session: AsyncSession, settings: Settings | None = None) -> None:
        self.session = session
        self.repo = WorkspaceApiKeysRepository(session)
        self.settings = settings or get_settings()

    async def get(self, workspace_id: uuid.UUID) -> WorkspaceApiKeys | None:
        return await self.repo.get_for_workspace(workspace_id)

    async def get_or_seed_from_env(self, workspace_id: uuid.UUID) -> WorkspaceApiKeys | None:
        """Return the workspace row, creating/filling missing keys from .env when present.

        Resolution for runtime calls stays DB-first then .env (provider_factory).
        This only *stores* env keys into the DB so Settings UI shows them as set.
        """
        env_keys = _env_key_values(self.settings)
        existing = await self.repo.get_for_workspace(workspace_id)
        if existing is None:
            if not env_keys:
                return None
            return self.repo.create(
                workspace_id=workspace_id,
                **{f: env_keys.get(f) for f in _KEY_FIELDS},
            )

        filled = False
        for field in _KEY_FIELDS:
            current = getattr(existing, field, None)
            if isinstance(current, str) and current.strip():
                continue
            if field in env_keys:
                setattr(existing, field, env_keys[field])
                filled = True
        return existing

    async def upsert(self, workspace_id: uuid.UUID, payload: WorkspaceApiKeysUpsert) -> WorkspaceApiKeys:
        fields = _normalize_incoming(payload)
        existing = await self.repo.get_for_workspace(workspace_id)
        if existing is None:
            # First save: merge explicit form values over .env defaults.
            seed = _env_key_values(self.settings)
            seed.update(fields)
            return self.repo.create(
                workspace_id=workspace_id,
                **{f: seed.get(f) for f in _KEY_FIELDS},
            )

        for field_name, value in fields.items():
            setattr(existing, field_name, value)
        return existing
