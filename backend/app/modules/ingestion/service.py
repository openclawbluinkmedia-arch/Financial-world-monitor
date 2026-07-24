from __future__ import annotations

import logging
import os
import tempfile
import time as time_mod
import uuid
from datetime import datetime, timezone
from typing import Any

from app.modules.evidence.models import Evidence, EvidenceDedupLog
from app.modules.ingestion.connectors import (
    BSEConfig,
    BSEConnector,
    GDELTConfig,
    GDELTConnector,
    NSEConfig,
    NSEConnector,
    RBIConfig,
    RBIConnector,
    SEBIConfig,
    SEBIConnector,
    WorldMonitorConfig,
    WorldMonitorConnector,
)
from app.modules.ingestion.models import ConnectorHealth, ConnectorStatus, IngestionRun

logger = logging.getLogger("fios.ingestion.service")


class DocumentProcessor:
    """
    Lightweight document processor using pypdf for text extraction.
    No OCR capability — scanned PDFs are marked for OCR and skipped.
    """

    async def process_document(self, content: bytes, filename: str) -> dict[str, Any]:
        if filename.lower().endswith(".pdf"):
            return await self._process_pdf(content, filename)
        else:
            return await self._process_text(content, filename)

    async def _process_pdf(self, content: bytes, filename: str) -> dict[str, Any]:
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp.write(content)
            tmp_path = tmp.name

        try:
            from pypdf import PdfReader
            reader = PdfReader(tmp_path)
            pages = []
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    pages.append(text)
            text = "\n\n".join(pages)

            if not text.strip():
                return {
                    "text": "",
                    "tables": [],
                    "method": "skipped_ocr_needed",
                    "error": "No extractable text — OCR required",
                }

            return {
                "text": text,
                "tables": [],
                "method": "pypdf",
            }
        except Exception as e:
            logger.error(f"PDF processing failed: {e}")
            return {"text": "", "tables": [], "method": "error", "error": str(e)}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    async def _process_text(self, content: bytes, filename: str) -> dict[str, Any]:
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError:
            text = content.decode("latin-1", errors="replace")
        return {"text": text, "tables": [], "method": "text"}


class DeduplicationService:
    def __init__(self, db_session):
        self.db = db_session

    async def check_exact_duplicate(self, content_hash: str) -> Evidence | None:
        from sqlalchemy import select
        result = await self.db.execute(
            select(Evidence).where(Evidence.content_hash == content_hash)
        )
        return result.scalar_one_or_none()

    async def check_near_duplicate(self, near_dup_hash: str, threshold: float = 0.85) -> Evidence | None:
        if not near_dup_hash:
            return None
        from simhash import Simhash
        from sqlalchemy import select
        try:
            query_hash = int(near_dup_hash)
            result = await self.db.execute(
                select(Evidence).where(Evidence.near_dup_hash != None)
            )
            for evidence in result.scalars().all():
                if evidence.near_dup_hash:
                    try:
                        stored_hash = int(evidence.near_dup_hash)
                        distance = Simhash(query_hash).distance(Simhash(stored_hash))
                        similarity = 1 - (distance / 64.0)
                        if similarity >= threshold:
                            return evidence
                    except Exception:
                        continue
        except Exception as e:
            logger.warning(f"Near-duplicate check failed: {e}")
        return None

    async def log_deduplication(
        self, evidence_id: uuid.UUID, duplicate_of_id: uuid.UUID, dedup_type: str, similarity: float | None
    ):
        log = EvidenceDedupLog(
            evidence_id=evidence_id,
            duplicate_of_id=duplicate_of_id,
            dedup_type=dedup_type,
            similarity_score=similarity,
        )
        self.db.add(log)


