import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.workspace_api_keys import WorkspaceApiKeys

_KEY_FIELDS = (
    "apollo_api_key",
    "smartlead_api_key",
    "anthropic_api_key",
)


class WorkspaceApiKeysRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_for_workspace(self, workspace_id: uuid.UUID) -> WorkspaceApiKeys | None:
        result = await self.session.execute(
            select(WorkspaceApiKeys).where(WorkspaceApiKeys.workspace_id == workspace_id)
        )
        return result.scalar_one_or_none()

    def create(self, workspace_id: uuid.UUID, **fields: Any) -> WorkspaceApiKeys:
        row = WorkspaceApiKeys(workspace_id=workspace_id, **fields)
        self.session.add(row)
        return row
