import os
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.config import get_settings  # noqa: E402
from app.core.database import Base  # noqa: E402
from app.models import *  # noqa: E402,F401,F403  (registers models on Base.metadata)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

settings = get_settings()
# Alembic runs migrations synchronously; swap the async driver for psycopg2.
# App Settings maps Neon sslmode→ssl for asyncpg; psycopg2 needs sslmode back.
sync_url = settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

_parsed = urlparse(sync_url)
_query: list[tuple[str, str]] = []
for key, value in parse_qsl(_parsed.query, keep_blank_values=True):
    if key.lower() == "ssl":
        _query.append(("sslmode", "require" if value in {"1", "true", "require"} else value))
    else:
        _query.append((key, value))
sync_url = urlunparse(_parsed._replace(query=urlencode(_query)))
config.set_main_option("sqlalchemy.url", sync_url)


target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
