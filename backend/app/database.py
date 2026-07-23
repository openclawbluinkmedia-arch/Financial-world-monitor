from __future__ import annotations

from typing import Any, AsyncGenerator
from urllib.parse import urlparse

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()


def build_engine_kwargs(database_url: str, database_ssl: str = "") -> tuple[str, dict[str, Any]]:
    connect_args: dict[str, Any] = {
        "statement_cache_size": 0,
        "prepared_statement_cache_size": 0,
    }
    ssl_value = database_ssl
    if not ssl_value:
        host = urlparse(database_url).hostname or ""
        if host not in ("localhost", "127.0.0.1", "::1", ""):
            ssl_value = "require"
    if ssl_value:
        connect_args["ssl"] = ssl_value
    return database_url, {"echo": False, "connect_args": connect_args}


url, engine_kwargs = build_engine_kwargs(settings.sqlalchemy_url, settings.DATABASE_SSL)
engine = create_async_engine(url, **engine_kwargs)
async_session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_health() -> bool:
    try:
        async with engine.connect() as conn:
            from sqlalchemy import text as sa_text
            await conn.execute(sa_text("SELECT 1"))
        return True
    except Exception:
        return False
