"""Alembic env — async migrations against the jobify schema."""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

import sqlalchemy as sa
from alembic import context
from sqlalchemy.ext.asyncio import async_engine_from_config

from jobify.db.models import Base
from jobify.settings import Settings

config = context.config
if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _set_url() -> None:
    config.set_main_option("sqlalchemy.url", Settings().db_url)


def run_migrations_offline() -> None:
    _set_url()
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        include_schemas=True,
        version_table_schema="jobify",
    )
    with context.begin_transaction():
        context.run_migrations()


def _do_run_migrations(connection) -> None:
    connection.execute(sa.text("CREATE SCHEMA IF NOT EXISTS jobify"))
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_schemas=True,
        version_table_schema="jobify",
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    _set_url()
    cfg = config.get_section(config.config_ini_section) or {}
    cfg["sqlalchemy.url"] = config.get_main_option("sqlalchemy.url")
    engine = async_engine_from_config(cfg, prefix="sqlalchemy.")
    async with engine.connect() as connection:
        await connection.run_sync(_do_run_migrations)
        await connection.commit()
    await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
