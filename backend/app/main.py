from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.health import router as health_router
from app.config import get_settings

settings = get_settings()

logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL, logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("fios")

app = FastAPI(
    title="FIOS — Financial Intelligence Operating System",
    version="0.1.0",
    description="Privacy-first, self-hostable B2B financial-intelligence platform.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api", tags=["health"])


@app.get("/")
async def root():
    return {
        "service": "FIOS",
        "version": "0.1.0",
        "mode": settings.DEPLOYMENT_MODE.value,
        "docs": "/docs",
    }
