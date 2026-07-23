from __future__ import annotations

import logging
import uuid

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.database import async_session_factory
from app.modules.ingestion.service import IngestionService

logger = logging.getLogger("fios.scheduler")

SOURCE_IDS: dict[str, uuid.UUID] = {
    "rbi": uuid.UUID("00000000-0000-0000-0000-000000000001"),
    "sebi": uuid.UUID("00000000-0000-0000-0000-000000000002"),
    "bse": uuid.UUID("00000000-0000-0000-0000-000000000003"),
    "nse": uuid.UUID("00000000-0000-0000-0000-000000000004"),
    "gdelt": uuid.UUID("00000000-0000-0000-0000-000000000005"),
    "world_monitor": uuid.UUID("00000000-0000-0000-0000-000000000006"),
}

SCHEDULE: list[tuple[str, int]] = [
    ("gdelt", 15),
    ("rbi", 30),
    ("sebi", 30),
    ("bse", 15),
    ("nse", 15),
    ("world_monitor", 30),
]

scheduler = AsyncIOScheduler()


async def run_connector(connector_name: str):
    async with async_session_factory() as db:
        try:
            service = IngestionService(db)
            source_id = SOURCE_IDS.get(connector_name)
            if source_id is None:
                logger.error("Unknown connector: %s", connector_name)
                return
            run = await service.run_ingestion(source_id, connector_name)
            logger.info(
                "Scheduled ingestion %s: status=%s ingested=%d failed=%d",
                connector_name,
                run.status,
                run.items_ingested,
                run.items_failed,
            )
        except Exception as e:
            logger.error("Scheduled ingestion %s failed: %s", connector_name, e, exc_info=True)


def start_scheduler():
    for name, interval_min in SCHEDULE:
        scheduler.add_job(
            run_connector,
            trigger=IntervalTrigger(minutes=interval_min),
            args=[name],
            id=f"ingest_{name}",
            replace_existing=True,
            misfire_grace_time=300,
        )
        logger.info("Scheduled connector %s every %d min", name, interval_min)
    scheduler.start()
    logger.info("APScheduler started with %d jobs", len(SCHEDULE))


def stop_scheduler():
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("APScheduler stopped")
