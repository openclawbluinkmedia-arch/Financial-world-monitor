from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings
from app.database import Base
from app.modules.alerts.models import Alert  # noqa: F401
from app.modules.audit.models import AuditLog  # noqa: F401

# Import all models so Alembic can detect them
from app.modules.auth.models import User  # noqa: F401
from app.modules.documents.models import Document  # noqa: F401
from app.modules.entities.models import Entity  # noqa: F401
from app.modules.events.models import Event  # noqa: F401
from app.modules.evidence.models import Evidence  # noqa: F401
from app.modules.graph.models import GraphEdge  # noqa: F401
from app.modules.impact.models import Impact  # noqa: F401
from app.modules.ingestion.models import IngestionRun  # noqa: F401
from app.modules.portfolios.models import Portfolio  # noqa: F401
from app.modules.sources.models import Source  # noqa: F401
from app.modules.tenants.models import Tenant  # noqa: F401

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.DATABASE_URL
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = create_async_engine(settings.DATABASE_URL)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
