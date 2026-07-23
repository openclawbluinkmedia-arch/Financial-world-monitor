from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.health import router as health_router
from app.config import get_settings
from app.database import get_db
from app.modules.evidence import router as evidence_router
from app.modules.ingestion import router as ingestion_router
from app.modules.intelligence import router as intelligence_router
from app.modules.auth.router import router as auth_router
from app.modules.portfolios import router as portfolios_router
from app.modules.copilot import router as copilot_router
from app.scheduler import start_scheduler, stop_scheduler

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fios")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Running database migrations...")
    try:
        proc = await asyncio.create_subprocess_exec(
            "alembic", "upgrade", "head",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode == 0:
            logger.info("Migrations completed successfully")
        else:
            logger.warning("Migrations failed (exit %d): %s", proc.returncode, stderr.decode().strip())
    except Exception as e:
        logger.warning("Could not run migrations: %s", e)

    if settings.ENABLE_SCHEDULER:
        logger.info("Starting APScheduler ingestion jobs...")
        start_scheduler()
    else:
        logger.info("Scheduler disabled (ENABLE_SCHEDULER=False)")
    yield
    if settings.ENABLE_SCHEDULER:
        stop_scheduler()


app = FastAPI(
    title="FIOS — Financial Intelligence Operating System",
    version="0.1.0",
    description="Privacy-first, self-hostable B2B financial-intelligence platform.",
    lifespan=lifespan,
)

allowed_origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins if allowed_origins else ["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])
app.include_router(ingestion_router, prefix="/api", tags=["ingestion"])
app.include_router(evidence_router, prefix="/api", tags=["evidence"])
app.include_router(auth_router, prefix="/api", tags=["auth"])
app.include_router(intelligence_router, prefix="/api", tags=["intelligence"])
app.include_router(portfolios_router, prefix="/api", tags=["portfolios"])
app.include_router(copilot_router, prefix="/api", tags=["copilot"])


@app.get("/")
async def root():
    return {
        "service": "FIOS",
        "version": "0.1.0",
        "mode": settings.DEPLOYMENT_MODE.value,
        "docs": "/docs",
    }


@app.post("/api/ingest/run-all")
async def run_all_ingestion(token: str = Query(...)):
    """Protected endpoint for external cron/scheduler.
    Called by GitHub Actions every 20 min. Guarded by INGEST_TOKEN."""
    if settings.INGEST_TOKEN and token != settings.INGEST_TOKEN:
        raise HTTPException(403, "Invalid ingest token")

    from app.database import async_session_factory
    from app.modules.ingestion.service import IngestionService
    import uuid

    source_ids = {
        "rbi": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "sebi": uuid.UUID("00000000-0000-0000-0000-000000000002"),
        "bse": uuid.UUID("00000000-0000-0000-0000-000000000003"),
        "nse": uuid.UUID("00000000-0000-0000-0000-000000000004"),
        "gdelt": uuid.UUID("00000000-0000-0000-0000-000000000005"),
        "world_monitor": uuid.UUID("00000000-0000-0000-0000-000000000006"),
    }

    results = {}
    async with async_session_factory() as db:
        service = IngestionService(db)
        for name, sid in source_ids.items():
            try:
                run = await service.run_ingestion(sid, name)
                results[name] = {
                    "status": run.status,
                    "ingested": run.items_ingested,
                    "failed": run.items_failed,
                }
                logger.info("run-all %s: %s", name, run.status)
            except Exception as e:
                results[name] = {"status": "error", "error": str(e)}
                logger.error("run-all %s failed: %s", name, e)

    return {
        "results": results,
        "summary": {
            "total": len(results),
            "ok": sum(1 for r in results.values() if r.get("status") in ("completed", "partial")),
            "failed": sum(1 for r in results.values() if r.get("status") == "error"),
        },
    }
