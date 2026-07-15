from __future__ import annotations

import logging
import uuid
import re
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.modules.entities.models import SecurityMaster, CompanyAlias, Sector, Industry, Exchange
from app.modules.intelligence.validation import ValidationService, ConfidenceService

logger = logging.getLogger("fios.intelligence.entity_extractor")


class EntityExtractor:
    """
    Entity extraction using GLiNER (urchade/gliner_multi) + ticker/company master table.
    """

    def __init__(self, db: AsyncSession, security_master_service):
        self.db = db
        self.security_master = security_master_service
        self._gliner = None
        self._initialized = False

    async def initialize(self):
        """Initialize GLiNER model"""
        try:
            from gliner import GLiNER
            self._gliner = GLiNER.from_pretrained("urchade/gliner_multi")
            self._initialized = True
            logger.info("GLiNER model initialized")
        except Exception as e:
            logger.error(f"Failed to initialize GLiNER: {e}")
            self._initialized = False

    async def extract_entities(
        self,
        text: str,
        evidence_ids: list[str],
    ) -> list[dict[str, Any]]:
        """
        Extract entities using GLiNER, then resolve against security master.
        """
        if not self._initialized:
            await self.initialize()

        entities = []

        # 1. GLiNER extraction
        if self._initialized:
            gliner_entities = await self._gliner_extract(text)
            entities.extend(gliner_entities)

        # 2. Ticker pattern extraction (Indian tickers)
        ticker_entities = self._extract_tickers(text)
        entities.extend(ticker_entities)

        # 3. Company name fuzzy matching against security master
        company_entities = await self._extract_companies(text)
        entities.extend(company_entities)

        # 4. Deduplicate and resolve
        deduplicated = self._deduplicate_entities(entities)
        resolved = await self._resolve_entities(deduplicated)

        return resolved

    async def _gliner_extract(self, text: str) -> list[dict[str, Any]]:
        """Extract entities using GLiNER"""
        try:
            labels = [
                "company", "organization", "person", "location",
                "currency", "commodity", "sector", "industry",
                "regulator", "government_agency", "financial_instrument"
            ]
            results = self._gliner.predict_entities(text, labels, threshold=0.5)

            entities = []
            for r in results:
                entities.append({
                    "text": r["text"],
                    "label": r["label"],
                    "score": r["score"],
                    "start": r["start"],
                    "end": r["end"],
                    "source": "gliner",
                })
            return entities
        except Exception as e:
            logger.warning(f"GLiNER extraction failed: {e}")
            return []

    def _extract_tickers(self, text: str) -> list[dict[str, Any]]:
        """Extract Indian tickers (NSE:SYMBOL, BSE:SYMBOL, SYMBOL)"""
        entities = []

        # NSE:SYMBOL pattern
        nse_pattern = r'\bNSE:([A-Z0-9]{1,15})\b'
        for match in re.finditer(nse_pattern, text):
            entities.append({
                "text": match.group(1),
                "label": "ticker",
                "exchange": "NSE",
                "score": 0.95,
                "source": "pattern",
            })

        # BSE:SYMBOL pattern
        bse_pattern = r'\bBSE:([A-Z0-9]{1,15})\b'
        for match in re.finditer(bse_pattern, text):
            entities.append({
                "text": match.group(1),
                "label": "ticker",
                "exchange": "BSE",
                "score": 0.95,
                "source": "pattern",
            })

        # Standalone symbol pattern (all caps, 2-15 chars, word boundary)
        # More restrictive to avoid false positives
        symbol_pattern = r'\b([A-Z]{2,15})\b'
        for match in re.finditer(symbol_pattern, text):
            symbol = match.group(1)
            # Filter common false positives
            if symbol not in {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "ANY", "CAN", "HAS", "HAD", "WAS", "WERE", "BEEN", "THIS", "THAT", "WITH", "FROM", "THEY", "WE", "YOUR", "OUR", "THEIR"}:
                entities.append({
                    "text": symbol,
                    "label": "ticker",
                    "exchange": "UNKNOWN",
                    "score": 0.5,
                    "source": "pattern",
                })

        return entities

    async def _extract_companies(self, text: str) -> list[dict[str, Any]]:
        """Fuzzy match company names against security master"""
        entities = []

        # Get all company names from security master
        result = await self.db.execute(
            select(SecurityMaster.company_name, SecurityMaster.company_short_name, SecurityMaster.nse_symbol, SecurityMaster.id)
            .where(SecurityMaster.is_active == True)
        )
        companies = result.all()

        text_lower = text.lower()
        for company in companies:
            name = company.company_name.lower()
            short = (company.company_short_name or "").lower()

            # Check full name
            if name in text_lower:
                entities.append({
                    "text": company.company_name,
                    "label": "company",
                    "score": 0.8,
                    "resolution": {
                        "id": str(company.id),
                        "company_name": company.company_name,
                        "nse_symbol": company.nse_symbol,
                    },
                    "source": "security_master",
                })
            # Check short name (if > 3 chars to avoid false positives)
            elif short and len(short) > 3 and short in text_lower:
                entities.append({
                    "text": company.company_short_name,
                    "label": "company",
                    "score": 0.7,
                    "resolution": {
                        "id": str(company.id),
                        "company_name": company.company_name,
                        "nse_symbol": company.nse_symbol,
                    },
                    "source": "security_master",
                })

        return entities

    def _deduplicate_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merge duplicate entities by text and label"""
        seen = {}
        for e in entities:
            key = (e["text"].lower(), e.get("label", ""))
            if key not in seen or e.get("score", 0) > seen[key].get("score", 0):
                seen[key] = e
        return list(seen.values())

    async def _resolve_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Resolve entities against security master and company aliases"""
        for entity in entities:
            if entity.get("resolution"):
                continue  # Already resolved

            if entity.get("label") == "ticker":
                # Resolve ticker
                resolution = await self.security_master.resolve_ticker(
                    entity["text"],
                    entity.get("exchange", "UNKNOWN")
                )
                if resolution:
                    entity["resolved"] = True
                    entity["resolution"] = resolution
            elif entity.get("label") == "company":
                # Resolve company name
                resolution = await self.security_master.resolve_company(entity["text"])
                if resolution:
                    entity["resolved"] = True
                    entity["resolution"] = resolution

        return entities


