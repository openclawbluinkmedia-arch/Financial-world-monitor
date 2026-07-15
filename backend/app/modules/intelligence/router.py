from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy import select, desc, func, or_, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.intelligence import (
    EventType,
    ImpactDirection,
    ImpactHorizon,
    IntelligenceEvent,
    CausalGraphEdge,
    KnowledgeGraphNode,
    ValidationResult,
    ConfidenceScore,
)
from app.modules.evidence.models import Evidence
from app.modules.intelligence.pipeline import IntelligencePipeline

router = APIRouter(prefix="/intelligence", tags=["intelligence"])


@router.get("/events")
async def list_intelligence_events(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    event_type: EventType | None = None,
    geography: str | None = None,
    impact_direction: ImpactDirection | None = None,
    impact_horizon: ImpactHorizon | None = None,
    min_confidence: float = Query(0.0, ge=0.0, le=1.0),
    human_review_only: bool = False,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(IntelligenceEvent)

    if event_type:
        query = query.where(IntelligenceEvent.event_type == event_type)
    if geography:
        query = query.where(IntelligenceEvent.geography == geography)
    if impact_direction:
        query = query.where(IntelligenceEvent.impact_direction == impact_direction)
    if impact_horizon:
        query = query.where(IntelligenceEvent.impact_horizon == impact_horizon)
    if min_confidence:
        query = query.where(IntelligenceEvent.confidence >= min_confidence)
    if human_review_only:
        query = query.where(IntelligenceEvent.human_review_required == True)
    if date_from:
        query = query.where(IntelligenceEvent.timestamp >= date_from)
    if date_to:
        query = query.where(IntelligenceEvent.timestamp <= date_to)
    if search:
        query = query.where(
            or_(
                IntelligenceEvent.factual_summary.ilike(f"%{search}%"),
                IntelligenceEvent.event_id.ilike(f"%{search}%"),
            )
        )

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(desc(IntelligenceEvent.timestamp)).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [serialize_intelligence_event(e) for e in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def serialize_intelligence_event(e: IntelligenceEvent) -> dict[str, Any]:
    return {
        "id": str(e.id),
        "event_id": e.event_id,
        "event_type": e.event_type.value if hasattr(e.event_type, 'value') else str(e.event_type),
        "factual_summary": e.factual_summary,
        "timestamp": e.timestamp.isoformat() if e.timestamp else None,
        "geography": e.geography,
        "entities": e.entities,
        "sectors": e.sectors,
        "industries": e.industries,
        "commodities": e.commodities,
        "currencies": e.currencies,
        "source_ids": e.source_ids,
        "direct_impacts": e.direct_impacts,
        "indirect_impacts": e.indirect_impacts,
        "possible_beneficiaries": e.possible_beneficiaries,
        "possible_negative_exposures": e.possible_negative_exposures,
        "impact_direction": e.impact_direction.value if hasattr(e.impact_direction, 'value') else str(e.impact_direction),
        "impact_horizon": e.impact_horizon.value if hasattr(e.impact_horizon, 'value') else str(e.impact_horizon),
        "causal_chain": e.causal_chain,
        "confidence": e.confidence,
        "uncertainty": e.uncertainty,
        "human_review_required": e.human_review_required,
        "validation_flags": e.validation_flags,
        "created_at": e.created_at.isoformat() if e.created_at else None,
    }


@router.get("/events/{event_id}")
async def get_intelligence_event(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IntelligenceEvent).where(IntelligenceEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Event not found")

    # Get validation
    val_result = await db.execute(
        select(ValidationResult).where(ValidationResult.event_id == event_id)
    )
    validation = val_result.scalar_one_or_none()

    # Get confidence
    conf_result = await db.execute(
        select(ConfidenceScore).where(ConfidenceScore.event_id == event_id)
    )
    confidence = conf_result.scalar_one_or_none()

    # Get causal edges
    edges_result = await db.execute(
        select(CausalGraphEdge).where(
            or_(
                CausalGraphEdge.source_entity_id == event_id,
                CausalGraphEdge.target_entity_id == event_id,
            )
        )
    )
    edges = edges_result.scalars().all()

    return {
        **serialize_intelligence_event(event),
        "validation": {
            "passed": validation.passed if validation else None,
            "abstained": validation.abstained if validation else None,
            "abstention_reason": validation.abstention_reason if validation else None,
            "citation_valid": validation.citation_valid if validation else None,
            "numerically_consistent": validation.numerically_consistent if validation else None,
            "has_contradictions": validation.has_contradictions if validation else None,
            "has_missing_evidence": validation.has_missing_evidence if validation else None,
            "flags": event.validation_flags,
        } if validation else None,
        "confidence": {
            "score": confidence.confidence if confidence else None,
            "uncertainty": confidence.uncertainty if confidence else None,
            "source_reliability": confidence.source_reliability if confidence else None,
            "corroboration_count": confidence.corroboration_count if confidence else None,
            "evidence_coverage": confidence.evidence_coverage if confidence else None,
            "entity_resolution_certainty": confidence.entity_resolution_certainty if confidence else None,
            "retrieval_score": confidence.retrieval_score if confidence else None,
            "weights": confidence.weights if confidence else None,
        } if confidence else None,
        "causal_edges": [
            {
                "source_entity_id": str(e.source_entity_id),
                "source_entity_type": e.source_entity_type,
                "target_entity_id": str(e.target_entity_id),
                "target_entity_type": e.target_entity_type,
                "edge_type": e.edge_type.value if hasattr(e.edge_type, 'value') else str(e.edge_type),
                "relationship": e.relationship,
                "weight": e.weight,
                "evidence_ids": e.evidence_ids,
                "confidence": e.confidence,
            }
            for e in edges
        ],
    }


@router.get("/events/{event_id}/affected")
async def get_affected_entities(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get affected sectors, companies, beneficiaries, negative exposures"""
    result = await db.execute(
        select(IntelligenceEvent).where(IntelligenceEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Event not found")

    return {
        "event_id": event.event_id,
        "sectors": event.sectors,
        "industries": event.industries,
        "commodities": event.commodities,
        "currencies": event.currencies,
        "direct_impacts": event.direct_impacts,
        "indirect_impacts": event.indirect_impacts,
        "possible_beneficiaries": event.possible_beneficiaries,
        "possible_negative_exposures": event.possible_negative_exposures,
    }


@router.get("/causal-chain/{event_id}")
async def get_causal_chain(
    event_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    """Get causal chain with evidence citations"""
    result = await db.execute(
        select(IntelligenceEvent).where(IntelligenceEvent.id == event_id)
    )
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(404, "Event not found")

    # Get edges
    edges_result = await db.execute(
        select(CausalGraphEdge).where(
            or_(
                CausalGraphEdge.source_entity_id == event_id,
                CausalGraphEdge.target_entity_id == event_id,
            )
        ).order_by(CausalGraphEdge.valid_from)
    )
    edges = edges_result.scalars().all()

    return {
        "event_id": event.event_id,
        "causal_chain": event.causal_chain,
        "graph_edges": [
            {
                "source": {"id": str(e.source_entity_id), "type": e.source_entity_type},
                "target": {"id": str(e.target_entity_id), "type": e.target_entity_type},
                "edge_type": e.edge_type.value if hasattr(e.edge_type, 'value') else str(e.edge_type),
                "relationship": e.relationship,
                "weight": e.weight,
                "evidence_ids": e.evidence_ids,
                "confidence": e.confidence,
            }
            for e in edges
        ],
    }


@router.get("/stats")
async def intelligence_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count(IntelligenceEvent.id)))
    by_type = await db.execute(
        select(IntelligenceEvent.event_type, func.count(IntelligenceEvent.id))
        .group_by(IntelligenceEvent.event_type)
    )
    by_direction = await db.execute(
        select(IntelligenceEvent.impact_direction, func.count(IntelligenceEvent.id))
        .group_by(IntelligenceEvent.impact_direction)
    )
    by_horizon = await db.execute(
        select(IntelligenceEvent.impact_horizon, func.count(IntelligenceEvent.id))
        .group_by(IntelligenceEvent.impact_horizon)
    )
    human_review = await db.execute(
        select(func.count(IntelligenceEvent.id)).where(IntelligenceEvent.human_review_required == True)
    )
    avg_confidence = await db.execute(
        select(func.avg(IntelligenceEvent.confidence))
    )

    return {
        "total_events": total.scalar(),
        "by_type": {str(k.value): v for k, v in by_type.all()},
        "by_direction": {str(k.value): v for k, v in by_direction.all()},
        "by_horizon": {str(k.value): v for k, v in by_horizon.all()},
        "human_review_required": human_review.scalar(),
        "avg_confidence": round(avg_confidence.scalar() or 0, 3),
    }


@router.post("/process-evidence")
async def process_evidence(
    evidence_ids: list[uuid.UUID],
    db: AsyncSession = Depends(get_db),
):
    """Process a batch of evidence through the intelligence pipeline"""
    if not evidence_ids:
        raise HTTPException(400, "No evidence IDs provided")

    # Get evidence
    result = await db.execute(
        select(Evidence).where(Evidence.id.in_(evidence_ids))
    )
    evidence_list = result.scalars().all()

    if not evidence_list:
        raise HTTPException(404, "No evidence found")

    # Run pipeline
    pipeline = IntelligencePipeline(db)
    await pipeline.initialize()
    results = await pipeline.process_evidence_batch(list(evidence_list))

    return {
        "processed": len(results),
        "results": results,
    }


@router.get("/knowledge-graph/nodes")
async def list_kg_nodes(
    node_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(KnowledgeGraphNode)
    if node_type:
        query = query.where(KnowledgeGraphNode.node_type == node_type)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(KnowledgeGraphNode.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    nodes = result.scalars().all()

    return {
        "items": [
            {
                "id": str(n.id),
                "node_type": n.node_type,
                "external_id": n.external_id,
                "properties": n.properties,
            }
            for n in nodes
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


@router.get("/knowledge-graph/edges")
async def list_kg_edges(
    edge_type: str | None = None,
    limit: int = Query(100, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    query = select(CausalGraphEdge)
    if edge_type:
        query = query.where(CausalGraphEdge.edge_type == edge_type)

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(CausalGraphEdge.created_at.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    edges = result.scalars().all()

    return {
        "items": [
            {
                "id": str(e.id),
                "source": {"id": str(e.source_entity_id), "type": e.source_entity_type},
                "target": {"id": str(e.target_entity_id), "type": e.target_entity_type},
                "edge_type": e.edge_type.value if hasattr(e.edge_type, 'value') else str(e.edge_type),
                "relationship": e.relationship,
                "weight": e.weight,
                "evidence_ids": e.evidence_ids,
                "confidence": e.confidence,
            }
            for e in edges
        ],
        "total": total,
        "limit": limit,
        "offset": offset,
    }