import uuid
from collections.abc import AsyncGenerator
from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import AsyncSessionLocal
from app.core.security import decode_token
from app.models.user import User
from app.models.workspace import WorkspaceMember, WorkspaceRole
from app.repositories.user_repository import UserRepository
from app.repositories.workspace_repository import WorkspaceRepository
from app.services.rate_limiter import RateLimiter, get_rate_limiter
from app.services.token_revocation import TokenRevocationStore, get_token_revocation_store
from app.utils.db_errors import db_unavailable_payload, is_db_connectivity_error

bearer_scheme = HTTPBearer(auto_error=False)


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    try:
        async with AsyncSessionLocal() as session:
            yield session
    except Exception as exc:  # noqa: BLE001
        if is_db_connectivity_error(exc):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=db_unavailable_payload(exc),
            ) from exc
        raise


async def get_bearer_payload(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    revocation_store: TokenRevocationStore = Depends(get_token_revocation_store),
) -> dict[str, Any]:
    """Decodes and validates the access token, including a revocation
    check — split out from get_current_user so /logout can read the
    token's jti/exp without a duplicate decode."""
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated"
        )

    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    if await revocation_store.is_revoked(payload["jti"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token has been revoked")

    return payload


async def get_current_user(
    payload: dict[str, Any] = Depends(get_bearer_payload),
    session: AsyncSession = Depends(get_db_session),
) -> User:
    user = await UserRepository(session).get_by_id(uuid.UUID(payload["sub"]))
    if user is None or not user.is_active:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return user


def rate_limit(*, limit: int, window_seconds: int, scope: str):
    """Dependency factory: fixed-window rate limit keyed by client IP +
    scope. See app/services/rate_limiter.py for why IP rather than
    account is the key."""

    async def _check(
        request: Request,
        limiter: RateLimiter = Depends(get_rate_limiter),
    ) -> None:
        client_ip = request.client.host if request.client else "unknown"
        allowed = await limiter.check(
            f"{scope}:{client_ip}", limit=limit, window_seconds=window_seconds
        )
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests — try again later",
            )

    return _check


# Auth endpoints are the highest-value brute-force target; limits are
# deliberately generous (real users retry typos) rather than tight.
login_rate_limit = rate_limit(limit=10, window_seconds=60, scope="login")
register_rate_limit = rate_limit(limit=5, window_seconds=60, scope="register")
refresh_rate_limit = rate_limit(limit=30, window_seconds=60, scope="refresh")


async def require_workspace_member(
    workspace_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> WorkspaceMember:
    """Enforces multi-tenant isolation: the caller must belong to the
    workspace named in the request, or the request is rejected outright —
    never partially scoped, never inferred."""
    membership = await WorkspaceRepository(session).get_membership(
        workspace_id=workspace_id, user_id=current_user.id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Not a member of this workspace"
        )
    return membership


async def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


def require_workspace_role(*allowed_roles: WorkspaceRole):
    """Dependency factory: the caller must be a member of the workspace
    AND hold one of `allowed_roles`. Built on top of require_workspace_member
    rather than duplicating the membership lookup."""

    async def _check(
        membership: WorkspaceMember = Depends(require_workspace_member),
    ) -> WorkspaceMember:
        if membership.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires one of these workspace roles: {', '.join(r.value for r in allowed_roles)}",
            )
        return membership

    return _check


# Owner/admin/member can create and modify workspace-owned data; viewer is
# read-only. Not yet applied to every write endpoint in the codebase (see
# README §14) — applied to the highest-value ones: workspace member
# management, campaign lifecycle actions, and suppression creation.
require_workspace_editor = require_workspace_role(
    WorkspaceRole.OWNER, WorkspaceRole.ADMIN, WorkspaceRole.MEMBER
)
require_workspace_admin = require_workspace_role(WorkspaceRole.OWNER, WorkspaceRole.ADMIN)
require_workspace_owner = require_workspace_role(WorkspaceRole.OWNER)
