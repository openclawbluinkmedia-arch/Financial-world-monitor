from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.evidence.models import Evidence, Jurisdiction, SourceType
from app.modules.intelligence import (
    CausalGraphEdge,
    IntelligenceEvent,
)
from app.modules.intelligence.classification import EventClassifier, ImpactReasoner
from app.modules.intelligence.entity_extractor import EntityExtractor, SecurityMasterService
from app.modules.intelligence.validation import ConfidenceService, ValidationService

logger = logging.getLogger("fios.intelligence.pipeline")


class IntelligencePipeline:
    """
    Full intelligence pipeline:
    EVENT -> EVIDENCE RETRIEVAL (bge-m3) -> ENTITY EXTRACTION (GLiNER + master table)
    -> ENTITY RESOLUTION -> EVENT CLASSIFICATION (FinBERT + Qwen) -> CONTEXT RETRIEVAL
    -> RERANK (BAAI/bge-reranker-v2-m3) -> IMPACT REASONING (Qwen, evidence-grounded)
    -> VALIDATION -> CONFIDENCE -> CITED OUTPUT.
    """

    def __init__(self, db: AsyncSession):
        self.db = db
        self.security_master = SecurityMasterService(db)
        self.entity_extractor = EntityExtractor(db, self.security_master)
        self.classifier = EventClassifier()
        self.reasoner = ImpactReasoner()
        self.validation_service = ValidationService(db)
        self.confidence_service = ConfidenceService(db)

        self._initialized = False

    async def initialize(self):
        if not self._initialized:
            await self.entity_extractor.initialize()
            self._initialized = True

    async def process(
        self,
        event_text: str,
        title: str = "",
        source_ids: list[str] | None = None,
        event_type: str | None = None,
    ) -> dict[str, Any]:
        """Process a raw event through the full pipeline"""
        await self.initialize()

        # Create a temporary evidence object for the input
        evidence = Evidence(
            evidence_id=f"inp-{uuid.uuid4().hex[:16]}",
            source_id=uuid.uuid4(),
            source_name="api_input",
            title=title or "API Input",
            raw_content=event_text,
            normalized_content=event_text,
            content_hash="",
            near_dup_hash=None,
            publication_ts=datetime.now(timezone.utc),
            ingestion_ts=datetime.now(timezone.utc),
            jurisdiction=Jurisdiction.IN,
            source_type=SourceType.API,
            version=1,
            is_mock=False,
        )

        return await self._process_single_evidence(evidence, event_type)

    async def process_evidence_batch(
        self,
        evidence_items: list[Evidence],
    ) -> list[IntelligenceEvent]:
        """Process a batch of evidence items through the full pipeline"""
        await self.initialize()

        results = []
        for evidence in evidence_items:
            try:
                event = await self._process_single_evidence(evidence)
                if event:
                    results.append(event)
            except Exception as e:
                logger.error(f"Failed to process evidence {evidence.id}: {e}", exc_info=True)

        return results

    async def _process_single_evidence(
        self,
        evidence: Evidence,
        event_type_hint: str | None = None,
    ) -> IntelligenceEvent | None:
        """Process a single evidence item through the full pipeline"""

        # 1. Entity extraction (GLiNER + master table)
        entities = await self.entity_extractor.extract_entities(
            evidence.raw_content,
            evidence_ids=[evidence.evidence_id]
        )

        # 2. Event classification
        event_type, sentiment = await self.classifier.classify_event(evidence.raw_content)

        # 3. Context retrieval (bge-m3 embedding search)
        context_evidence = await self._retrieve_context(evidence, entities)

        # 4. Reranking (BAAI/bge-reranker-v2-m3)
        ranked_evidence = await self._rerank_evidence(evidence, context_evidence, entities)

        # 5. Impact reasoning (Qwen, evidence-grounded)
        impact_analysis = await self.reasoner.reason_impact(
            event_text=evidence.raw_content,
            event_category=event_type,
            evidence_texts=[e.raw_content for e in ranked_evidence],
            entities=entities,
            sectors=[],  # Would be extracted from entities
            security_master_service=self.security_master,
        )

        # 6. Validation (deterministic)
        validation = self.validation_service.validate(impact_analysis, ranked_evidence, entities)

        # 7. Confidence computation
        confidence = await self.confidence_service.compute_confidence(
            uuid.uuid4(),  # temp event_id
            impact_analysis,
            ranked_evidence,
            entities
        )

        # 8. Create intelligence event
        event = IntelligenceEvent(
            event_id=self._generate_event_id(evidence),
            event_type=event_type,
            factual_summary=impact_analysis.get("factual_summary", ""),
            timestamp=evidence.publication_ts or datetime.now(timezone.utc),
            geography=evidence.jurisdiction.value if hasattr(evidence.jurisdiction, 'value') else str(evidence.jurisdiction),
            entities=entities,
            sectors=impact_analysis.get("sectors", []),
            industries=impact_analysis.get("industries", []),
            commodities=impact_analysis.get("commodities", []),
            currencies=impact_analysis.get("currencies", []),
            source_ids=[evidence.evidence_id] + [e.evidence_id for e in ranked_evidence],
            direct_impacts=impact_analysis.get("direct_impacts", []),
            indirect_impacts=impact_analysis.get("indirect_impacts", []),
            possible_beneficiaries=impact_analysis.get("possible_beneficiaries", []),
            possible_negative_exposures=impact_analysis.get("possible_negative_exposures", []),
            impact_direction=impact_analysis.get("impact_direction", "unknown"),
            impact_horizon=impact_analysis.get("impact_horizon", "unknown"),
            causal_chain=impact_analysis.get("causal_chain", []),
            confidence=confidence.confidence,
            uncertainty=confidence.uncertainty,
            human_review_required=validation.abstained or confidence.confidence < 0.4,
            validation_flags=validation.get("flags", []),
            extra_metadata=str({
                "validation": validation,
                "confidence_components": {
                    "source_reliability": confidence.source_reliability,
                    "corroboration_count": confidence.corroboration_count,
                    "evidence_coverage": confidence.evidence_coverage,
                    "entity_resolution_certainty": confidence.entity_resolution_certainty,
                    "retrieval_score": confidence.retrieval_score,
                },
                "sentiment": sentiment,
            }),
        )

        # Persist
        self.db.add(event)
        await self.db.flush()

        # Create validation record
        from app.modules.intelligence.models import ValidationResult
        val_record = ValidationResult(
            event_id=event.id,
            citations_valid=validation.get("citations_valid", True),
            invalid_citations=validation.get("invalid_citations", []),
            missing_citations=validation.get("missing_citations", []),
            numerically_consistent=validation.get("numerically_consistent", True),
            numerical_issues=validation.get("numerical_issues", []),
            has_contradictions=validation.get("has_contradictions", False),
            contradictions=validation.get("contradictions", []),
            has_missing_evidence=validation.get("has_missing_evidence", False),
            missing_evidence_claims=validation.get("missing_evidence_claims", []),
            abstained=validation.get("abstained", False),
            abstention_reason=validation.get("abstention_reason"),
            passed=validation.get("passed", True),
        )
        self.db.add(val_record)

        # Create confidence record
        from app.modules.intelligence.models import ConfidenceScore
        conf_record = ConfidenceScore(
            event_id=event.id,
            source_reliability=confidence.source_reliability,
            corroboration_count=confidence.corroboration_count,
            evidence_coverage=confidence.evidence_coverage,
            entity_resolution_certainty=confidence.entity_resolution_certainty,
            retrieval_score=confidence.retrieval_score,
            weights=confidence.weights,
            confidence=confidence.confidence,
            uncertainty=confidence.uncertainty,
        )
        self.db.add(conf_record)

        # Build causal graph edges
        await self._build_causal_edges(event, impact_analysis, entities, ranked_evidence)

        return event

    def _generate_event_id(self, evidence: Evidence) -> str:
        import hashlib
        content = f"{evidence.evidence_id}:{evidence.title}:{evidence.publication_ts}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    async def _retrieve_context(
        self,
        evidence: Evidence,
        entities: list[dict[str, Any]],
    ) -> list[Evidence]:
        """Retrieve related evidence using bge-m3 embeddings"""
        from sqlalchemy import text

        if not evidence.embedding:
            return []

        query = text("""
            SELECT id, evidence_id, source_name, title, raw_content,
                   publication_ts, jurisdiction, source_type, is_mock,
                   1 - (embedding <=> :query_vec) as similarity
            FROM evidence
            WHERE embedding IS NOT NULL
            ORDER BY embedding <=> :query_vec
            LIMIT 20
        """)
        result = await self.db.execute(query, {"query_vec": evidence.embedding})
        rows = result.mappings().all()

        context = []
        for row in rows:
            if row["evidence_id"] != evidence.evidence_id:
                e = Evidence(
                    id=row["id"],
                    evidence_id=row["evidence_id"],
                    source_name=row["source_name"],
                    title=row["title"],
                    raw_content=row["raw_content"],
                    publication_ts=row["publication_ts"],
                    jurisdiction=row["jurisdiction"],
                    source_type=row["source_type"],
                    is_mock=row["is_mock"],
                )
                context.append(e)

        return context

    async def _rerank_evidence(
        self,
        primary: Evidence,
        context: list[Evidence],
        entities: list[dict[str, Any]],
    ) -> list[Evidence]:
        """Rerank using bge-reranker-v2-m3"""
        from app.ai.router import rerank

        if not context:
            return [primary]

        entity_text = " ".join([e.get("text", "") for e in entities[:10]])
        query = f"{primary.title} {entity_text}"

        docs = [e.raw_content[:1000] for e in context]
        try:
            result = await rerank(query, docs, top_k=10)
            ranked = [context[i] for i in result.indices]
            return [primary] + ranked
        except Exception as e:
            logger.warning(f"Reranking failed: {e}")
            return [primary] + context

    async def _build_causal_edges(
        self,
        event: IntelligenceEvent,
        impact_analysis: dict[str, Any],
        entities: list[dict[str, Any]],
        evidence: list[Evidence],
    ):
        """Build causal graph edges from impact analysis"""
        evidence_ids = [e.evidence_id for e in evidence]

        # Entity to event edges
        for entity in entities:
            if entity.get("resolution"):
                edge = CausalGraphEdge(
                    source_entity_id=uuid.UUID(entity["resolution"]["id"]) if isinstance(entity["resolution"].get("id"), str) else uuid.uuid4(),
                    source_entity_type="company",
                    target_entity_id=event.id,
                    target_entity_type="event",
                    edge_type="INFERRED",
                    relationship="impacts",
                    weight=0.7,
                    evidence_ids=evidence_ids,
                    confidence=0.6,
                )
                self.db.add(edge)

        # Causal chain edges
        for step in impact_analysis.get("causal_chain", []):
            edge = CausalGraphEdge(
                source_entity_id=event.id,
                source_entity_type="event",
                target_entity_id=event.id,  # Simplified - in reality would link to specific entities
                target_entity_type="event",
                edge_type=step.get("type", "UNCERTAIN"),
                relationship="causes",
                weight=0.8 if step.get("confidence") == "high" else 0.5,
                evidence_ids=step.get("evidence_refs", []),
                confidence=0.8 if step.get("confidence") == "high" else 0.4,
            )
            self.db.add(edge)

        await self.db.flush()
