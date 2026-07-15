from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum
from typing import Optional

from sqlalchemy import DateTime, Index, String, Text, func, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Exchange(str, PyEnum):
    NSE = "NSE"
    BSE = "BSE"


class Sector(str, PyEnum):
    FINANCIALS = "Financials"
    ENERGY = "Energy"
    MATERIALS = "Materials"
    INDUSTRIALS = "Industrials"
    CONSUMER_DISCRETIONARY = "Consumer Discretionary"
    CONSUMER_STAPLES = "Consumer Staples"
    HEALTHCARE = "Healthcare"
    INFORMATION_TECHNOLOGY = "Information Technology"
    COMMUNICATION_SERVICES = "Communication Services"
    UTILITIES = "Utilities"
    REAL_ESTATE = "Real Estate"
    OTHER = "Other"


class Industry(str, PyEnum):
    BANKS = "Banks"
    INSURANCE = "Insurance"
    CAPITAL_MARKETS = "Capital Markets"
    OIL_GAS = "Oil & Gas"
    CHEMICALS = "Chemicals"
    METALS_MINING = "Metals & Mining"
    AUTOMOBILES = "Automobiles"
    PHARMACEUTICALS = "Pharmaceuticals"
    IT_SERVICES = "IT Services"
    TELECOM = "Telecom"
    POWER = "Power"
    CONSTRUCTION = "Construction"
    CEMENT = "Cement"
    FMCG = "FMCG"
    OTHER = "Other"


class SecurityMaster(Base):
    """
    Security master table mapping NSE/BSE tickers to companies, sectors, industries.
    Sourced from OpenBB service and cached in Postgres.
    """
    __tablename__ = "security_master"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Ticker symbols
    nse_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    bse_symbol: Mapped[str | None] = mapped_column(String(32), nullable=True, index=True)
    isin: Mapped[str | None] = mapped_column(String(12), nullable=True, index=True)

    # Company info
    company_name: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    company_short_name: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Classification
    sector: Mapped[Sector] = mapped_column(String(64), nullable=False, default=Sector.OTHER.value, index=True)
    industry: Mapped[Industry] = mapped_column(String(64), nullable=False, default=Industry.OTHER.value, index=True)
    sub_industry: Mapped[str | None] = mapped_column(String(128), nullable=True)

    # Exchange info
    primary_exchange: Mapped[Exchange] = mapped_column(String(8), nullable=False, default=Exchange.NSE.value)
    listing_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    face_value: Mapped[float | None] = mapped_column(nullable=True)
    market_lot: Mapped[int | None] = mapped_column(nullable=True)

    # Status
    is_active: Mapped[bool] = mapped_column(default=True, index=True)
    is_suspended: Mapped[bool] = mapped_column(default=False)

    # Metadata
    openbb_symbol: Mapped[str | None] = mapped_column(String(64), nullable=True)
    extra_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("nse_symbol", "bse_symbol", name="uq_security_master_symbols"),
        Index("ix_security_master_sector_industry", "sector", "industry"),
        Index("ix_security_master_active_symbols", "is_active", "nse_symbol", "bse_symbol"),
    )


class CompanyAlias(Base):
    """
    Alternative names, abbreviations, common misspellings for entity resolution.
    """
    __tablename__ = "company_aliases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    security_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), nullable=False, index=True
    )
    alias: Mapped[str] = mapped_column(String(256), nullable=False, index=True)
    alias_type: Mapped[str] = mapped_column(String(32), nullable=False)  # "short_name", "abbreviation", "common_misspelling", "former_name"
    is_primary: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("security_id", "alias", name="uq_company_alias"),
        Index("ix_company_aliases_alias_type", "alias", "alias_type"),
    )