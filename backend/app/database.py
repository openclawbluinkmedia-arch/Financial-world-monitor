from __future__ import annotations

from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.config import get_settings

settings = get_settings()

_connect_args = {}
if settings.DATABASE_SSL:
    _connect_args["ssl"] = settings.DATABASE_SSL

_db_url = settings.DATABASE_URL
if _db_url.startswith("postgresql://"):
    _db_url = "postgresql+asyncpg://" + _db_url[len("postgresql://"):]

engine = create_async_engine(
    _db_url,
    echo=False,
    connect_args=_connect_args if _connect_args else {},
)
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
