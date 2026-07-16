from __future__ import annotations

import csv
import io
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import and_, delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.audit.models import AuditLog
from app.modules.portfolios.models import (
    AlertPreference,
    Holding,
    HoldingImpact,
    Portfolio,
    PortfolioAlert,
)

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


# Pydantic models
class PortfolioCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    description: str | None = None


class PortfolioUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=256)
    description: str | None = None


class HoldingCreate(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)
    exchange: str = Field(..., pattern="^(NSE|BSE)$")
    isin: str | None = Field(None, pattern="^[A-Z]{2}[A-Z0-9]{9}[0-9]{1}$")
    company_name: str = Field(..., min_length=1, max_length=256)
    sector: str | None = None
    industry: str | None = None
    country: str = Field(default="IN", min_length=2, max_length=2)
    quantity: float = Field(..., gt=0)
    weight: float = Field(..., gt=0, le=100)
    avg_price: float | None = None
    current_price: float | None = None
    market_value: float | None = None


class HoldingUpdate(BaseModel):
    quantity: float | None = Field(None, gt=0)
    weight: float | None = Field(None, gt=0, le=100)
    avg_price: float | None = None
    current_price: float | None = None
    market_value: float | None = None


class AlertPreferenceUpdate(BaseModel):
    enable_new_direct_exposure: bool | None = None
    enable_new_indirect_exposure: bool | None = None
    enable_material_event: bool | None = None
    enable_changed_assessment: bool | None = None
    min_severity: str | None = None
    internal_web: bool | None = None
    internal_email: bool | None = None


class PortfolioResponse(BaseModel):
    id: str
    name: str
    description: str | None
    tenant_id: str
    created_at: str
    updated_at: str
    holdings_count: int = 0
    total_market_value: float | None = None


class HoldingResponse(BaseModel):
    id: str
    portfolio_id: str
    ticker: str
    exchange: str
    isin: str | None
    company_name: str
    sector: str | None
    industry: str | None
    country: str
    quantity: float
    weight: float
    avg_price: float | None
    current_price: float | None
    market_value: float | None
    created_at: str
    updated_at: str


class HoldingImpactResponse(BaseModel):
    id: str
    event_id: str
    holding_id: str
    classification: str
    impact_score: float
    confidence: float
    uncertainty: float
    reasoning: str
    citations: list[str]
    verified_relationships: list[str]
    inferred_relationships: list[str]
    impact_horizon: str | None
    assessed_at: str


class PortfolioAlertResponse(BaseModel):
    id: str
    portfolio_id: str
    alert_type: str
    title: str
    message: str
    severity: str
    event_id: str | None
    holding_id: str | None
    is_read: bool
    created_at: str


class ExposureSummaryResponse(BaseModel):
    directly_affected: int
    indirectly_affected: int
    possible_beneficiaries: int
    possible_negative_exposures: int
    uncertain: int
    no_material_evidence: int
    total_holdings: int


class AlertPreferenceResponse(BaseModel):
    enable_new_direct_exposure: bool
    enable_new_indirect_exposure: bool
    enable_material_event: bool
    enable_changed_assessment: bool
    min_severity: str
    internal_web: bool
    internal_email: bool


# Helper functions
def serialize_portfolio(p: Portfolio, holdings_count: int = 0, total_market_value: float | None = None) -> dict:
    return {
        "id": str(p.id),
        "name": p.name,
        "description": p.description,
        "tenant_id": str(p.tenant_id),
        "created_at": p.created_at.isoformat() if p.created_at else None,
        "updated_at": p.updated_at.isoformat() if p.updated_at else None,
        "holdings_count": holdings_count,
        "total_market_value": total_market_value,
    }


def serialize_holding(h: Holding) -> dict:
    return {
        "id": str(h.id),
        "portfolio_id": str(h.portfolio_id),
        "ticker": h.ticker,
        "exchange": h.exchange,
        "isin": h.isin,
        "company_name": h.company_name,
        "sector": h.sector,
        "industry": h.industry,
        "country": h.country,
        "quantity": h.quantity,
        "weight": h.weight,
        "avg_price": h.avg_price,
        "current_price": h.current_price,
        "market_value": h.market_value,
        "created_at": h.created_at.isoformat() if h.created_at else None,
        "updated_at": h.updated_at.isoformat() if h.updated_at else None,
    }


