from __future__ import annotations

import logging
import re
from typing import Any

logger = logging.getLogger("fios.intelligence.entity_extraction")


class EntityExtractor:
    """
    Entity extraction using GLiNER (urchade/gliner_multi) + ticker/company master table.
    """

    def __init__(self, db_session, security_master_service):
        self.db = db_session
        self.security_master = security_master_service
        self._gliner_model = None
        self._ticker_pattern = re.compile(r'\b([A-Z]{2,10})\b')  # Simple ticker pattern
        self._currency_pattern = re.compile(r'\b(USD|INR|EUR|GBP|JPY|CNY|AUD|CAD|CHF)\b', re.IGNORECASE)
        self._commodity_pattern = re.compile(r'\b(oil|gold|silver|copper|aluminium|steel|coal|gas|wheat|corn|soybean|cotton|sugar|coffee|cocoa)\b', re.IGNORECASE)

    async def initialize(self):
        """Load GLiNER model"""
        try:
            from gliner import GLiNER
            self._gliner_model = GLiNER.from_pretrained("urchade/gliner_multi")
            logger.info("GLiNER model loaded successfully")
        except Exception as e:
            logger.warning(f"GLiNER not available: {e}")

    def _get_gliner_labels(self) -> list[str]:
        """Labels for GLiNER entity extraction"""
        return [
            "company", "organization", "person", "location",
            "ticker", "stock", "currency", "commodity",
            "regulator", "government", "sector", "industry",
            "event", "date", "money", "percentage"
        ]

    async def extract_entities(self, text: str, evidence_ids: list[str] | None = None) -> list[dict[str, Any]]:
        """
        Extract entities from text using GLiNER + ticker/company master table.
        Returns list of entity dicts with resolution info.
        """
        entities = []

        # 1. GLiNER extraction (if available)
        if self._gliner_model:
            gliner_entities = await self._extract_with_gliner(text)
            entities.extend(gliner_entities)

        # 2. Ticker/symbol extraction via regex + master table
        ticker_entities = await self._extract_tickers(text)
        entities.extend(ticker_entities)

        # 3. Currency extraction
        currency_entities = self._extract_currencies(text)
        entities.extend(currency_entities)

        # 4. Commodity extraction
        commodity_entities = self._extract_commodities(text)
        entities.extend(commodity_entities)

        # 5. Deduplicate and resolve
        resolved = await self._resolve_entities(entities)

        # Add evidence references
        if evidence_ids:
            for e in resolved:
                e["evidence_ids"] = evidence_ids

        return resolved

    async def _extract_with_gliner(self, text: str) -> list[dict[str, Any]]:
        """Extract entities using GLiNER"""
        if not self._gliner_model:
            return []

        try:
            labels = self._get_gliner_labels()
            predictions = self._gliner_model.predict_entities(text, labels, threshold=0.5)

            entities = []
            for pred in predictions:
                entities.append({
                    "text": pred["text"],
                    "label": pred["label"],
                    "start": pred["start"],
                    "end": pred["end"],
                    "score": pred["score"],
                    "source": "gliner",
                })
            return entities
        except Exception as e:
            logger.warning(f"GLiNER extraction failed: {e}")
            return []

    async def _extract_tickers(self, text: str) -> list[dict[str, Any]]:
        """Extract tickers via regex + master table lookup"""
        entities = []

        # Find potential tickers
        matches = self._ticker_pattern.finditer(text)
        for match in matches:
            ticker = match.group(1)

            # Skip common false positives
            if ticker in {"THE", "AND", "FOR", "ARE", "BUT", "NOT", "YOU", "ALL", "CAN", "HER", "WAS", "ONE", "OUR", "OUT", "DAY", "GET", "HAS", "HIM", "HIS", "HOW", "ITS", "MAY", "NEW", "NOW", "OLD", "SEE", "TWO", "WHO", "BOY", "DID", "MAN", "TOO", "USE"}:
                continue

            # Lookup in security master
            resolved = await self.security_master.resolve_ticker(ticker)
            if resolved:
                entities.append({
                    "text": ticker,
                    "label": "ticker",
                    "start": match.start(),
                    "end": match.end(),
                    "score": 0.95,
                    "source": "security_master",
                    "resolved": True,
                    "resolution": resolved,
                })
            else:
                # Unknown ticker - still capture but mark unresolved
                entities.append({
                    "text": ticker,
                    "label": "ticker",
                    "start": match.start(),
                    "end": match.end(),
                    "score": 0.5,
                    "source": "regex",
                    "resolved": False,
                })

        return entities

    def _extract_currencies(self, text: str) -> list[dict[str, Any]]:
        entities = []
        for match in self._currency_pattern.finditer(text):
            entities.append({
                "text": match.group(1).upper(),
                "label": "currency",
                "start": match.start(),
                "end": match.end(),
                "score": 0.9,
                "source": "regex",
                "resolved": True,
            })
        return entities

    def _extract_commodities(self, text: str) -> list[dict[str, Any]]:
        entities = []
        for match in self._commodity_pattern.finditer(text):
            entities.append({
                "text": match.group(1).lower(),
                "label": "commodity",
                "start": match.start(),
                "end": match.end(),
                "score": 0.8,
                "source": "regex",
                "resolved": True,
            })
        return entities

    async def _resolve_entities(self, entities: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Deduplicate and resolve entities"""
        # Group by (text, label) keeping highest score
        seen: dict[tuple[str, str], dict] = {}

        for e in entities:
            key = (e["text"].lower(), e["label"])
            if key not in seen or e["score"] > seen[key]["score"]:
                seen[key] = e

        # Try to resolve unresolved tickers via fuzzy search
        for e in seen.values():
            if e["label"] == "ticker" and not e.get("resolved", False):
                results = await self.security_master.search_companies(e["text"])
                if results:
                    e["resolved"] = True
                    e["resolution"] = results[0]
                    e["score"] = max(e["score"], 0.8)

        return list(seen.values())