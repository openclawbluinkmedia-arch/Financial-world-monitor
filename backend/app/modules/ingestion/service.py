from __future__ import annotations

import logging
import os
import tempfile
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
    def __init__(self):
        self._docling_available = False
        self._paddleocr_available = False
        self._initialize_processors()

    def _initialize_processors(self):
        try:
            from docling.document_converter import DocumentConverter
            self._docling_converter = DocumentConverter()
            self._docling_available = True
            logger.info("Docling document processor initialized")
        except Exception as e:
            logger.warning(f"Docling not available: {e}")

        try:
            from paddleocr import PaddleOCR
            self._paddle_ocr = PaddleOCR(use_angle_cls=True, lang="en", use_gpu=False)
            self._paddleocr_available = True
            logger.info("PaddleOCR initialized")
        except Exception as e:
            logger.warning(f"PaddleOCR not available: {e}")

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
            if self._docling_available:
                result = self._docling_converter.convert(tmp_path)
                text = result.document.export_to_text()
                tables = result.document.export_to_dict().get("tables", [])

                if self._is_scanned_or_empty(text):
                    logger.info(f"Document {filename} appears scanned, using PaddleOCR")
                    if self._paddleocr_available:
                        text = await self._ocr_pdf(tmp_path)

                return {
                    "text": text,
                    "tables": tables,
                    "method": "docling" + ("+paddleocr" if self._paddleocr_available else ""),
                }
            else:
                return {"text": "", "tables": [], "method": "none", "error": "No processor available"}
        finally:
            try:
                os.unlink(tmp_path)
            except Exception:
                pass

    def _is_scanned_or_empty(self, text: str) -> bool:
        text = text.strip()
        if len(text) < 100:
            return True
        if len(text.split()) < 20:
            return True
        return False

    async def _ocr_pdf(self, pdf_path: str) -> str:
        if not self._paddleocr_available:
            return ""

        try:
            import fitz
            doc = fitz.open(pdf_path)
            all_text = []

            for page_num in range(len(doc)):
                page = doc[page_num]
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")

                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(img_bytes)
                    img_path = tmp.name

                try:
                    result = self._paddle_ocr.ocr(img_path, cls=True)
                    if result:
                        page_text = "\n".join([line[1][0] for line in result if line])
                        all_text.append(page_text)
                finally:
                    os.unlink(img_path)

            doc.close()
            return "\n\n".join(all_text)
        except Exception as e:
            logger.error(f"PaddleOCR failed: {e}")
            return ""

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
