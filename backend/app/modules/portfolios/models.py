from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Portfolio(Base):
    __tablename__ = "portfolios"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    config: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)


class Holding(Base):
    __tablename__ = "holdings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Security identification
    ticker: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    exchange: Mapped[str] = mapped_column(String(8), nullable=False)  # NSE, BSE
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)

    # Company info
    company_name: Mapped[str] = mapped_column(String(256), nullable=False)
    sector: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    industry: Mapped[str | None] = mapped_column(String(64), nullable=True)
    country: Mapped[str] = mapped_column(String(2), nullable=False, default="IN")

    # Position details
    quantity: Mapped[float] = mapped_column(nullable=False)
    weight: Mapped[float] = mapped_column(nullable=False)  # Percentage weight
    avg_price: Mapped[float | None] = mapped_column(nullable=True)
    current_price: Mapped[float | None] = mapped_column(nullable=True)
    market_value: Mapped[float | None] = mapped_column(nullable=True)

    # Metadata
    extra_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("portfolio_id", "ticker", "exchange", name="uq_holding_portfolio_ticker"),
        Index("ix_holding_portfolio_sector", "portfolio_id", "sector"),
    )


class ExposureClassification(str, PyEnum):
    DIRECTLY_AFFECTED = "directly_affected"
    INDIRECTLY_AFFECTED = "indirectly_affected"
    POSSIBLE_BENEFICIARY = "possible_beneficiary"
    POSSIBLE_NEGATIVE_EXPOSURE = "possible_negative_exposure"
    UNCERTAIN = "uncertain"
    NO_MATERIAL_EVIDENCE = "no_material_evidence"


class HoldingImpact(Base):
    """
    Tracks the impact of an intelligence event on a specific holding.
    """
    __tablename__ = "holding_impacts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    event_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    holding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Classification
    classification: Mapped[ExposureClassification] = mapped_column(
        String(32), nullable=False, index=True
    )

    # Impact details
    impact_score: Mapped[float] = mapped_column(default=0.0)  # -1.0 to 1.0
    confidence: Mapped[float] = mapped_column(default=0.0)
    uncertainty: Mapped[float] = mapped_column(default=1.0)

    # Explanation with citations
    reasoning: Mapped[str] = mapped_column(Text, nullable=False)
    citations: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    verified_relationships: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    inferred_relationships: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Timing
    impact_horizon: Mapped[str | None] = mapped_column(String(16), nullable=True)
    assessed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("event_id", "holding_id", name="uq_holding_impact"),
        Index("ix_holding_impact_portfolio_classification", "portfolio_id", "classification"),
    )


class PortfolioAlert(Base):
    """
    Internal alert system for portfolio impact events.
    """
    __tablename__ = "portfolio_alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Alert type
    alert_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    # Types: new_direct_exposure, new_indirect_exposure, material_event, changed_assessment

    # References
    event_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    holding_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)

    # Alert details
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False, default="info")

    # Status
    is_read: Mapped[bool] = mapped_column(default=False)
    dismissed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Metadata
    extra_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_portfolio_alert_portfolio_unread", "portfolio_id", "is_read"),
    )


class AlertPreference(Base):
    """
    User preferences for alert notifications.
    """
    __tablename__ = "alert_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    portfolio_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, unique=True, index=True
    )
    tenant_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )

    # Alert type preferences
    enable_new_direct_exposure: Mapped[bool] = mapped_column(default=True)
    enable_new_indirect_exposure: Mapped[bool] = mapped_column(default=True)
    enable_material_event: Mapped[bool] = mapped_column(default=True)
    enable_changed_assessment: Mapped[bool] = mapped_column(default=True)

    # Severity thresholds
    min_severity: Mapped[str] = mapped_column(String(16), default="info")

    # Channels (internal only for now)
    internal_web: Mapped[bool] = mapped_column(default=True)
    internal_email: Mapped[bool] = mapped_column(default=False)  # Future

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
