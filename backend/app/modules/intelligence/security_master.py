from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.modules.intelligence.openbb import OpenBBClient

logger = logging.getLogger("fios.intelligence.security_master")


class SecurityMasterService:
    """
    Manages the security master table: NSE/BSE ticker -> company -> sector/industry mapping.
    Sourced from OpenBB service and cached in Postgres.
    """

    def __init__(self, db_session):
        self.db = db_session

    async def sync_from_openbb(self) -> dict[str, int]:
        """
        Sync security master from OpenBB service.
        Returns stats: {added, updated, skipped}
        """
        stats = {"added": 0, "updated": 0, "skipped": 0, "errors": 0}

        async with OpenBBClient() as client:
            try:
                equities = await client.get_indian_equities_master()
                logger.info(f"Fetched {len(equities)} equities from OpenBB")
            except Exception as e:
                logger.error(f"Failed to fetch from OpenBB: {e}")
                stats["errors"] = 1
                return stats

        for eq in equities:
            try:
                result = await self._upsert_security(eq)
                if result == "added":
                    stats["added"] += 1
                elif result == "updated":
                    stats["updated"] += 1
                else:
                    stats["skipped"] += 1
            except Exception as e:
                logger.error(f"Error upserting {eq.get('symbol', 'unknown')}: {e}")
                stats["errors"] += 1

        await self.db.commit()
        logger.info(f"Security master sync complete: {stats}")
        return stats

    async def _upsert_security(self, eq: dict[str, Any]) -> str:
        """
        Upsert a security into the master table.
        Returns: "added", "updated", or "skipped"
        """
        from sqlalchemy import select
        from app.modules.entities.models import SecurityMaster, Exchange, Sector, Industry

        # Determine primary symbol and exchange
        nse_symbol = eq.get("nse_symbol") or eq.get("symbol")
        bse_symbol = eq.get("bse_symbol")
        isin = eq.get("isin")

        # Check if exists
        existing = None
        if nse_symbol:
            result = await self.db.execute(
                select(SecurityMaster).where(SecurityMaster.nse_symbol == nse_symbol)
            )
            existing = result.scalar_one_or_none()
        elif bse_symbol:
            result = await self.db.execute(
                select(SecurityMaster).where(SecurityMaster.bse_symbol == bse_symbol)
            )
            existing = result.scalar_one_or_none()

        # Map sector/industry
        sector_str = eq.get("sector", "Other")
        industry_str = eq.get("industry", "Other")

        try:
            sector = Sector(sector_str)
        except ValueError:
            sector = Sector.OTHER

        try:
            industry = Industry(industry_str)
        except ValueError:
            industry = Industry.OTHER

        exchange_str = eq.get("exchange", "NSE")
        try:
            exchange = Exchange(exchange_str)
        except ValueError:
            exchange = Exchange.NSE

        if existing:
            # Update
            existing.nse_symbol = nse_symbol or existing.nse_symbol
            existing.bse_symbol = bse_symbol or existing.bse_symbol
            existing.isin = isin or existing.isin
            existing.company_name = eq.get("name", existing.company_name)
            existing.company_short_name = eq.get("short_name", existing.company_short_name)
            existing.sector = sector
            existing.industry = industry
            existing.sub_industry = eq.get("sub_industry")
            existing.primary_exchange = exchange
            existing.listing_date = self._parse_date(eq.get("listing_date"))
            existing.face_value = eq.get("face_value")
            existing.market_lot = eq.get("market_lot")
            existing.is_active = eq.get("is_active", True)
            existing.is_suspended = eq.get("is_suspended", False)
            existing.openbb_symbol = eq.get("openbb_symbol")
            existing.extra_metadata = str(eq)
            existing.updated_at = datetime.now(timezone.utc)
            return "updated"
        else:
            # Insert
            security = SecurityMaster(
                nse_symbol=nse_symbol,
                bse_symbol=bse_symbol,
                isin=isin,
                company_name=eq.get("name", ""),
                company_short_name=eq.get("short_name"),
                sector=sector,
                industry=industry,
                sub_industry=eq.get("sub_industry"),
                primary_exchange=exchange,
                listing_date=self._parse_date(eq.get("listing_date")),
                face_value=eq.get("face_value"),
                market_lot=eq.get("market_lot"),
                is_active=eq.get("is_active", True),
                is_suspended=eq.get("is_suspended", False),
                openbb_symbol=eq.get("openbb_symbol"),
                extra_metadata=str(eq),
            )
            self.db.add(security)
            return "added"

    def _parse_date(self, date_str: str | None) -> datetime | None:
        if not date_str:
            return None
        for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%Y/%m/%d", "%d/%m/%Y"):
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def resolve_ticker(self, ticker: str) -> dict[str, Any] | None:
        """
        Resolve a ticker (NSE or BSE symbol) to company info.
        Returns dict with company info or None if not found.
        """
        from sqlalchemy import select
        from app.modules.entities.models import SecurityMaster

        result = await self.db.execute(
            select(SecurityMaster).where(
                (SecurityMaster.nse_symbol == ticker.upper()) |
                (SecurityMaster.bse_symbol == ticker.upper())
            )
        )
        security = result.scalar_one_or_none()

        if not security:
            return None

        return {
            "id": str(security.id),
            "nse_symbol": security.nse_symbol,
            "bse_symbol": security.bse_symbol,
            "isin": security.isin,
            "company_name": security.company_name,
            "company_short_name": security.company_short_name,
            "sector": security.sector.value if hasattr(security.sector, 'value') else str(security.sector),
            "industry": security.industry.value if hasattr(security.industry, 'value') else str(security.industry),
            "sub_industry": security.sub_industry,
            "exchange": security.primary_exchange.value if hasattr(security.primary_exchange, 'value') else str(security.primary_exchange),
            "is_active": security.is_active,
            "is_suspended": security.is_suspended,
        }

    async def search_companies(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        """Search companies by name or symbol"""
        from sqlalchemy import select, or_, func
        from app.modules.entities.models import SecurityMaster

        result = await self.db.execute(
            select(SecurityMaster)
            .where(
                or_(
                    SecurityMaster.company_name.ilike(f"%{query}%"),
                    SecurityMaster.nse_symbol.ilike(f"%{query}%"),
                    SecurityMaster.bse_symbol.ilike(f"%{query}%"),
                )
            )
            .where(SecurityMaster.is_active == True)
            .limit(limit)
        )
        securities = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "nse_symbol": s.nse_symbol,
                "bse_symbol": s.bse_symbol,
                "company_name": s.company_name,
                "company_short_name": s.company_short_name,
                "sector": s.sector.value if hasattr(s.sector, 'value') else str(s.sector),
                "industry": s.industry.value if hasattr(s.industry, 'value') else str(s.industry),
            }
            for s in securities
        ]

    async def get_sector_constituents(self, sector: str, limit: int = 100) -> list[dict[str, Any]]:
        """Get all companies in a sector"""
        from sqlalchemy import select
        from app.modules.entities.models import SecurityMaster, Sector as SectorEnum

        try:
            sector_enum = SectorEnum(sector)
        except ValueError:
            return []

        result = await self.db.execute(
            select(SecurityMaster)
            .where(SecurityMaster.sector == sector_enum)
            .where(SecurityMaster.is_active == True)
            .limit(limit)
        )
        securities = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "nse_symbol": s.nse_symbol,
                "bse_symbol": s.bse_symbol,
                "company_name": s.company_name,
                "sector": s.sector.value if hasattr(s.sector, 'value') else str(s.sector),
                "industry": s.industry.value if hasattr(s.industry, 'value') else str(s.industry),
            }
            for s in securities
        ]