class IngestionService:
    def __init__(self, db_session):
        self.db = db_session
        self.doc_processor = DocumentProcessor()
        self.dedup_service = DeduplicationService(db_session)
        self.connectors = self._initialize_connectors()

    def _initialize_connectors(self) -> dict[str, Any]:
        return {
            "rbi": RBIConnector(RBIConfig(name="rbi")),
            "sebi": SEBIConnector(SEBIConfig(name="sebi")),
            "bse": BSEConnector(BSEConfig(name="bse")),
            "nse": NSEConnector(NSEConfig(name="nse")),
            "gdelt": GDELTConnector(GDELTConfig(name="gdelt")),
            "world_monitor": WorldMonitorConnector(WorldMonitorConfig(name="world_monitor")),
        }

    async def run_ingestion(self, source_id: uuid.UUID, connector_name: str) -> IngestionRun:
        connector = self.connectors.get(connector_name)
        if not connector:
            raise ValueError(f"Unknown connector: {connector_name}")

        run = IngestionRun(source_id=source_id, status="running", started_at=datetime.now(timezone.utc))
        self.db.add(run)
        await self.db.flush()

        try:
            async with connector:
                result = await connector.fetch()
                run.items_ingested = result.success_count
                run.items_failed = result.error_count
                run.status = "completed" if result.error_count == 0 else "partial"
                run.completed_at = datetime.now(timezone.utc)

                for item in result.items:
                    await self._process_item(item, run.id)

                await self._update_connector_health(connector_name, True, None)
        except Exception as e:
            run.status = "failed"
            run.error = str(e)
            run.completed_at = datetime.now(timezone.utc)
            await self._update_connector_health(connector_name, False, str(e))
            logger.error(f"Ingestion run failed: {e}", exc_info=True)

        return run

    async def _process_item(self, item, run_id: uuid.UUID):
        existing = await self.dedup_service.check_exact_duplicate(item.content_hash)
        if existing:
            await self.dedup_service.log_deduplication(
                item.evidence_id, existing.id, "exact", 1.0
            )
            return

        near_dup = await self.dedup_service.check_near_duplicate(item.near_dup_hash)
        if near_dup:
            await self.dedup_service.log_deduplication(
                item.evidence_id, near_dup.id, "near", 0.85
            )
            return

        evidence = Evidence(
            evidence_id=item.evidence_id,
            source_id=item.source_id,
            source_name=item.source_name,
            original_url=item.original_url,
            publisher=item.publisher,
            title=item.title,
            raw_content=item.raw_content,
            normalized_content=item.raw_content,
            content_hash=item.content_hash,
            near_dup_hash=item.near_dup_hash,
            publication_ts=item.publication_ts,
            ingestion_ts=datetime.now(timezone.utc),
            jurisdiction=item.jurisdiction,
            source_type=item.source_type,
            version=1,
            is_mock=item.is_mock,
            extra_metadata=str(item.metadata) if item.metadata else None,
        )

        self.db.add(evidence)
        await self.db.flush()

    async def _update_connector_health(self, name: str, success: bool, error: str | None):
        from sqlalchemy import select
        result = await self.db.execute(
            select(ConnectorHealth).where(ConnectorHealth.connector_name == name)
        )
        health = result.scalar_one_or_none()

        if not health:
            health = ConnectorHealth(connector_name=name)
            self.db.add(health)

        if success:
            health.status = ConnectorStatus.HEALTHY
            health.last_success_at = datetime.now(timezone.utc)
            health.consecutive_failures = 0
            health.last_error = None
        else:
            health.consecutive_failures += 1
            health.last_error = error
            if health.consecutive_failures >= 3:
                health.status = ConnectorStatus.FAILED
            elif health.consecutive_failures >= 1:
                health.status = ConnectorStatus.DEGRADED

        health.last_run_at = datetime.now(timezone.utc)
        await self.db.flush()

    async def get_connector_health(self, name: str) -> dict[str, Any]:
        from sqlalchemy import select
        result = await self.db.execute(
            select(ConnectorHealth).where(ConnectorHealth.connector_name == name)
        )
        health = result.scalar_one_or_none()
        if not health:
            return {"connector": name, "status": "unknown", "last_run_at": None}
        return {
            "connector": health.connector_name,
            "status": health.status.value,
            "last_run_at": health.last_run_at.isoformat() if health.last_run_at else None,
            "last_success_at": health.last_success_at.isoformat() if health.last_success_at else None,
            "consecutive_failures": health.consecutive_failures,
            "last_error": health.last_error,
        }

    async def get_all_health(self) -> list[dict[str, Any]]:
        from sqlalchemy import select
        result = await self.db.execute(select(ConnectorHealth))
        health_list = result.scalars().all()
        return [
            {
                "connector": h.connector_name,
                "status": h.status.value,
                "last_run_at": h.last_run_at.isoformat() if h.last_run_at else None,
                "last_success_at": h.last_success_at.isoformat() if h.last_success_at else None,
                "consecutive_failures": h.consecutive_failures,
                "last_error": h.last_error,
            }
            for h in health_list
        ]

    SOURCE_IDS: dict[str, uuid.UUID] = {
        "rbi": uuid.UUID("00000000-0000-0000-0000-000000000001"),
        "sebi": uuid.UUID("00000000-0000-0000-0000-000000000002"),
        "bse": uuid.UUID("00000000-0000-0000-0000-000000000003"),
        "nse": uuid.UUID("00000000-0000-0000-0000-000000000004"),
        "gdelt": uuid.UUID("00000000-0000-0000-0000-000000000005"),
        "world_monitor": uuid.UUID("00000000-0000-0000-0000-000000000006"),
    }

    async def run_all_connectors(self) -> dict[str, Any]:
        start = time_mod.monotonic()

        from sqlalchemy import select as sa_select, text as sa_text

        lock_result = await self.db.execute(sa_text("SELECT pg_try_advisory_xact_lock(42)"))
        if not lock_result.scalar():
            return {"error": "Another ingestion run is already in progress", "overlap": True}

        connectors_summary: dict[str, dict[str, Any]] = {}
        all_new_evidence_ids: list[str] = []

        for name, sid in self.SOURCE_IDS.items():
            connector_start = time_mod.monotonic()
            connector = self.connectors.get(name)
            if not connector:
                connectors_summary[name] = {"status": "error", "error": "Unknown connector"}
                continue

            run = IngestionRun(
                source_id=sid, status="running", started_at=datetime.now(timezone.utc)
            )
            self.db.add(run)
            await self.db.flush()

            items_fetched = 0
            new_count = 0
            dup_count = 0

            try:
                async with connector:
                    result = await connector.fetch()
                    items_fetched = len(result.items)

                    for item in result.items:
                        existing = await self.dedup_service.check_exact_duplicate(item.content_hash)
                        if existing:
                            await self.dedup_service.log_deduplication(
                                item.evidence_id, existing.id, "exact", 1.0
                            )
                            dup_count += 1
                            continue

                        near_dup = await self.dedup_service.check_near_duplicate(item.near_dup_hash)
                        if near_dup:
                            await self.dedup_service.log_deduplication(
                                item.evidence_id, near_dup.id, "near", 0.85
                            )
                            dup_count += 1
                            continue

                        evidence = Evidence(
                            evidence_id=item.evidence_id,
                            source_id=item.source_id,
                            source_name=item.source_name,
                            original_url=item.original_url,
                            publisher=item.publisher,
                            title=item.title,
                            raw_content=item.raw_content,
                            normalized_content=item.raw_content,
                            content_hash=item.content_hash,
                            near_dup_hash=item.near_dup_hash,
                            publication_ts=item.publication_ts,
                            ingestion_ts=datetime.now(timezone.utc),
                            jurisdiction=item.jurisdiction,
                            source_type=item.source_type,
                            version=1,
                            is_mock=item.is_mock,
                            extra_metadata=str(item.metadata) if item.metadata else None,
                        )
                        self.db.add(evidence)
                        await self.db.flush()
                        all_new_evidence_ids.append(evidence.evidence_id)
                        new_count += 1

                run.items_ingested = new_count
                run.items_failed = result.error_count
                run.status = "completed" if result.error_count == 0 else "partial"
                run.completed_at = datetime.now(timezone.utc)
                await self._update_connector_health(name, True, None)

            except Exception as e:
                run.status = "failed"
                run.error = str(e)
                run.completed_at = datetime.now(timezone.utc)
                await self._update_connector_health(name, False, str(e))
                logger.error("run-all %s failed: %s", name, e, exc_info=True)

            elapsed = time_mod.monotonic() - connector_start
            connectors_summary[name] = {
                "status": run.status,
                "items_fetched": items_fetched,
                "new": new_count,
                "duplicates": dup_count,
                "failed": run.items_failed or 0,
                "error": run.error,
                "duration_seconds": round(elapsed, 2),
            }

        # Step 2 — generate embeddings for new evidence
        embed_count = 0
        if all_new_evidence_ids:
            try:
                from app.ai.embeddings import embed_texts

                result = await self.db.execute(
                    sa_select(Evidence).where(Evidence.evidence_id.in_(all_new_evidence_ids))
                )
                new_evidence = result.scalars().all()

                texts: list[str] = []
                ev_map: dict[str, Evidence] = {}
                for ev in new_evidence:
                    t = f"{ev.title}\n\n{ev.raw_content[:2000]}"
                    texts.append(t)
                    ev_map[t] = ev

                batch_size = 10
                for i in range(0, len(texts), batch_size):
                    batch = texts[i : i + batch_size]
                    vectors = await embed_texts(batch)
                    for t, vec in zip(batch, vectors):
                        ev_map[t].embedding = vec
                    embed_count += len(batch)
                await self.db.flush()
            except Exception as e:
                logger.warning("Embedding generation skipped: %s", e)

        # Step 3 — run intelligence pipeline on new items
        pipeline_count = 0
        if all_new_evidence_ids:
            try:
                from app.modules.intelligence.pipeline import IntelligencePipeline

                result = await self.db.execute(
                    sa_select(Evidence).where(Evidence.evidence_id.in_(all_new_evidence_ids))
                )
                new_evidence = result.scalars().all()
                pipeline = IntelligencePipeline(self.db)
                events = await pipeline.process_evidence_batch(new_evidence)
                pipeline_count = len(events)
            except Exception as e:
                logger.warning("Intelligence pipeline skipped: %s", e)

        total_duration = time_mod.monotonic() - start
        return {
            "connectors": connectors_summary,
            "embeddings_generated": embed_count,
            "intelligence_events_created": pipeline_count,
            "total_duration_seconds": round(total_duration, 2),
            "summary": {
                "total_connectors": len(connectors_summary),
                "ok": sum(
                    1 for r in connectors_summary.values()
                    if r.get("status") in ("completed", "partial")
                ),
                "failed": sum(
                    1 for r in connectors_summary.values()
                    if r.get("status") == "error"
                ),
                "total_items_fetched": sum(
                    r["items_fetched"] for r in connectors_summary.values()
                ),
                "total_new": sum(
                    r["new"] for r in connectors_summary.values()
                ),
                "total_duplicates": sum(
                    r["duplicates"] for r in connectors_summary.values()
                ),
            },
        }
