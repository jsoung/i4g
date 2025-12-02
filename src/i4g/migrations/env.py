"""Alembic environment configuration for the i4g project."""

from __future__ import annotations

import os
from logging.config import fileConfig
from pathlib import Path
from typing import Any, Dict

from alembic import context
from sqlalchemy import engine_from_config, pool
from sqlalchemy.engine import Connection

from i4g.settings import get_settings
from i4g.store.sql import METADATA

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = METADATA


def _resolve_database_url() -> str:
    """Determine the database URL used for migrations."""

    override = os.getenv("I4G_DATABASE_URL") or os.getenv("ALEMBIC_DATABASE_URL")
    if override:
        return override

    settings = get_settings()
    sqlite_path = Path(settings.storage.sqlite_path)
    if not sqlite_path.is_absolute():
        sqlite_path = (Path(settings.project_root) / sqlite_path).resolve()
    normalized = sqlite_path.as_posix()
    return f"sqlite:///{normalized}"


def _prepare_config_section() -> Dict[str, Any]:
    """Update the Alembic config section with the resolved database URL."""

    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _resolve_database_url()
    return section


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    section = _prepare_config_section()
    url = section["sqlalchemy.url"]
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True, dialect_opts={"paramstyle": "named"})

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using a SQLAlchemy engine."""

    section = _prepare_config_section()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)

    with connectable.connect() as connection:  # type: ignore[assignment]
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


def main() -> None:
    """Entrypoint used by Alembic to execute migrations."""

    if context.is_offline_mode():
        run_migrations_offline()
    else:
        run_migrations_online()


main()
