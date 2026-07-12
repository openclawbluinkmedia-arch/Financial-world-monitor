from __future__ import annotations

import logging

import redis.asyncio as aioredis
from fastapi import APIRouter

from app.config import get_settings

logger = logging.getLogger("fios.health")
settings = get_settings()

router = APIRouter()


async def _check_postgres() -> dict:
    try:
        from app.database import check_db_health

        ok = await check_db_health()
        return {"status": "ok" if ok else "error", "detail": None}
    except Exception as e:
        logger.warning("Postgres health check failed: %s", e)
        return {"status": "error", "detail": str(e)}


async def _check_redis() -> dict:
    try:
        r = aioredis.from_url(settings.REDIS_URL, socket_connect_timeout=3)
        await r.ping()
        await r.aclose()
        return {"status": "ok", "detail": None}
    except Exception as e:
        logger.warning("Redis health check failed: %s", e)
        return {"status": "error", "detail": str(e)}


@router.get("/health")
async def health_check():
    db = await _check_postgres()
    cache = await _check_redis()
    overall = "ok" if db["status"] == "ok" and cache["status"] == "ok" else "degraded"
    return {
        "status": overall,
        "mode": settings.DEPLOYMENT_MODE.value,
        "services": {
            "postgres": db,
            "redis": cache,
        },
    }