def serialize_holding_impact(hi: HoldingImpact) -> dict:
    return {
        "id": str(hi.id),
        "event_id": str(hi.event_id),
        "holding_id": str(hi.holding_id),
        "classification": hi.classification.value if hasattr(hi.classification, 'value') else str(hi.classification),
        "impact_score": hi.impact_score,
        "confidence": hi.confidence,
        "uncertainty": hi.uncertainty,
        "reasoning": hi.reasoning,
        "citations": hi.citations,
        "verified_relationships": hi.verified_relationships,
        "inferred_relationships": hi.inferred_relationships,
        "impact_horizon": hi.impact_horizon,
        "assessed_at": hi.assessed_at.isoformat() if hi.assessed_at else None,
    }


def serialize_alert(a: PortfolioAlert) -> dict:
    return {
        "id": str(a.id),
        "portfolio_id": str(a.portfolio_id),
        "alert_type": a.alert_type,
        "title": a.title,
        "message": a.message,
        "severity": a.severity,
        "event_id": str(a.event_id) if a.event_id else None,
        "holding_id": str(a.holding_id) if a.holding_id else None,
        "is_read": a.is_read,
        "created_at": a.created_at.isoformat() if a.created_at else None,
    }


# CSV Upload
@router.post("/upload", response_model=dict)
async def upload_portfolio_csv(
    file: UploadFile = File(...),
    portfolio_name: str = Query(...),
    portfolio_description: str | None = Query(None),
    tenant_id: uuid.UUID = Query(...),  # In production, get from auth
    db: AsyncSession = Depends(get_db),
):
    """Upload portfolio from CSV file"""
    if not file.filename.endswith(".csv") or file.content_type not in (
        "text/csv", "application/vnd.ms-excel", "text/plain",
    ):
        raise HTTPException(400, "File must be a CSV")

    content = await file.read()
    if len(content) > 5 * 1024 * 1024:  # 5MB limit
        raise HTTPException(400, "File too large (max 5MB)")

    try:
        text = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(400, "File must be UTF-8 encoded")

    reader = csv.DictReader(io.StringIO(text))
    required_columns = {"ticker", "exchange", "company_name", "quantity", "weight"}
    if not reader.fieldnames or not required_columns.issubset(set(reader.fieldnames)):
        missing = required_columns - set(reader.fieldnames or [])
        raise HTTPException(400, f"Missing required columns: {missing}")

    rows = list(reader)
    if not rows:
        raise HTTPException(400, "CSV has no data rows")

    # Validate each row
    holdings_data = []
    total_weight = 0.0
    for i, row in enumerate(rows):
        try:
            ticker = row["ticker"].strip().upper()
            exchange = row["exchange"].strip().upper()
            if exchange not in ("NSE", "BSE"):
                raise ValueError(f"Row {i+1}: exchange must be NSE or BSE")
            company_name = row["company_name"].strip()
            quantity = float(row["quantity"])
            weight = float(row["weight"])
            if quantity <= 0:
                raise ValueError(f"Row {i+1}: quantity must be positive")
            if weight <= 0 or weight > 100:
                raise ValueError(f"Row {i+1}: weight must be between 0 and 100")

            holdings_data.append({
                "ticker": ticker,
                "exchange": exchange,
                "isin": row.get("isin", "").strip().upper() or None,
                "company_name": company_name,
                "sector": row.get("sector", "").strip() or None,
                "industry": row.get("industry", "").strip() or None,
                "country": row.get("country", "IN").strip().upper() or "IN",
                "quantity": quantity,
                "weight": weight,
                "avg_price": float(row["avg_price"]) if row.get("avg_price") else None,
                "current_price": float(row["current_price"]) if row.get("current_price") else None,
                "market_value": float(row["market_value"]) if row.get("market_value") else None,
            })
            total_weight += weight
        except (ValueError, KeyError) as e:
            raise HTTPException(400, f"Row {i+1}: {e}")

    if abs(total_weight - 100.0) > 0.1:
        raise HTTPException(400, f"Total weight must equal 100%, got {total_weight}")

    # Create portfolio
    portfolio = Portfolio(
        name=portfolio_name,
        description=portfolio_description,
        tenant_id=tenant_id,
    )
    db.add(portfolio)
    await db.flush()

    # Create holdings
    for hd in holdings_data:
        holding = Holding(
            portfolio_id=portfolio.id,
            tenant_id=tenant_id,
            **hd,
        )
        db.add(holding)

    # Create default alert preferences
    alert_pref = AlertPreference(
        portfolio_id=portfolio.id,
        tenant_id=tenant_id,
    )
    db.add(alert_pref)

    await db.commit()

    # Audit log
    audit = AuditLog(
        user_id=None,
        action="portfolio_upload",
        resource_type="portfolio",
        resource_id=str(portfolio.id),
        details=f"Uploaded portfolio '{portfolio_name}' with {len(holdings_data)} holdings",
        ip_address=None,
    )
    db.add(audit)
    await db.commit()

    return {
        "portfolio_id": str(portfolio.id),
        "name": portfolio.name,
        "holdings_created": len(holdings_data),
        "message": "Portfolio uploaded successfully",
    }


