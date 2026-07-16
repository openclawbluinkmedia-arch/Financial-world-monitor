from __future__ import annotations

import logging

logger = logging.getLogger("fios.copilot.query_classifier")


class QueryClassification:
    intent: str
    needs_portfolio: bool
    needs_evidence_search: bool
    entity_focus: str | None
    sector_focus: str | None

    def __init__(self, intent: str, needs_portfolio: bool = False, needs_evidence_search: bool = True, entity_focus: str | None = None, sector_focus: str | None = None):
        self.intent = intent
        self.needs_portfolio = needs_portfolio
        self.needs_evidence_search = needs_evidence_search
        self.entity_focus = entity_focus
        self.sector_focus = sector_focus


POSITIVE_KEYWORDS = [
    "beneficiary", "benefit", "positive", "gain", "opportunity", "upside", "bullish", "growth",
    "profit", "advantage", "favorable", "boost", "rally", "outperform", "overweight",
]

NEGATIVE_KEYWORDS = [
    "negative", "risk", "exposure", "downside", "bearish", "loss", "decline", "fall", "drop",
    "crash", "penalty", "fine", "investigation", "lawsuit", "regulatory", "sanction",
    "underperform", "underweight", "downgrade", "sell-off",
]

REGULATORY_KEYWORDS = [
    "regulation", "regulatory", "rbi", "sebi", "reserve bank", "board", "circular",
    "compliance", "policy change", "draft", "notification", "guideline", "amendment",
]

PORTFOLIO_KEYWORDS = [
    "my portfolio", "my holdings", "my positions", "my investments", "my stocks",
    "portfolio impact", "affect my", "my exposure", "do i own", "should i",
    "holdings impact", "portfolio risk", "my allocation",
]

SECTOR_KEYWORDS = [
    "banking", "it", "pharma", "automobile", "fmcg", "oil and gas", "power", "renewable",
    "telecom", "metal", "mining", "real estate", "construction", "infrastructure",
    "textile", "chemical", "consumer", "retail", "healthcare", "insurance", "finance",
    "technology", "manufacturing", "defense", "aviation", "shipping",
]

MARKET_INTEL_KEYWORDS = [
    "market", "stock", "index", "nifty", "sensex", "sector", "industry", "economy",
    "gdp", "inflation", "interest rate", "monetary policy", "budget", "trade",
    "what is", "explain", "tell me about", "news", "update", "recent",
]


async def classify_query(query: str, mode: str) -> QueryClassification:
    query_lower = query.lower()

    intent = "general"
    needs_portfolio = False
    needs_evidence_search = True
    entity_focus = None
    sector_focus = None

    # Mode-based classification
    if mode == "portfolio_impact":
        needs_portfolio = True
        intent = "portfolio_impact"

    # Keyword-based classification
    if any(kw in query_lower for kw in PORTFOLIO_KEYWORDS):
        needs_portfolio = True
        if "impact" in query_lower or "affect" in query_lower:
            intent = "portfolio_impact"
        else:
            intent = "portfolio_query"

    if any(kw in query_lower for kw in REGULATORY_KEYWORDS):
        intent = "regulatory"

    if any(kw in query_lower for kw in MARKET_INTEL_KEYWORDS):
        if intent == "general":
            intent = "market_intelligence"

    # Check for specific entity
    for kw in SECTOR_KEYWORDS:
        if kw in query_lower:
            sector_focus = kw
            break

    logger.info(
        f"Query classification: intent={intent}, needs_portfolio={needs_portfolio}, "
        f"entity_focus={entity_focus}, sector_focus={sector_focus}"
    )

    return QueryClassification(
        intent=intent,
        needs_portfolio=needs_portfolio,
        needs_evidence_search=needs_evidence_search,
        entity_focus=entity_focus,
        sector_focus=sector_focus,
    )