class SecurityMasterService:
    """
    Security master service: NSE/BSE ticker -> company -> sector/industry mapping.
    Sourced from OpenBB service; cached in Postgres.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_ticker(self, symbol: str, exchange: str = "UNKNOWN") -> dict[str, Any] | None:
        """Resolve ticker symbol to security master entry"""
        from app.modules.entities.models import SecurityMaster

        stmt = select(SecurityMaster).where(SecurityMaster.is_active == True)

        if exchange == "NSE":
            stmt = stmt.where(SecurityMaster.nse_symbol == symbol)
        elif exchange == "BSE":
            stmt = stmt.where(SecurityMaster.bse_symbol == symbol)
        else:
            # Try both
            stmt = stmt.where(
                (SecurityMaster.nse_symbol == symbol) |
                (SecurityMaster.bse_symbol == symbol)
            )

        result = await self.db.execute(stmt)
        security = result.scalar_one_or_none()

        if security:
            return {
                "id": str(security.id),
                "company_name": security.company_name,
                "nse_symbol": security.nse_symbol,
                "bse_symbol": security.bse_symbol,
                "sector": security.sector.value if hasattr(security.sector, 'value') else str(security.sector),
                "industry": security.industry.value if hasattr(security.industry, 'value') else str(security.industry),
            }
        return None

    async def resolve_company(self, name: str) -> dict[str, Any] | None:
        """Fuzzy resolve company name"""
        from app.modules.entities.models import SecurityMaster, CompanyAlias

        # Try exact match first
        stmt = select(SecurityMaster).where(
            SecurityMaster.is_active == True,
            SecurityMaster.company_name.ilike(f"%{name}%")
        )
        result = await self.db.execute(stmt)
        security = result.scalar_one_or_none()

        if not security:
            # Try alias match
            stmt = select(CompanyAlias, SecurityMaster).join(
                SecurityMaster, CompanyAlias.security_id == SecurityMaster.id
            ).where(
                SecurityMaster.is_active == True,
                CompanyAlias.alias.ilike(f"%{name}%")
            )
            result = await self.db.execute(stmt)
            row = result.first()
            if row:
                security = row[1]

        if security:
            return {
                "id": str(security.id),
                "company_name": security.company_name,
                "nse_symbol": security.nse_symbol,
                "bse_symbol": security.bse_symbol,
                "sector": security.sector.value if hasattr(security.sector, 'value') else str(security.sector),
                "industry": security.industry.value if hasattr(security.industry, 'value') else str(security.industry),
            }
        return None

    async def get_sector_companies(self, sector: str) -> list[dict[str, Any]]:
        """Get all companies in a sector"""
        from app.modules.entities.models import SecurityMaster

        stmt = select(SecurityMaster).where(
            SecurityMaster.is_active == True,
            SecurityMaster.sector == sector
        )
        result = await self.db.execute(stmt)
        securities = result.scalars().all()

        return [
            {
                "id": str(s.id),
                "company_name": s.company_name,
                "nse_symbol": s.nse_symbol,
                "bse_symbol": s.bse_symbol,
                "industry": s.industry.value if hasattr(s.industry, 'value') else str(s.industry),
            }
            for s in securities
        ]