import os
from collections.abc import AsyncGenerator

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# Vercel (and other serverless) must not keep a process-wide connection pool —
# each invocation should open/close connections. NullPool does that.
_engine_kwargs: dict = {"pool_pre_ping": True, "echo": settings.DEBUG}
if os.getenv("VERCEL") or os.getenv("AWS_LAMBDA_FUNCTION_NAME"):
    _engine_kwargs["poolclass"] = NullPool

# Neon pooler (PgBouncer) + asyncpg: disable statement cache, and force
# search_path=public. pg_dump sets search_path='' for the import session; that
# empty path can stick on pooled backends so unqualified ORM tables (users)
# raise UndefinedTableError even though public.users exists.
_connect_args: dict = {}
_db_url = settings.DATABASE_URL or ""
_is_neon_pooler = "neon.tech" in _db_url or "-pooler." in _db_url
if _is_neon_pooler:
    _connect_args["statement_cache_size"] = 0
    _connect_args["server_settings"] = {"search_path": "public"}
if _connect_args:
    _engine_kwargs["connect_args"] = _connect_args

engine = create_async_engine(settings.DATABASE_URL, **_engine_kwargs)

if _is_neon_pooler:

    @event.listens_for(engine.sync_engine, "connect")
    def _force_public_search_path(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
        # Belt-and-suspenders: pooler backends can retain empty search_path
        # from pg_dump sessions even when server_settings is set.
        cursor = dbapi_connection.cursor()
        cursor.execute("SET search_path TO public")
        cursor.close()


AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
