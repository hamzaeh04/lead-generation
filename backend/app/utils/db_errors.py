"""Helpers for surfacing database connectivity failures to API clients."""
from __future__ import annotations

import re
from typing import Any

from sqlalchemy.exc import DBAPIError, InterfaceError, OperationalError, SQLAlchemyError

_PASSWORD_IN_URL = re.compile(r"(://[^:/@]+):([^@/]+)(@)")


def sanitize_db_error(exc: BaseException) -> str:
    """Human-readable error text with credentials stripped from any URLs."""
    parts: list[str] = [str(exc)]
    cause = exc.__cause__ or getattr(exc, "orig", None)
    if cause is not None and str(cause) not in parts[0]:
        parts.append(str(cause))
    message = " | ".join(p for p in parts if p)
    message = _PASSWORD_IN_URL.sub(r"\1:***\3", message)
    return message[:800] if message else type(exc).__name__


def is_db_connectivity_error(exc: BaseException) -> bool:
    """True only for connection/auth/timeout failures — not missing tables/SQL bugs."""
    text = str(exc).lower()
    # Empty search_path → UndefinedTableError looks like a missing table; that is
    # not a connectivity failure.
    if "undefinedtable" in type(exc).__name__.lower() or (
        "does not exist" in text and "relation" in text
    ):
        return False
    if isinstance(exc, (OperationalError, InterfaceError, TimeoutError, ConnectionError, OSError)):
        return True
    if isinstance(exc, DBAPIError):
        markers = ("connection", "connect", "timeout", "refused", "ssl", "password", "auth", "operational")
        name = type(exc).__name__.lower()
        return any(m in name or m in text for m in markers)
    if isinstance(exc, SQLAlchemyError):
        name = type(exc).__name__.lower()
        markers = ("connection", "connect", "timeout", "refused", "ssl", "password", "auth", "operational")
        return any(m in name or m in text for m in markers)
    module = type(exc).__module__ or ""
    if module.startswith("asyncpg"):
        return any(m in text for m in ("connection", "timeout", "refused", "ssl", "password"))
    return False


def db_unavailable_payload(exc: BaseException) -> dict[str, Any]:
    return {
        "error": "database_unavailable",
        "issue": sanitize_db_error(exc),
    }
