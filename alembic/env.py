"""
Alembic environment configuration.
Supports async SQLAlchemy engine and reads DATABASE_URL from settings.
"""
from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import settings
from app.infrastructure.database.models import Base

# Alembic Config object
config = context.config

# Interpret the config file for Python logging.
# disable_existing_loggers=False: fileConfig's default (True) disables every logger not
# explicitly listed in alembic.ini's [loggers] section. Since migrations now run inside
# the app's own lifespan (see main.py), that would silently disable uvicorn's loggers —
# and app/infrastructure/observability/logging_config.py re-applies the app's own JSON
# formatter to the root logger right after migrations run, to undo the rest of fileConfig's
# handler/formatter reset.
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

# Set the target metadata for autogenerate support
target_metadata = Base.metadata

# Override sqlalchemy.url with the value from app settings
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (no DB connection needed)."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # Required for SQLite ALTER TABLE support
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode using async engine."""
    connectable = create_async_engine(settings.DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
