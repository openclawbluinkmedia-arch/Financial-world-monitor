from __future__ import annotations

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import get_settings
from app.database import Base, build_engine_kwargs
# Import all models so Alembic can detect them
from app.modules.audit.models import AuditLog  # noqa: F401
from app.modules.entities.models import CompanyAlias, SecurityMaster  # noqa: F401
from app.modules.evidence.models import Evidence, EvidenceDedupLog  # noqa: F401
from app.modules.ingestion.models import ConnectorHealth, IngestionRun  # noqa: F401
from app.modules.intelligence.models import (  # noqa: F401
    CausalGraphEdge,
    ConfidenceScore,
    IntelligenceEvent,
    KnowledgeGraphNode,
    ValidationResult,
)
from app.modules.portfolios.models import (  # noqa: F401
    AlertPreference,
    Holding,
    HoldingImpact,
    Portfolio,
    PortfolioAlert,
)
from app.modules.copilot.models import (  # noqa: F401
    CopilotConversation,
    CopilotMessage,
)

config = context.config
settings = get_settings()

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = settings.sqlalchemy_url
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    url, engine_kwargs = build_engine_kwargs(settings.sqlalchemy_url, settings.DATABASE_SSL)
    connectable = create_async_engine(url, **engine_kwargs)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
