from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.ingestion.models import IngestionRun
from app.modules.ingestion.service import IngestionService

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("/connectors")
async def list_connectors():
    return {
        "connectors": [
            {"name": "rbi", "display_name": "RBI Press Releases", "type": "rss"},
            {"name": "sebi", "display_name": "SEBI Circulars/Orders", "type": "rss"},
            {"name": "bse", "display_name": "BSE Corporate Announcements", "type": "scraper"},
            {"name": "nse", "display_name": "NSE Corporate Announcements", "type": "api"},
            {"name": "gdelt", "display_name": "GDELT Global Events", "type": "gdelt"},
            {"name": "world_monitor", "display_name": "World Monitor Events", "type": "world_monitor"},
        ]
    }


@router.get("/connectors/{name}/health")
async def connector_health(name: str, db: AsyncSession = Depends(get_db)):
    service = IngestionService(db)
    health = await service.get_connector_health(name)
    return health


@router.get("/connectors/health")
async def all_connectors_health(db: AsyncSession = Depends(get_db)):
    service = IngestionService(db)
    return await service.get_all_health()


@router.post("/run/{connector_name}")
async def run_ingestion(
    connector_name: str,
    source_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    service = IngestionService(db)

    if source_id is None:
        source_map = {
            "rbi": "00000000-0000-0000-0000-000000000001",
            "sebi": "00000000-0000-0000-0000-000000000002",
            "bse": "00000000-0000-0000-0000-000000000003",
            "nse": "00000000-0000-0000-0000-000000000004",
            "gdelt": "00000000-0000-0000-0000-000000000005",
            "world_monitor": "00000000-0000-0000-0000-000000000006",
        }
        if connector_name not in source_map:
            raise HTTPException(400, f"Unknown connector: {connector_name}")
        source_id = uuid.UUID(source_map[connector_name])

    run = await service.run_ingestion(source_id, connector_name)
    return {
        "run_id": str(run.id),
        "status": run.status,
        "items_ingested": run.items_ingested,
        "items_failed": run.items_failed,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }


@router.get("/runs")
async def list_runs(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IngestionRun)
        .order_by(IngestionRun.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    runs = result.scalars().all()
    return [
        {
            "id": str(r.id),
            "source_id": str(r.source_id),
            "status": r.status,
            "error": r.error,
            "items_ingested": r.items_ingested,
            "items_failed": r.items_failed,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "completed_at": r.completed_at.isoformat() if r.completed_at else None,
        }
        for r in runs
    ]


@router.get("/runs/{run_id}")
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(IngestionRun).where(IngestionRun.id == run_id))
    run = result.scalar_one_or_none()
    if not run:
        raise HTTPException(404, "Run not found")
    return {
        "id": str(run.id),
        "source_id": str(run.source_id),
        "status": run.status,
        "error": run.error,
        "items_ingested": run.items_ingested,
        "items_failed": run.items_failed,
        "started_at": run.started_at.isoformat() if run.started_at else None,
        "completed_at": run.completed_at.isoformat() if run.completed_at else None,
    }
