from __future__ import annotations

import json
import logging
import re
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.ai.router import generate
from app.modules.entities.models import CompanyAlias, SecurityMaster

logger = logging.getLogger("fios.intelligence.entity_extractor")


class EntityExtractor:
    """
    Entity extraction using LLM (Qwen via model router) + ticker/company master table.
    The LLM proposes entities; the database confirms them. Never let an unresolved
    entity become a fact.
    """

    def __init__(self, db: AsyncSession, security_master_service):
        self.db = db
        self.security_master = security_master_service

    async def initialize(self):
        pass  # No local model to load

    async def extract_entities(
        self,
        text: str,
        evidence_ids: list[str],
    ) -> list[dict[str, Any]]:
        entities = []

        # 1. LLM-based entity proposal
        try:
            llm_entities = await self._llm_extract(text)
            entities.extend(llm_entities)
        except Exception as e:
            logger.warning(f"LLM entity extraction failed: {e}")

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

    async def _llm_extract(self, text: str) -> list[dict[str, Any]]:
        prompt = f"""Extract financial entities from the following text.

Return a JSON array of objects with fields:
- "text": the entity name as written
- "label": one of "company", "organization", "person", "location", "currency", "commodity", "sector", "industry", "regulator", "government_agency", "financial_instrument"

Only return entities explicitly mentioned or clearly referenced in the text.
Return ONLY valid JSON, no markdown, no explanation.

Text: {text[:4000]}"""

        result = await generate(
            messages=[{"role": "user", "content": prompt}],
            max_tokens=2048,
            temperature=0.1,
        )
        content = result.content.strip()
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            content = content.split("```")[1].split("```")[0]
        content = content.strip()

        raw = json.loads(content)
        entities = []
        for item in raw:
            entities.append({
                "text": item.get("text", ""),
                "label": item.get("label", "other"),
                "score": 0.8,
                "source": "llm",
            })
        return entities

    def _extract_tickers(self, text: str) -> list[dict[str, Any]]:
        entities = []
        nse_pattern = r'\bNSE:([A-Z0-9]{1,15})\b'
        for match in re.finditer(nse_pattern, text):
            entities.append({
                "text": match.group(1),
                "label": "ticker",
                "exchange": "NSE",
                "score": 0.95,
                "source": "pattern",
            })
        bse_pattern = r'\bBSE:([A-Z0-9]{1,15})\b'
        for match in re.finditer(bse_pattern, text):
            entities.append({
                "text": match.group(1),
                "label": "ticker",
                "exchange": "BSE",
                "score": 0.95,
                "source": "pattern",
            })
        symbol_pattern = r'\b([A-Z]{2,15})\b'
        for match in re.finditer(symbol_pattern, text):
            symbol = match.group(1)
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
        entities = []
        result = await self.db.execute(
            select(SecurityMaster.company_name, SecurityMaster.company_short_name, SecurityMaster.nse_symbol, SecurityMaster.id)
            .where(SecurityMaster.is_active == True)
        )
        companies = result.all()
        text_lower = text.lower()
        for company in companies:
            name = company.company_name.lower()
            short = (company.company_short_name or "").lower()
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
        seen = {}
        for e in entities:
            key = (e["text"].lower(), e.get("label", ""))
            if key not in seen or e.get("score", 0) > seen[key].get("score", 0):
                seen[key] = e
        return list(seen.values())

    async def _resolve_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        for entity in entities:
            if entity.get("resolution"):
                continue
            if entity.get("label") == "ticker":
                resolution = await self.security_master.resolve_ticker(
                    entity["text"],
                    entity.get("exchange", "UNKNOWN")
                )
                if resolution:
                    entity["resolved"] = True
                    entity["resolution"] = resolution
            elif entity.get("label") == "company":
                resolution = await self.security_master.resolve_company(entity["text"])
                if resolution:
                    entity["resolved"] = True
                    entity["resolution"] = resolution
        return entities


class SecurityMasterService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def resolve_ticker(self, symbol: str, exchange: str = "UNKNOWN") -> dict[str, Any] | None:
        from app.modules.entities.models import SecurityMaster
        stmt = select(SecurityMaster).where(SecurityMaster.is_active == True)
        if exchange == "NSE":
            stmt = stmt.where(SecurityMaster.nse_symbol == symbol)
        elif exchange == "BSE":
            stmt = stmt.where(SecurityMaster.bse_symbol == symbol)
        else:
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
        from app.modules.entities.models import SecurityMaster
        stmt = select(SecurityMaster).where(
            SecurityMaster.is_active == True,
            SecurityMaster.company_name.ilike(f"%{name}%")
        )
        result = await self.db.execute(stmt)
        security = result.scalar_one_or_none()
        if not security:
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
