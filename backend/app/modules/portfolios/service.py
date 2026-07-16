from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.intelligence.models import IntelligenceEvent
from app.modules.intelligence.pipeline import IntelligencePipeline
from app.modules.portfolios.models import (
    AlertPreference,
    ExposureClassification,
    Holding,
    HoldingImpact,
    Portfolio,
    PortfolioAlert,
)

logger = logging.getLogger("fios.portfolios.service")


class PortfolioImpactService:
    """
    Portfolio impact assessment service.
    Maps intelligence events to portfolio holdings and classifies exposure.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.pipeline = IntelligencePipeline(db)

    async def assess_event_impact(
        self,
        event_id: uuid.UUID,
        portfolio_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[HoldingImpact]:
        """
        Assess impact of an intelligence event on all holdings in a portfolio.
        Returns created HoldingImpact records.
        """
        event_result = await self.db.execute(
            select(IntelligenceEvent).where(IntelligenceEvent.id == event_id)
        )
        event = event_result.scalar_one_or_none()
        if not event:
            raise ValueError(f"Event {event_id} not found")

        portfolio_result = await self.db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
            )
        )
        portfolio = portfolio_result.scalar_one_or_none()
        if not portfolio:
            raise ValueError(f"Portfolio {portfolio_id} not found")

        holdings_result = await self.db.execute(
            select(Holding).where(
                and_(Holding.portfolio_id == portfolio_id, Holding.tenant_id == tenant_id)
            )
        )
        holdings = holdings_result.scalars().all()
        if not holdings:
            return []

        event_entities = event.entities or []
        event_sectors = set(s.lower() for s in (event.sectors or []))
        event_industries = set(i.lower() for i in (event.industries or []))
        event_geography = (event.geography or "").lower()
        event_companies = set()
        event_tickers = set()
        for entity in event_entities:
            label = entity.get("label", "").lower()
            text = entity.get("text", "")
            resolution = entity.get("resolution") or {}
            if label in ("company", "organization"):
                event_companies.add(text.lower())
                company_name = resolution.get("company_name", "")
                if company_name:
                    event_companies.add(company_name.lower())
            elif label == "ticker":
                event_tickers.add(text.upper())

        direct_impacts = event.direct_impacts or []
        indirect_impacts = event.indirect_impacts or []
        possible_beneficiaries = event.possible_beneficiaries or []
        possible_negative_exposures = event.possible_negative_exposures or []

        impact_entity_names = set()
        for imp in direct_impacts + indirect_impacts + possible_beneficiaries + possible_negative_exposures:
            name = (imp.get("entity", "") or "").lower()
            if name:
                impact_entity_names.add(name)

        event_affected_names = event_companies | impact_entity_names

        created_impacts = []
        for holding in holdings:
            existing = await self.db.execute(
                select(HoldingImpact).where(
                    and_(
                        HoldingImpact.event_id == event_id,
                        HoldingImpact.holding_id == holding.id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            match_type, classification, impact_score, confidence, reasoning, citations = (
                self._classify_holding_impact(
                    holding=holding,
                    event_entities=event_entities,
                    event_sectors=event_sectors,
                    event_industries=event_industries,
                    event_geography=event_geography,
                    event_affected_names=event_affected_names,
                    event_companies=event_companies,
                    event_tickers=event_tickers,
                    direct_impacts=direct_impacts,
                    indirect_impacts=indirect_impacts,
                    possible_beneficiaries=possible_beneficiaries,
                    possible_negative_exposures=possible_negative_exposures,
                    event=event,
                )
            )

            impact = HoldingImpact(
                event_id=event.id,
                holding_id=holding.id,
                portfolio_id=portfolio.id,
                tenant_id=tenant_id,
                classification=classification,
                impact_score=impact_score,
                confidence=confidence,
                uncertainty=1.0 - confidence,
                reasoning=reasoning,
                citations=citations,
                verified_relationships=citations if match_type == "direct" else [],
                inferred_relationships=citations if match_type == "indirect" else [],
                impact_horizon=event.impact_horizon.value if hasattr(event.impact_horizon, 'value') else str(event.impact_horizon),
            )
            self.db.add(impact)
            created_impacts.append(impact)

            await self._create_alert(portfolio, holding, event, classification, impact_score, tenant_id)

        await self.db.flush()
        return created_impacts

    def _classify_holding_impact(
        self,
        holding: Holding,
        event_entities: list[dict[str, Any]],
        event_sectors: set[str],
        event_industries: set[str],
        event_geography: str,
        event_affected_names: set[str],
        event_companies: set[str],
        event_tickers: set[str],
        direct_impacts: list[dict[str, Any]],
        indirect_impacts: list[dict[str, Any]],
        possible_beneficiaries: list[dict[str, Any]],
        possible_negative_exposures: list[dict[str, Any]],
        event: IntelligenceEvent,
    ) -> tuple[str, ExposureClassification, float, float, str, list[str]]:
        holding_name_lower = holding.company_name.lower()
        holding_ticker = holding.ticker.upper()
        holding_sector = (holding.sector or "").lower()
        holding_industry = (holding.industry or "").lower()
        holding_country = (holding.country or "").lower()

        citations = []

        # 1. Direct ticker/company match — DIRECTLY_AFFECTED
        if holding_ticker in event_tickers or holding_name_lower in event_companies:
            impact_score, confidence = self._get_impact_from_impacts(
                holding_name_lower, holding_ticker, direct_impacts, indirect_impacts
            )
            citations.append(f"Direct entity match: {holding.company_name} ({holding.ticker}) referenced in event")
            return ("direct", ExposureClassification.DIRECTLY_AFFECTED, impact_score, max(confidence, 0.7), f"Holding {holding.ticker} ({holding.company_name}) is directly referenced in the intelligence event. Direct impact assessment applied.", citations)

        # 2. Check possible_negative_exposures — POSSIBLE_NEGATIVE_EXPOSURE
        for ne in possible_negative_exposures:
            ne_name = (ne.get("entity", "") or "").lower()
            if ne_name in (holding_name_lower, holding_ticker.lower()):
                confidence = ne.get("confidence", 0.5)
                citations.append(f"Listed as possible negative exposure: {ne.get('entity')}")
                return ("direct", ExposureClassification.POSSIBLE_NEGATIVE_EXPOSURE, -abs(ne.get("confidence", 0.5)), confidence, "Holding appears in event's possible negative exposures.", citations)

        # 3. Check possible_beneficiaries — POSSIBLE_BENEFICIARY
        for pb in possible_beneficiaries:
            pb_name = (pb.get("entity", "") or "").lower()
            if pb_name in (holding_name_lower, holding_ticker.lower()):
                confidence = pb.get("confidence", 0.5)
                citations.append(f"Listed as possible beneficiary: {pb.get('entity')}")
                return ("direct", ExposureClassification.POSSIBLE_BENEFICIARY, abs(pb.get("confidence", 0.5)), confidence, "Holding appears in event's possible beneficiaries.", citations)

        # 4. Sector/industry match — INDIRECTLY_AFFECTED or POSSIBLE_BENEFICIARY
        if holding_sector in event_sectors or holding_industry in event_industries:
            impact_direction = event.impact_direction.value if hasattr(event.impact_direction, 'value') else str(event.impact_direction)
            if impact_direction in ("positive", "mixed"):
                citations.append(f"Sector/industry overlap: {holding_sector or holding_industry}")
                return ("indirect", ExposureClassification.POSSIBLE_BENEFICIARY, 0.3, 0.5, f"Holding sector/industry ({holding_sector}/{holding_industry}) aligns with event sectors. Potential beneficiary.", citations)
            elif impact_direction == "negative":
                citations.append(f"Sector/industry overlap with negative event: {holding_sector or holding_industry}")
                return ("indirect", ExposureClassification.INDIRECTLY_AFFECTED, -0.3, 0.5, f"Holding sector/industry ({holding_sector}/{holding_industry}) overlaps with event sectors carrying negative impact.", citations)
            else:
                citations.append(f"Sector/industry overlap: {holding_sector or holding_industry} (uncertain direction)")
                return ("indirect", ExposureClassification.INDIRECTLY_AFFECTED, 0.0, 0.4, f"Holding sector/industry ({holding_sector}/{holding_industry}) overlaps with event sectors but impact direction is uncertain.", citations)

        # 5. Country match (for macro events) — INDIRECTLY_AFFECTED
        if event_geography and holding_country and event_geography == holding_country:
            citations.append(f"Country overlap: {holding_country}")
            return ("indirect", ExposureClassification.INDIRECTLY_AFFECTED, 0.1, 0.3, f"Holding country ({holding_country}) matches event geography ({event_geography}). Indirect exposure possible.", citations)

        # 6. Company name mentioned in event text — UNCERTAIN
        if holding_name_lower in event_affected_names or holding_ticker.lower() in event_affected_names:
            citations.append(f"Holding mentioned in event context: {holding.company_name}")
            return ("indirect", ExposureClassification.UNCERTAIN, 0.0, 0.3, f"Holding {holding.company_name} is mentioned in event context but relationship is unclear.", citations)

        # 7. No match — NO_MATERIAL_EVIDENCE
        return ("none", ExposureClassification.NO_MATERIAL_EVIDENCE, 0.0, 0.0, f"No material connection found between event and holding {holding.ticker} ({holding.company_name}).", citations)

    def _get_impact_from_impacts(
        self,
        company_name: str,
        ticker: str,
        direct_impacts: list[dict[str, Any]],
        indirect_impacts: list[dict[str, Any]],
    ) -> tuple[float, float]:
        for imp in direct_impacts + indirect_impacts:
            imp_entity = (imp.get("entity", "") or "").lower()
            if company_name in imp_entity or imp_entity in company_name or ticker.lower() in imp_entity:
                direction = imp.get("direction", "neutral")
                conf = imp.get("confidence", 0.5)
                if direction == "positive":
                    return (abs(conf), conf)
                elif direction == "negative":
                    return (-abs(conf), conf)
                else:
                    return (0.0, conf)
        return (0.0, 0.5)

    async def _create_alert(
        self,
        portfolio: Portfolio,
        holding: Holding,
        event: IntelligenceEvent,
        classification: ExposureClassification,
        impact_score: float,
        tenant_id: uuid.UUID,
    ):
        pref_result = await self.db.execute(
            select(AlertPreference).where(AlertPreference.portfolio_id == portfolio.id)
        )
        pref = pref_result.scalar_one_or_none()

        severity = self._severity_from_impact(impact_score, classification)

        if pref:
            if severity == "critical" and not pref.enable_material_event:
                return
            if classification in (ExposureClassification.DIRECTLY_AFFECTED, ExposureClassification.POSSIBLE_NEGATIVE_EXPOSURE):
                if not pref.enable_new_direct_exposure:
                    return
            elif classification == ExposureClassification.INDIRECTLY_AFFECTED:
                if not pref.enable_new_indirect_exposure:
                    return
            min_sev = {"info": 0, "warning": 1, "critical": 2}.get(pref.min_severity, 0)
            sev_score = {"info": 0, "warning": 1, "critical": 2}.get(severity, 0)
            if sev_score < min_sev:
                return

        alert_type = "material_event" if severity == "critical" else (
            "new_direct_exposure" if classification in (ExposureClassification.DIRECTLY_AFFECTED, ExposureClassification.POSSIBLE_NEGATIVE_EXPOSURE) else
            "new_indirect_exposure" if classification in (ExposureClassification.INDIRECTLY_AFFECTED, ExposureClassification.POSSIBLE_BENEFICIARY) else
            "changed_assessment"
        )

        title = f"{classification.value.replace('_', ' ').title()}: {holding.ticker}"
        message = f"Event '{event.factual_summary[:100]}...' classified as {classification.value} for {holding.ticker} ({holding.company_name}). Impact score: {impact_score:.2f}."

        alert = PortfolioAlert(
            portfolio_id=portfolio.id,
            tenant_id=tenant_id,
            alert_type=alert_type,
            event_id=event.id,
            holding_id=holding.id,
            title=title,
            message=message,
            severity=severity,
        )
        self.db.add(alert)

    def _severity_from_impact(self, impact_score: float, classification: ExposureClassification) -> str:
        if classification in (ExposureClassification.DIRECTLY_AFFECTED, ExposureClassification.POSSIBLE_NEGATIVE_EXPOSURE):
            return "critical" if abs(impact_score) > 0.5 else "warning"
        elif classification == ExposureClassification.INDIRECTLY_AFFECTED:
            return "warning"
        elif classification == ExposureClassification.POSSIBLE_BENEFICIARY:
            return "info"
        return "info"

    async def assess_new_events_for_portfolio(
        self,
        portfolio_id: uuid.UUID,
        tenant_id: uuid.UUID,
        days_back: int = 7,
    ) -> list[HoldingImpact]:
        portfolio_result = await self.db.execute(
            select(Portfolio).where(
                and_(Portfolio.id == portfolio_id, Portfolio.tenant_id == tenant_id)
            )
        )
        if not portfolio_result.scalar_one_or_none():
            raise ValueError(f"Portfolio {portfolio_id} not found")

        cutoff = datetime.now(timezone.utc)
        events_result = await self.db.execute(
            select(IntelligenceEvent).where(
                IntelligenceEvent.timestamp >= cutoff
            ).order_by(desc(IntelligenceEvent.timestamp)).limit(100)
        )
        events = events_result.scalars().all()

        all_impacts = []
        for event in events:
            impacts = await self.assess_event_impact(event.id, portfolio_id, tenant_id)
            all_impacts.extend(impacts)
        return all_impacts

    async def get_portfolio_exposure_summary(
        self,
        portfolio_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> dict[str, Any]:
        counts = await self.db.execute(
            select(
                HoldingImpact.classification,
                func.count(HoldingImpact.id),
            ).where(
                and_(
                    HoldingImpact.portfolio_id == portfolio_id,
                    HoldingImpact.tenant_id == tenant_id,
                )
            ).group_by(HoldingImpact.classification)
        )
        classification_counts = {row[0]: row[1] for row in counts.all()}

        total = await self.db.execute(
            select(func.count(Holding.id)).where(
                and_(Holding.portfolio_id == portfolio_id, Holding.tenant_id == tenant_id)
            )
        )
        total_holdings = total.scalar() or 0

        return {
            "directly_affected": classification_counts.get(ExposureClassification.DIRECTLY_AFFECTED.value, 0),
            "indirectly_affected": classification_counts.get(ExposureClassification.INDIRECTLY_AFFECTED.value, 0),
            "possible_beneficiaries": classification_counts.get(ExposureClassification.POSSIBLE_BENEFICIARY.value, 0),
            "possible_negative_exposures": classification_counts.get(ExposureClassification.POSSIBLE_NEGATIVE_EXPOSURE.value, 0),
            "uncertain": classification_counts.get(ExposureClassification.UNCERTAIN.value, 0),
            "no_material_evidence": classification_counts.get(ExposureClassification.NO_MATERIAL_EVIDENCE.value, 0),
            "total_holdings": total_holdings,
        }

    async def get_holding_impacts(
        self,
        holding_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ) -> list[HoldingImpact]:
        result = await self.db.execute(
            select(HoldingImpact).where(
                and_(
                    HoldingImpact.holding_id == holding_id,
                    HoldingImpact.tenant_id == tenant_id,
                )
            ).order_by(desc(HoldingImpact.assessed_at))
        )
        return list(result.scalars().all())

    async def get_portfolio_alerts(
        self,
        portfolio_id: uuid.UUID,
        tenant_id: uuid.UUID,
        unread_only: bool = False,
        limit: int = 50,
    ) -> list[PortfolioAlert]:
        query = select(PortfolioAlert).where(
            and_(
                PortfolioAlert.portfolio_id == portfolio_id,
                PortfolioAlert.tenant_id == tenant_id,
            )
        )
        if unread_only:
            query = query.where(PortfolioAlert.is_read == False)
        query = query.order_by(desc(PortfolioAlert.created_at)).limit(limit)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def mark_alert_read(
        self,
        alert_id: uuid.UUID,
        tenant_id: uuid.UUID,
    ):
        result = await self.db.execute(
            select(PortfolioAlert).where(
                and_(
                    PortfolioAlert.id == alert_id,
                    PortfolioAlert.tenant_id == tenant_id,
                )
            )
        )
        alert = result.scalar_one_or_none()
        if not alert:
            raise ValueError(f"Alert {alert_id} not found")
        alert.is_read = True
        await self.db.flush()
