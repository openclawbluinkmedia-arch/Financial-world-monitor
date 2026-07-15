from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SourceType(str, PyEnum):
    RSS = "rss"
    API = "api"
    SCRAPER = "scraper"
    WORLD_MONITOR = "world_monitor"
    GDELT = "gdelt"


class Jurisdiction(str, PyEnum):
    IN = "IN"
    US = "US"
    EU = "EU"
    GLOBAL = "GLOBAL"
    OTHER = "OTHER"


class Evidence(Base):
    __tablename__ = "evidence"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_id: Mapped[str] = mapped_column(String(128), nullable=False, unique=True, index=True)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_name: Mapped[str] = mapped_column(String(256), nullable=False)
    original_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    publisher: Mapped[str | None] = mapped_column(String(256), nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    near_dup_hash: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    publication_ts: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ingestion_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)
    jurisdiction: Mapped[Jurisdiction] = mapped_column(String(32), nullable=False, default=Jurisdiction.OTHER.value)
    source_type: Mapped[SourceType] = mapped_column(String(32), nullable=False)
    version: Mapped[int] = mapped_column(default=1)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)
    is_mock: Mapped[bool] = mapped_column(default=False)
    extra_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_evidence_source_pub_ts", "source_id", "publication_ts"),
        Index("ix_evidence_jurisdiction_type", "jurisdiction", "source_type"),
        Index("ix_evidence_content_hash", "content_hash", unique=False),
    )


class EvidenceDedupLog(Base):
    __tablename__ = "evidence_dedup_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    evidence_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    duplicate_of_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    dedup_type: Mapped[str] = mapped_column(String(32), nullable=False)
    similarity_score: Mapped[float | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
