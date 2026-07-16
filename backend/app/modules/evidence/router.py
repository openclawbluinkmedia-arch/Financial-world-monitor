from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, func, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.evidence.models import Evidence, EvidenceDedupLog, Jurisdiction, SourceType
from app.modules.ingestion.models import ConnectorHealth

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/")
async def list_evidence(
    limit: int = Query(50, le=200),
    offset: int = Query(0, ge=0),
    source_id: uuid.UUID | None = None,
    source_type: SourceType | None = None,
    jurisdiction: Jurisdiction | None = None,
    is_mock: bool | None = None,
    duplicate_status: str | None = Query(None, description="unique|exact_dup|near_dup|all"),
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    search: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    query = select(Evidence)

    if source_id:
        query = query.where(Evidence.source_id == source_id)
    if source_type:
        query = query.where(Evidence.source_type == source_type)
    if jurisdiction:
        query = query.where(Evidence.jurisdiction == jurisdiction)
    if is_mock is not None:
        query = query.where(Evidence.is_mock == is_mock)
    if date_from:
        query = query.where(Evidence.publication_ts >= date_from)
    if date_to:
        query = query.where(Evidence.publication_ts <= date_to)
    if search:
        query = query.where(
            or_(
                Evidence.title.ilike(f"%{search}%"),
                Evidence.raw_content.ilike(f"%{search}%"),
                Evidence.normalized_content.ilike(f"%{search}%"),
            )
        )

    if duplicate_status == "unique":
        subq = select(EvidenceDedupLog.evidence_id)
        query = query.where(~Evidence.id.in_(subq))
    elif duplicate_status == "exact":
        subq = select(EvidenceDedupLog.evidence_id).where(EvidenceDedupLog.dedup_type == "exact")
        query = query.where(Evidence.id.in_(subq))
    elif duplicate_status == "near":
        subq = select(EvidenceDedupLog.evidence_id).where(EvidenceDedupLog.dedup_type == "near")
        query = query.where(Evidence.id.in_(subq))

    total_result = await db.execute(select(func.count()).select_from(query.subquery()))
    total = total_result.scalar()

    query = query.order_by(desc(Evidence.ingestion_ts)).limit(limit).offset(offset)
    result = await db.execute(query)
    items = result.scalars().all()

    return {
        "items": [serialize_evidence(e) for e in items],
        "total": total,
        "limit": limit,
        "offset": offset,
    }


def serialize_evidence(e: Evidence) -> dict[str, Any]:
    dup_status = "unique"
    return {
        "id": str(e.id),
        "evidence_id": e.evidence_id,
        "source_id": str(e.source_id),
        "source_name": e.source_name,
        "original_url": e.original_url,
        "publisher": e.publisher,
        "title": e.title,
        "raw_content": e.raw_content[:500] + "..." if len(e.raw_content) > 500 else e.raw_content,
        "normalized_content": e.normalized_content[:500] + "..." if e.normalized_content and len(e.normalized_content) > 500 else e.normalized_content,
        "content_hash": e.content_hash,
        "near_dup_hash": e.near_dup_hash,
        "publication_ts": e.publication_ts.isoformat() if e.publication_ts else None,
        "ingestion_ts": e.ingestion_ts.isoformat() if e.ingestion_ts else None,
        "jurisdiction": e.jurisdiction.value if hasattr(e.jurisdiction, 'value') else str(e.jurisdiction),
        "source_type": e.source_type.value if hasattr(e.source_type, 'value') else str(e.source_type),
        "version": e.version,
        "is_mock": e.is_mock,
        "has_embedding": e.embedding is not None,
        "duplicate_status": dup_status,
    }


@router.get("/stats/sources")
async def source_stats(db: AsyncSession = Depends(get_db)):
    stmt = (
        select(
            Evidence.source_id,
            Evidence.source_name,
            Evidence.source_type,
            func.count(Evidence.id).label("total_items"),
            func.sum(func.cast(Evidence.is_mock, int)).label("mock_items"),
            func.max(Evidence.ingestion_ts).label("latest_ingestion"),
        )
        .group_by(Evidence.source_id, Evidence.source_name, Evidence.source_type)
        .order_by(desc("total_items"))
    )
    result = await db.execute(stmt)

    stats = []
    for row in result:
        health = await db.execute(
            text("SELECT status FROM connector_health WHERE connector_name = :name"),
            {"name": row.source_name},
        )
        health_status = health.scalar() or "unknown"

        stats.append(
            {
                "source_id": str(row.source_id),
                "source_name": row.source_name,
                "source_type": str(row.source_type.value) if hasattr(row.source_type, 'value') else str(row.source_type),
                "total_items": row.total_items,
                "mock_items": row.mock_items or 0,
                "latest_ingestion": row.latest_ingestion.isoformat() if row.latest_ingestion else None,
                "health_status": health_status,
            }
        )
    return stats


@router.get("/health/connectors")
async def connector_health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ConnectorHealth).order_by(ConnectorHealth.connector_name))
    connectors = result.scalars().all()
    return [
        {
            "connector": c.connector_name,
            "status": c.status.value if hasattr(c.status, 'value') else str(c.status),
            "last_run_at": c.last_run_at.isoformat() if c.last_run_at else None,
            "consecutive_failures": c.consecutive_failures,
            "last_error": c.last_error,
        }
        for c in connectors
    ]


