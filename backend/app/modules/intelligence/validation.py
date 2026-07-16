from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evidence.models import Evidence
from app.modules.intelligence.models import ConfidenceScore, ValidationResult

logger = logging.getLogger("fios.intelligence.validation")


class ValidationService:
    """
    Deterministic validation layer for intelligence events.
    Never uses LLM to validate LLM output.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def validate_event(self, event_id: uuid.UUID, event: dict[str, Any]) -> ValidationResult:
        """
        Run all deterministic validation checks.
        """
        result = ValidationResult(event_id=event_id)

        # 1. Citation validation
        await self._validate_citations(event, result)

        # 2. Numerical consistency
        self._validate_numerical_consistency(event, result)

        # 3. Contradiction detection
        self._detect_contradictions(event, result)

        # 4. Missing evidence detection
        self._detect_missing_evidence(event, result)

        # 5. Abstention logic
        self._check_abstention(event, result)

        # Overall
        result.passed = (
            result.citations_valid
            and result.numerically_consistent
            and not result.has_contradictions
            and not result.has_missing_evidence
            and not result.abstained
        )
        result.score = self._compute_validation_score(result)

        self.db.add(result)
        await self.db.flush()

        return result

    async def _validate_citations(self, event: dict[str, Any], result: ValidationResult):
        """
        Every factual claim must map to a real stored evidence ID.
        """
        evidence_refs = self._extract_evidence_refs(event)

        invalid = []
        missing = []

        for ref in evidence_refs:
            evidence = await self.db.get(Evidence, ref)
            if not evidence:
                invalid.append(str(ref))
            elif evidence.is_mock:
                missing.append(f"Evidence {ref} is mock data")

        result.citations_valid = len(invalid) == 0
        result.invalid_citations = invalid
        result.missing_citations = missing

    def _extract_evidence_refs(self, event: dict[str, Any]) -> list[uuid.UUID]:
        """Extract all UUID evidence IDs referenced in event"""
        refs = []

        for sid in event.get("source_ids", []):
            try:
                refs.append(uuid.UUID(sid))
            except (ValueError, TypeError):
                pass

        for impact_list in ["direct_impacts", "indirect_impacts", "possible_beneficiaries", "possible_negative_exposures"]:
            for impact in event.get(impact_list, []):
                for ref in impact.get("evidence_refs", []):
                    try:
                        refs.append(uuid.UUID(ref))
                    except (ValueError, TypeError):
                        pass

        for step in event.get("causal_chain", []):
            for ref in step.get("evidence_refs", []):
                try:
                    refs.append(uuid.UUID(ref))
                except (ValueError, TypeError):
                    pass

        return refs

    def _validate_numerical_consistency(self, event: dict[str, Any], result: ValidationResult):
        """Check numerical claims for internal consistency"""
        issues = []

        conf = event.get("confidence", 0)
        if not 0 <= conf <= 1:
            issues.append(f"Confidence {conf} out of bounds [0,1]")

        unc = event.get("uncertainty", 1)
        if not 0 <= unc <= 1:
            issues.append(f"Uncertainty {unc} out of bounds [0,1]")

        if conf + unc > 1.2:
            issues.append(f"Confidence + uncertainty > 1.2: {conf} + {unc}")

        # Impact direction vs impacts consistency
        direction = event.get("impact_direction", "unknown")
        direct = event.get("direct_impacts", [])
        indirect = event.get("indirect_impacts", [])

        pos_count = sum(1 for i in direct + indirect if i.get("direction") == "positive")
        neg_count = sum(1 for i in direct + indirect if i.get("direction") == "negative")

        if direction == "positive" and neg_count > pos_count:
            issues.append(f"Direction 'positive' but {neg_count} negative vs {pos_count} positive impacts")
        elif direction == "negative" and pos_count > neg_count:
            issues.append(f"Direction 'negative' but {pos_count} positive vs {neg_count} negative impacts")

        result.numerically_consistent = len(issues) == 0
        result.numerical_issues = issues

    def _detect_contradictions(self, event: dict[str, Any], result: ValidationResult):
        """Detect contradictory claims within the event"""
        contradictions = []

        # Same entity with opposite impacts
        entity_impacts: dict[str, list[str]] = {}

        for impact in event.get("direct_impacts", []) + event.get("indirect_impacts", []):
            entity = impact.get("entity", "")
            direction = impact.get("direction", "")
            if entity and direction:
                entity_impacts.setdefault(entity, []).append(direction)

        for entity, directions in entity_impacts.items():
            if "positive" in directions and "negative" in directions:
                contradictions.append({
                    "type": "opposite_directions",
                    "entity": entity,
                    "directions": directions,
                })

        # Beneficiary vs negative exposure overlap
        beneficiaries = {b.get("entity", "") for b in event.get("possible_beneficiaries", [])}
        negative = {n.get("entity", "") for n in event.get("possible_negative_exposures", [])}
        overlap = beneficiaries & negative

        for entity in overlap:
            contradictions.append({
                "type": "beneficiary_and_exposure",
                "entity": entity,
            })

        result.has_contradictions = len(contradictions) > 0
        result.contradictions = contradictions

    def _detect_missing_evidence(self, event: dict[str, Any], result: ValidationResult):
        """Detect claims made without supporting evidence"""
        missing = []

        for impact_list in ["direct_impacts", "indirect_impacts"]:
            for i, impact in enumerate(event.get(impact_list, [])):
                if not impact.get("evidence_refs"):
                    missing.append(f"{impact_list}[{i}]: '{impact.get('entity')}' has no evidence")

        for i, step in enumerate(event.get("causal_chain", [])):
            if not step.get("evidence_refs"):
                missing.append(f"causal_chain[{i}]: '{step.get('cause')} -> {step.get('effect')}' has no evidence")

        for ben_list in ["possible_beneficiaries", "possible_negative_exposures"]:
            for i, item in enumerate(event.get(ben_list, [])):
                if not item.get("evidence_refs"):
                    missing.append(f"{ben_list}[{i}]: '{item.get('entity')}' has no evidence")

        result.has_missing_evidence = len(missing) > 0
        result.missing_evidence_claims = missing

    def _check_abstention(self, event: dict[str, Any], result: ValidationResult):
        """Determine if we should abstain due to insufficient evidence"""
        reasons = []

        # No evidence at all
        if not event.get("source_ids"):
            reasons.append("No source evidence provided")

        # No direct impacts with evidence
        has_evidence = any(
            impact.get("evidence_refs")
            for impact in event.get("direct_impacts", []) + event.get("indirect_impacts", [])
        )
        if not has_evidence:
            reasons.append("No impacts supported by evidence")

        # Low confidence
        if event.get("confidence", 0) < 0.3:
            reasons.append(f"Confidence too low: {event.get('confidence', 0)}")

        # Many validation failures
        if not result.citations_valid or result.has_contradictions or result.has_missing_evidence:
            reasons.append("Validation failures detected")

        result.abstained = len(reasons) > 0
        result.abstention_reason = "; ".join(reasons) if reasons else None

    def _compute_validation_score(self, result: ValidationResult) -> float:
        """Compute overall validation score 0-1"""
        score = 1.0
        if not result.citations_valid:
            score -= 0.4
        if not result.numerically_consistent:
            score -= 0.2
        if result.has_contradictions:
            score -= 0.2
        if result.has_missing_evidence:
            score -= 0.2
        if result.abstained:
            score -= 0.3
        return max(0.0, score)


class ConfidenceService:
    """
    Confidence computed from deterministic factors, never invented by LLM.
    Factors: source reliability, corroboration count, evidence coverage, entity resolution certainty, retrieval score.
    """

    WEIGHTS = {
        "source_reliability": 0.25,
        "corroboration_count": 0.20,
        "evidence_coverage": 0.20,
        "entity_resolution_certainty": 0.20,
        "retrieval_score": 0.15,
    }

    def __init__(self, db: AsyncSession):
        self.db = db

    async def compute_confidence(
        self,
        event_id: uuid.UUID,
        event: dict[str, Any],
        evidence: list[Evidence],
        entities: list[dict[str, Any]],
    ) -> ConfidenceScore:
        """Compute confidence from deterministic factors"""

        # Source reliability (based on source type and history)
        source_reliability = self._compute_source_reliability(evidence)

        # Corroboration count (independent sources)
        corroboration_count = len(set(e.source_name for e in evidence))

        # Evidence coverage (what fraction of claims have evidence)
        evidence_coverage = self._compute_evidence_coverage(event)

        # Entity resolution certainty
        entity_resolution_certainty = self._compute_entity_resolution_certainty(entities)

        # Retrieval score (average similarity of retrieved evidence)
        retrieval_score = self._compute_retrieval_score(evidence)

        # Apply weights
        weights = self.WEIGHTS
        confidence = (
            source_reliability * weights["source_reliability"] +
            min(corroboration_count / 5.0, 1.0) * weights["corroboration_count"] +
            evidence_coverage * weights["evidence_coverage"] +
            entity_resolution_certainty * weights["entity_resolution_certainty"] +
            retrieval_score * weights["retrieval_score"]
        )

        uncertainty = 1.0 - confidence

        score = ConfidenceScore(
            event_id=event_id,
            source_reliability=source_reliability,
            corroboration_count=corroboration_count,
            evidence_coverage=evidence_coverage,
            entity_resolution_certainty=entity_resolution_certainty,
            retrieval_score=retrieval_score,
            weights=weights,
            confidence=confidence,
            uncertainty=uncertainty,
        )

        self.db.add(score)
        await self.db.flush()

        return score

    def _compute_source_reliability(self, evidence: list[Evidence]) -> float:
        """Reliability based on source type and track record"""
        if not evidence:
            return 0.0

        type_scores = {
            "rss": 0.8,
            "api": 0.85,
            "world_monitor": 0.9,
            "gdelt": 0.7,
            "scraper": 0.6,
            "document": 0.75,
        }

        total = 0.0
        for e in evidence:
            stype = e.source_type.value if hasattr(e.source_type, 'value') else str(e.source_type)
            total += type_scores.get(stype, 0.5)

        return min(total / len(evidence), 1.0)

    def _compute_evidence_coverage(self, event: dict[str, Any]) -> float:
        """Fraction of claims that have evidence"""
        total_claims = 0
        supported_claims = 0

        for impact_list in ["direct_impacts", "indirect_impacts", "possible_beneficiaries", "possible_negative_exposures"]:
            for impact in event.get(impact_list, []):
                total_claims += 1
                if impact.get("evidence_refs"):
                    supported_claims += 1

        for step in event.get("causal_chain", []):
            total_claims += 1
            if step.get("evidence_refs"):
                supported_claims += 1

        if total_claims == 0:
            return 0.0
        return supported_claims / total_claims

    def _compute_entity_resolution_certainty(self, entities: list[dict[str, Any]]) -> float:
        """Certainty of entity resolution"""
        if not entities:
            return 0.0

        resolved = sum(1 for e in entities if e.get("resolved", False))
        return resolved / len(entities)

    def _compute_retrieval_score(self, evidence: list[Evidence]) -> float:
        """Average retrieval similarity score"""
        if not evidence:
            return 0.0

        # Use embedding similarity if available, else default
        scores = [e.extra_metadata for e in evidence if e.extra_metadata]
        if scores:
            return sum(scores) / len(scores)
        return 0.5  # Default moderate score
