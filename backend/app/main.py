from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import get_settings
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
    logger.info("Starting APScheduler ingestion jobs...")
    start_scheduler()
    yield
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
