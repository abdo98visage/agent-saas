import asyncio
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

from app.core.config import settings
from app.core.db import Base
import app.models  # Ensure all models are registered

# Windows compatibility for async Psycopg
if sys.platform == 'win32':
    import asyncio
    from asyncio import WindowsSelectorEventLoopPolicy
    asyncio.set_event_loop_policy(WindowsSelectorEventLoopPolicy())

# this is the Alembic Config object
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Set the sqlalchemy.url from our settings
config.set_main_option("sqlalchemy.url", settings.database_url)

# target_metadata is required for autogenerate
target_metadata = Base.metadata

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()

async def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    from sqlalchemy.ext.asyncio import create_async_engine
    
    async_engine = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
    )
    
    async with async_engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    
    await async_engine.dispose()

def context_run_migrations_online() -> None:
    """
    This is a wrapper to run the async run_migrations_online in a sync context.
    """
    asyncio.run(run_migrations_online())

if context.is_offline_mode():
    run_migrations_offline()
else:
    context_run_migrations_online()