# Portfolio CRUD
@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_portfolio(
    data: PortfolioCreate,
    tenant_id: uuid.UUID = Query(...),  # In production, get from auth
    db: AsyncSession = Depends(get_db),
):
    portfolio = Portfolio(
        name=data.name,
        description=data.description,
        tenant_id=tenant_id,
    )
    db.add(portfolio)
    await db.flush()

    # Default alert preferences
    alert_pref = AlertPreference(portfolio_id=portfolio.id, tenant_id=tenant_id)
    db.add(alert_pref)

    await db.commit()

    # Audit
    audit = AuditLog(
        action="portfolio_create",
        resource_type="portfolio",
        resource_id=str(portfolio.id),
        details=f"Created portfolio '{data.name}'",
    )
    db.add(audit)
    await db.commit()

    return {"id": str(portfolio.id), "name": portfolio.name}


@router.get("", response_model=list[dict])
async def list_portfolios(
    tenant_id: uuid.UUID = Query(...),
    include_deleted: bool = False,
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(Portfolio).where(Portfolio.tenant_id == tenant_id)
    if not include_deleted:
        query = query.where(Portfolio.deleted_at.is_(None))

    query = query.order_by(desc(Portfolio.created_at)).limit(limit).offset(offset)
    result = await db.execute(query)
    portfolios = result.scalars().all()

    portfolio_ids = [p.id for p in portfolios]
    if portfolio_ids:
        agg_result = await db.execute(
            select(
                Holding.portfolio_id,
                func.count(Holding.id),
                func.sum(Holding.market_value),
            ).where(Holding.portfolio_id.in_(portfolio_ids))
            .group_by(Holding.portfolio_id)
        )
        agg_map = {row[0]: (row[1] or 0, row[2]) for row in agg_result.all()}
    else:
        agg_map = {}

    return [
        serialize_portfolio(p, *agg_map.get(p.id, (0, None)))
        for p in portfolios
    ]


@router.get("/{portfolio_id}", response_model=dict)
async def get_portfolio(
    portfolio_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Portfolio).where(
            and_(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # Get holdings count and total value
    holdings_result = await db.execute(
        select(func.count(Holding.id), func.sum(Holding.market_value))
        .where(Holding.portfolio_id == portfolio_id)
    )
    count, total_value = holdings_result.first() or (0, None)

    return {**serialize_portfolio(portfolio, count, total_value)}


@router.patch("/{portfolio_id}", response_model=dict)
async def update_portfolio(
    portfolio_id: uuid.UUID,
    data: PortfolioUpdate,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Portfolio).where(
            and_(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    if data.name is not None:
        portfolio.name = data.name
    if data.description is not None:
        portfolio.description = data.description

    await db.commit()

    # Audit
    audit = AuditLog(
        action="portfolio_update",
        resource_type="portfolio",
        resource_id=str(portfolio.id),
        details=f"Updated portfolio '{portfolio.name}'",
    )
    db.add(audit)
    await db.commit()

    return {"id": str(portfolio.id), "name": portfolio.name}


@router.delete("/{portfolio_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_portfolio(
    portfolio_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    secure: bool = Query(False),  # Secure deletion - overwrite data before deleting
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Portfolio).where(
            and_(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
        )
    )
    portfolio = result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    if secure:
        # Secure deletion: overwrite sensitive data before deleting
        # Update holdings with random data
        await db.execute(
            Holding.__table__.update()
            .where(Holding.portfolio_id == portfolio_id)
            .values(
                company_name="[DELETED]",
                ticker="[DELETED]",
                isin=None,
                sector=None,
                industry=None,
                quantity=0,
                weight=0,
                avg_price=None,
                current_price=None,
                market_value=None,
                extra_metadata=None,
            )
        )

        # Delete related records
        await db.execute(delete(HoldingImpact).where(HoldingImpact.portfolio_id == portfolio_id))
        await db.execute(delete(PortfolioAlert).where(PortfolioAlert.portfolio_id == portfolio_id))
        await db.execute(delete(AlertPreference).where(AlertPreference.portfolio_id == portfolio_id))

        # Hard delete holdings
        await db.execute(delete(Holding).where(Holding.portfolio_id == portfolio_id))
    else:
        # Soft delete
        portfolio.deleted_at = datetime.now(timezone.utc)
        # Also soft delete holdings
        await db.execute(
            Holding.__table__.update()
            .where(Holding.portfolio_id == portfolio_id)
            .values(deleted_at=datetime.now(timezone.utc))
        )

    await db.commit()

    # Audit
    audit = AuditLog(
        action="portfolio_delete",
        resource_type="portfolio",
        resource_id=str(portfolio_id),
        details=f"Deleted portfolio '{portfolio.name}' (secure={secure})",
    )
    db.add(audit)
    await db.commit()


# Holdings
@router.get("/{portfolio_id}/holdings", response_model=list[dict])
async def list_holdings(
    portfolio_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    sector: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    # Verify portfolio access
    portfolio_result = await db.execute(
        select(Portfolio).where(
            and_(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
        )
    )
    if not portfolio_result.scalar_one_or_none():
        raise HTTPException(404, "Portfolio not found")

    query = select(Holding).where(Holding.portfolio_id == portfolio_id)
    if sector:
        query = query.where(Holding.sector == sector)

    query = query.order_by(desc(Holding.weight)).limit(limit).offset(offset)
    result = await db.execute(query)
    holdings = result.scalars().all()

    return [serialize_holding(h) for h in holdings]


@router.post("/{portfolio_id}/holdings", response_model=dict, status_code=status.HTTP_201_CREATED)
async def add_holding(
    portfolio_id: uuid.UUID,
    data: HoldingCreate,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    # Verify portfolio
    portfolio_result = await db.execute(
        select(Portfolio).where(
            and_(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
        )
    )
    portfolio = portfolio_result.scalar_one_or_none()
    if not portfolio:
        raise HTTPException(404, "Portfolio not found")

    # Check for duplicate
    existing = await db.execute(
        select(Holding).where(
            and_(
                Holding.portfolio_id == portfolio_id,
                Holding.ticker == data.ticker.upper(),
                Holding.exchange == data.exchange.upper(),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Holding with this ticker and exchange already exists")

    holding = Holding(
        portfolio_id=portfolio_id,
        tenant_id=tenant_id,
        ticker=data.ticker.upper(),
        exchange=data.exchange.upper(),
        isin=data.isin,
        company_name=data.company_name,
        sector=data.sector,
        industry=data.industry,
        country=data.country,
        quantity=data.quantity,
        weight=data.weight,
        avg_price=data.avg_price,
        current_price=data.current_price,
        market_value=data.market_value,
    )
    db.add(holding)
    await db.commit()

    return {"id": str(holding.id), "message": "Holding added"}


@router.patch("/{portfolio_id}/holdings/{holding_id}", response_model=dict)
async def update_holding(
    portfolio_id: uuid.UUID,
    holding_id: uuid.UUID,
    data: HoldingUpdate,
    tenant_id: uuid.UUID = Query(...),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Holding).where(
            and_(
                Holding.id == holding_id,
                Holding.portfolio_id == portfolio_id,
                Holding.tenant_id == tenant_id,
            )
        )
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(404, "Holding not found")

    if data.quantity is not None:
        holding.quantity = data.quantity
    if data.weight is not None:
        holding.weight = data.weight
    if data.avg_price is not None:
        holding.avg_price = data.avg_price
    if data.current_price is not None:
        holding.current_price = data.current_price
    if data.market_value is not None:
        holding.market_value = data.market_value

    await db.commit()
    return {"id": str(holding.id), "message": "Holding updated"}


@router.delete("/{portfolio_id}/holdings/{holding_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_holding(
    portfolio_id: uuid.UUID,
    holding_id: uuid.UUID,
    tenant_id: uuid.UUID = Query(...),
    secure: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Holding).where(
            and_(
                Holding.id == holding_id,
                Holding.portfolio_id == portfolio_id,
                Holding.tenant_id == tenant_id,
            )
        )
    )
    holding = result.scalar_one_or_none()
    if not holding:
        raise HTTPException(404, "Holding not found")

    if secure:
        # Overwrite before deleting
        await db.execute(
            Holding.__table__.update()
            .where(Holding.id == holding_id)
            .values(
                company_name="[DELETED]",
                ticker="[DELETED]",
                isin=None,
                sector=None,
                industry=None,
                quantity=0,
                weight=0,
                avg_price=None,
                current_price=None,
                market_value=None,
                extra_metadata=None,
            )
        )

    await db.execute(delete(Holding).where(Holding.id == holding_id))
    await db.commit()
