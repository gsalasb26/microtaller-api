"""Alembic environment configuration — MicroTaller.

Supports async SQLAlchemy (asyncpg) via asyncio.run().
The database URL is read directly from app/config.py so it always
matches the application settings (or the .env file / environment variables).
"""
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

# ---------------------------------------------------------------------------
# Import Base and ALL models so Alembic's autogenerate can detect every table.
# Adding a new model? Import it here too.
# ---------------------------------------------------------------------------
from app.database import Base  # noqa: E402
from app.models import (  # noqa: F401
    Currency,
    Customer,
    FuelLevel,
    Reception,
    ReceptionDetail,
    ReceptionStatus,
    Vehicle,
    VehicleType,
    WorkOrder,
    WorkOrderLine,
    WorkOrderStatus,
    WorkType,
)

# ---------------------------------------------------------------------------
# Override the sqlalchemy.url from app settings / environment variables.
# This guarantees that alembic always uses the same connection string as the
# running application without duplicating values in alembic.ini.
# ---------------------------------------------------------------------------
from app.config import settings  # noqa: E402

# ---------------------------------------------------------------------------
# Standard Alembic boilerplate
# ---------------------------------------------------------------------------
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Inject the real database URL (overrides any value in alembic.ini)
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

# The metadata object that autogenerate compares against
target_metadata = Base.metadata


# ---------------------------------------------------------------------------
# Offline mode — generates SQL without connecting to the database
# ---------------------------------------------------------------------------
def run_migrations_offline() -> None:
    """Run migrations without a live DB connection.

    Useful for previewing SQL or deploying to environments where a direct
    DB connection is not available at migration time.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # Render CHECK constraints defined at the model level
        render_as_batch=False,
        compare_type=True,
    )

    with context.begin_transaction():
        context.run_migrations()


# ---------------------------------------------------------------------------
# Online mode — connects to the database and applies migrations
# ---------------------------------------------------------------------------
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,          # Detect column type changes
        compare_server_default=True,  # Detect server-default changes
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and delegate to the sync helper via run_sync."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,  # Use a fresh connection per migration run
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