@router.get("/stats")
async def evidence_stats(db: AsyncSession = Depends(get_db)):
    total = await db.execute(select(func.count(Evidence.id)))
    by_source = await db.execute(
        select(Evidence.source_name, func.count(Evidence.id)).group_by(Evidence.source_name)
    )
    by_type = await db.execute(
        select(Evidence.source_type, func.count(Evidence.id)).group_by(Evidence.source_type)
    )
    by_jurisdiction = await db.execute(
        select(Evidence.jurisdiction, func.count(Evidence.id)).group_by(Evidence.jurisdiction)
    )
    mock_count = await db.execute(select(func.count(Evidence.id)).where(Evidence.is_mock == True))
    with_embedding = await db.execute(select(func.count(Evidence.id)).where(Evidence.embedding != None))

    return {
        "total": total.scalar(),
        "mock_count": mock_count.scalar(),
        "with_embedding": with_embedding.scalar(),
        "by_source": {str(k): v for k, v in by_source.all()},
        "by_type": {str(k.value): v for k, v in by_type.all()},
        "by_jurisdiction": {str(k.value): v for k, v in by_jurisdiction.all()},
    }


@router.get("/{evidence_id}")
async def get_evidence(evidence_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Evidence).where(Evidence.id == evidence_id))
    evidence = result.scalar_one_or_none()
    if not evidence:
        return {"error": "Not found"}, 404

    dedup_logs = await db.execute(
        select(EvidenceDedupLog).where(EvidenceDedupLog.evidence_id == evidence_id)
    )
    dedups = dedup_logs.scalars().all()

    return {
        "id": str(evidence.id),
        "evidence_id": evidence.evidence_id,
        "source_id": str(evidence.source_id),
        "source_name": evidence.source_name,
        "original_url": evidence.original_url,
        "publisher": evidence.publisher,
        "title": evidence.title,
        "raw_content": evidence.raw_content,
        "normalized_content": evidence.normalized_content,
        "content_hash": evidence.content_hash,
        "near_dup_hash": evidence.near_dup_hash,
        "publication_ts": evidence.publication_ts.isoformat() if evidence.publication_ts else None,
        "ingestion_ts": evidence.ingestion_ts.isoformat() if evidence.ingestion_ts else None,
        "jurisdiction": evidence.jurisdiction.value if hasattr(evidence.jurisdiction, 'value') else str(evidence.jurisdiction),
        "source_type": evidence.source_type.value if hasattr(evidence.source_type, 'value') else str(evidence.source_type),
        "version": evidence.version,
        "is_mock": evidence.is_mock,
        "has_embedding": evidence.embedding is not None,
        "extra_metadata": evidence.extra_metadata,
        "deduplications": [
            {
                "duplicate_of_id": str(d.duplicate_of_id),
                "dedup_type": d.dedup_type,
                "similarity_score": d.similarity_score,
            }
            for d in dedups
        ],
    }


@router.get("/search/similar")
async def search_similar(
    text: str = Query(..., min_length=10),
    limit: int = Query(10, le=50),
    threshold: float = Query(0.7, ge=0.0, le=1.0),
    db: AsyncSession = Depends(get_db),
):
    from app.ai.embeddings import embed_query

    query_vector = await embed_query(text)
    if not query_vector:
        return {"results": [], "error": "Embedding generation failed"}

    query = text("""
        SELECT id, evidence_id, source_name, title, raw_content,
               publication_ts, jurisdiction, source_type, is_mock,
               1 - (embedding <=> :query_vec) as similarity
        FROM evidence
        WHERE embedding IS NOT NULL
        ORDER BY embedding <=> :query_vec
        LIMIT :limit
    """)
    result = await db.execute(query, {"query_vec": query_vector, "limit": limit})
    rows = result.mappings().all()

    results = []
    for row in rows:
        if row["similarity"] >= threshold:
            results.append({
                "id": str(row["id"]),
                "evidence_id": row["evidence_id"],
                "source_name": row["source_name"],
                "title": row["title"],
                "preview": row["raw_content"][:200] + "...",
                "publication_ts": row["publication_ts"].isoformat() if row["publication_ts"] else None,
                "jurisdiction": row["jurisdiction"],
                "source_type": row["source_type"],
                "is_mock": row["is_mock"],
                "similarity": round(row["similarity"], 4),
            })

    return {"results": results, "query": text}
