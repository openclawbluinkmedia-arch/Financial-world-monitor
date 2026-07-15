from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, Index, String, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class EventType(str, PyEnum):
    MACRO = "macro"
    EARNINGS = "earnings"
    M_A = "m_a"
    REGULATORY = "regulatory"
    POLICY = "policy"
    CORPORATE_ACTION = "corporate_action"
    MARKET_MOVE = "market_move"
    COMMODITY = "commodity"
    CURRENCY = "currency"
    GEOPOLITICAL = "geopolitical"
    SECTOR = "sector"
    SUPPLY_CHAIN = "supply_chain"
    ESG = "esg"
    OTHER = "other"


class ImpactDirection(str, PyEnum):
    POSITIVE = "positive"
    NEGATIVE = "negative"
    NEUTRAL = "neutral"
    MIXED = "mixed"
    UNKNOWN = "unknown"


class ImpactHorizon(str, PyEnum):
    IMMEDIATE = "immediate"
    SHORT_TERM = "short_term"
    MEDIUM_TERM = "medium_term"
    LONG_TERM = "long_term"
    UNKNOWN = "unknown"


class CausalEdgeType(str, PyEnum):
    VERIFIED = "verified"
    INFERRED = "inferred"
    UNCERTAIN = "uncertain"


class IntelligenceEvent(Base):
    """
    Structured event schema for intelligence pipeline output.
    """
    __tablename__ = "intelligence_events"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)

    # Core event info
    event_type: Mapped[EventType] = mapped_column(String(32), nullable=False, index=True)
    factual_summary: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    geography: Mapped[str] = mapped_column(String(64), nullable=False, default="IN", index=True)

    # Entities (JSON arrays of entity IDs)
    entities: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    sectors: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    industries: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    commodities: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    currencies: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Evidence references
    source_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Impact assessment
    direct_impacts: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    indirect_impacts: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    possible_beneficiaries: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
    possible_negative_exposures: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    # Impact characterization
    impact_direction: Mapped[ImpactDirection] = mapped_column(String(16), nullable=False, default=ImpactDirection.UNKNOWN.value)
    impact_horizon: Mapped[ImpactHorizon] = mapped_column(String(16), nullable=False, default=ImpactHorizon.UNKNOWN.value)
    causal_chain: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    # Confidence & validation
    confidence: Mapped[float] = mapped_column(default=0.0)
    uncertainty: Mapped[float] = mapped_column(default=1.0)
    human_review_required: Mapped[bool] = mapped_column(default=False)
    validation_flags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Metadata
    pipeline_version: Mapped[str] = mapped_column(String(32), nullable=False, default="1.0")
    extra_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_intelligence_events_timestamp_type", "timestamp", "event_type"),
        Index("ix_intelligence_events_geography_type", "geography", "event_type"),
        Index("ix_intelligence_events_confidence", "confidence"),
    )


class CausalGraphEdge(Base):
    """
    Knowledge graph edges: every causal edge is labelled VERIFIED / INFERRED / UNCERTAIN.
    Never render an inferred edge as a verified fact.
    """
    __tablename__ = "causal_graph_edges"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    # Source and target entities
    source_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    source_entity_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    target_entity_type: Mapped[str] = mapped_column(String(32), nullable=False)

    # Edge properties
    edge_type: Mapped[CausalEdgeType] = mapped_column(String(16), nullable=False, default=CausalEdgeType.UNCERTAIN.value)
    relationship: Mapped[str] = mapped_column(String(64), nullable=False)
    weight: Mapped[float] = mapped_column(default=1.0)

    # Evidence
    evidence_ids: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    confidence: Mapped[float] = mapped_column(default=0.0)

    # Temporal
    valid_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_causal_edges_source", "source_entity_id", "source_entity_type"),
        Index("ix_causal_edges_target", "target_entity_id", "target_entity_type"),
        Index("ix_causal_edges_type", "edge_type"),
        UniqueConstraint("source_entity_id", "source_entity_type", "target_entity_id", "target_entity_type", "relationship", name="uq_causal_edge"),
    )


class KnowledgeGraphNode(Base):
    """
    Knowledge graph nodes: events, companies, sectors, industries, countries, regulators, commodities, currencies, suppliers, customers, competitors, securities.
    """
    __tablename__ = "knowledge_graph_nodes"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    node_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # Properties stored as JSON
    properties: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Embedding for similarity search
    embedding: Mapped[list[float] | None] = mapped_column(Vector(1024), nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_kg_nodes_type_external", "node_type", "external_id"),
    )


class ValidationResult(Base):
    """
    Deterministic validation results for an intelligence event.
    """
    __tablename__ = "validation_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)

    # Citation validation
    citations_valid: Mapped[bool] = mapped_column(default=True)
    invalid_citations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    missing_citations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Numerical consistency
    numerically_consistent: Mapped[bool] = mapped_column(default=True)
    numerical_issues: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Contradiction detection
    has_contradictions: Mapped[bool] = mapped_column(default=False)
    contradictions: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)

    # Missing evidence
    has_missing_evidence: Mapped[bool] = mapped_column(default=False)
    missing_evidence_claims: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Abstention
    abstained: Mapped[bool] = mapped_column(default=False)
    abstention_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Overall
    passed: Mapped[bool] = mapped_column(default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ConfidenceScore(Base):
    """
    Confidence computation from source reliability, corroboration, coverage, entity resolution certainty, retrieval score.
    Never invented by the LLM.
    """
    __tablename__ = "confidence_scores"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, unique=True, index=True)

    # Components
    source_reliability: Mapped[float] = mapped_column(default=0.0)
    corroboration_count: Mapped[int] = mapped_column(default=0)
    evidence_coverage: Mapped[float] = mapped_column(default=0.0)
    entity_resolution_certainty: Mapped[float] = mapped_column(default=0.0)
    retrieval_score: Mapped[float] = mapped_column(default=0.0)

    # Weights
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Final
    confidence: Mapped[float] = mapped_column(default=0.0)
    uncertainty: Mapped[float] = mapped_column(default=1.0)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())