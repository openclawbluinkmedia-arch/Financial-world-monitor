from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.copilot.models import CopilotConversation, CopilotMessage
from app.modules.copilot.prompt_manager import build_system_prompt, build_user_prompt
from app.modules.copilot.query_classifier import classify_query
from app.modules.copilot.schemas import CitationSource, CopilotResponse
from app.modules.intelligence.validation import ValidationService

logger = logging.getLogger("fios.copilot.service")


class CopilotPipeline:
    """
    Full copilot pipeline:
    USER QUERY -> AUTH CHECK -> QUERY CLASSIFICATION -> EVIDENCE RETRIEVAL (bge-m3)
    -> PORTFOLIO RETRIEVAL (if authorized) -> RERANK (bge-reranker-v2-m3)
    -> STRUCTURED REASONING (Qwen via model router) -> CITATION VALIDATION
    -> RESPONSE
    """

    def __init__(self, db: AsyncSession, tenant_id: uuid.UUID, user_id: uuid.UUID, role: str):
        self.db = db
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.role = role

    async def run(
        self,
        query: str,
        mode: str = "market_intelligence",
        conversation_id: str | None = None,
    ) -> CopilotResponse:
        conv = await self._get_or_create_conversation(conversation_id, mode)

        # 1. Query classification
        classification = await classify_query(query, mode)

        # 2. Evidence retrieval (bge-m3)
        evidence_items = []
        if classification.needs_evidence_search:
            evidence_items = await self._retrieve_evidence(query)

        # 3. Portfolio retrieval (if authorized, tenant-scoped)
        portfolio_items = []
        if classification.needs_portfolio:
            portfolio_items = await self._retrieve_portfolio()

        # 4. Rerank evidence
        ranked_evidence = await self._rerank_evidence(query, evidence_items)

        # 5. Build prompts with injection defense
        system_prompt = build_system_prompt()
        user_prompt = build_user_prompt(query, ranked_evidence, portfolio_items)

        # 6. Structured reasoning via Qwen
        llm_response = await self._call_llm(system_prompt, user_prompt)

        # 7. Parse and validate
        parsed = self._parse_llm_response(llm_response, ranked_evidence)
        parsed = await self._validate_citations(parsed, ranked_evidence)

        # 8. Build response
        response = self._build_response(parsed, conv.id, ranked_evidence)

        # 9. Persist conversation
        await self._persist_message(conv.id, "user", query)
        await self._persist_message(
            conv.id, "assistant", response.answer,
            sources=response.sources,
            verified_facts=response.verified_facts,
            analysis=response.analysis,
            portfolio_relevance=response.portfolio_relevance,
            uncertainty=response.uncertainty,
            abstained=response.abstained,
            abstention_reason=response.abstention_reason,
        )

        return response

    async def _get_or_create_conversation(
        self, conversation_id: str | None, mode: str
    ) -> CopilotConversation:
        if conversation_id:
            result = await self.db.execute(
                select(CopilotConversation).where(
                    CopilotConversation.id == uuid.UUID(conversation_id),
                    CopilotConversation.tenant_id == self.tenant_id,
                )
            )
            conv = result.scalar_one_or_none()
            if conv:
                conv.updated_at = datetime.now(timezone.utc)
                return conv

        conv = CopilotConversation(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            mode=mode,
        )
        self.db.add(conv)
        await self.db.flush()
        return conv

    async def _retrieve_evidence(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        from app.ai.embeddings import embed_query

        query_vector = await embed_query(query)
        if not query_vector:
            logger.warning("Embedding generation failed")
            return []

        sql = text("""
            SELECT id, evidence_id, source_name, title, raw_content,
                   publication_ts, jurisdiction, source_type, is_mock,
                   original_url,
                   1 - (embedding <=> :query_vec) as similarity
            FROM evidence
            WHERE embedding IS NOT NULL
              AND is_mock = false
            ORDER BY embedding <=> :query_vec
            LIMIT :limit
        """)
        result = await self.db.execute(sql, {"query_vec": query_vector, "limit": limit})
        rows = result.mappings().all()

        return [
            {
                "id": str(row["id"]),
                "evidence_id": row["evidence_id"],
                "source_name": row["source_name"],
                "title": row["title"],
                "raw_content": row["raw_content"],
                "publication_ts": row["publication_ts"].isoformat() if row["publication_ts"] else None,
                "jurisdiction": row["jurisdiction"],
                "source_type": row["source_type"],
                "is_mock": row["is_mock"],
                "original_url": row["original_url"],
                "similarity": round(row["similarity"], 4),
            }
            for row in rows
            if row["similarity"] >= 0.5
        ]

    async def _retrieve_portfolio(self) -> list[dict[str, Any]]:
        from app.modules.portfolios.models import Holding, Portfolio

        result = await self.db.execute(
            select(Portfolio).where(
                Portfolio.tenant_id == self.tenant_id,
                Portfolio.deleted_at.is_(None),
            )
        )
        portfolios = result.scalars().all()
        if not portfolios:
            return []

        portfolio_ids = [p.id for p in portfolios]
        holdings_result = await self.db.execute(
            select(Holding).where(Holding.portfolio_id.in_(portfolio_ids))
        )
        holdings = holdings_result.scalars().all()

        return [
            {
                "ticker": h.ticker,
                "name": h.name,
                "exchange": h.exchange,
                "sector": h.sector,
                "quantity": h.quantity,
                "allocation_pct": h.allocation_pct,
                "market_value": h.market_value,
                "portfolio_id": str(h.portfolio_id),
            }
            for h in holdings
        ]

    async def _rerank_evidence(
        self, query: str, evidence_items: list[dict[str, Any]], top_k: int = 10
    ) -> list[dict[str, Any]]:
        if not evidence_items:
            return []

        from app.ai.router import rerank

        docs = [e["raw_content"][:1000] for e in evidence_items]
        try:
            result = await rerank(query, docs, top_k=top_k)
            return [evidence_items[i] for i in result.indices if i < len(evidence_items)]
        except Exception as e:
            logger.warning(f"Reranking failed: {e}")
            return evidence_items[:top_k]

    async def _call_llm(self, system_prompt: str, user_prompt: str) -> str:
        from app.ai.router import generate

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        result = await generate(
            messages=messages,
            max_tokens=4096,
            temperature=0.3,
        )

        return result.text.strip()

    def _parse_llm_response(
        self, raw: str, evidence_items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Parse LLM JSON response with fallback for malformed output."""
        try:
            # Try to extract JSON from possible markdown code block
            if "```json" in raw:
                raw = raw[raw.index("```json") + 7:]
                raw = raw[: raw.index("```")]
            elif "```" in raw:
                raw = raw[raw.index("```") + 3:]
                raw = raw[: raw.index("```")]

            raw = raw.strip()
            parsed = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            logger.warning("Failed to parse LLM response as JSON")
            return {
                "verified_facts": [],
                "analysis": "",
                "portfolio_relevance": "",
                "uncertainty": "Could not parse structured response",
                "abstained": True,
                "abstention_reason": "Failed to generate structured response",
                "sources": [],
                "answer": raw[:2000] if raw else "I encountered an error processing your request.",
            }

        # Defaults for missing fields
        parsed.setdefault("verified_facts", [])
        parsed.setdefault("analysis", "")
        parsed.setdefault("portfolio_relevance", "")
        parsed.setdefault("uncertainty", "")
        parsed.setdefault("abstained", False)
        parsed.setdefault("abstention_reason", None)
        parsed.setdefault("sources", [])

        # Build answer from components
        answer_parts = []
        if parsed.get("verified_facts"):
            answer_parts.append("**Verified Facts:**\n")
            for fact in parsed["verified_facts"]:
                answer_parts.append(f"• {fact}\n")
        if parsed.get("analysis"):
            answer_parts.append(f"\n**Analysis:**\n{parsed['analysis']}\n")
        if parsed.get("portfolio_relevance"):
            answer_parts.append(f"\n**Portfolio Relevance:**\n{parsed['portfolio_relevance']}\n")
        if parsed.get("uncertainty"):
            answer_parts.append(f"\n**Uncertainty:**\n{parsed['uncertainty']}\n")

        parsed["answer"] = "".join(answer_parts) if answer_parts else "No answer generated."

        return parsed

    async def _validate_citations(
        self, parsed: dict[str, Any], evidence_items: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Validate that all cited evidence_ids exist in our retrieved set."""
        valid_ids = {e["evidence_id"] for e in evidence_items}
        cited_ids = set()

        for source in parsed.get("sources", []):
            if isinstance(source, dict) and source.get("evidence_id"):
                cited_ids.add(source["evidence_id"])

        for fact in parsed.get("verified_facts", []):
            import re
            ids = re.findall(r"\(citation:\s*([^)]+)\)", fact)
            cited_ids.update(ids)

        invalid = cited_ids - valid_ids
        if invalid:
            logger.warning(f"LLM invented citations: {invalid}")
            # Remove invalid citations from sources
            parsed["sources"] = [
                s for s in parsed.get("sources", [])
                if s.get("evidence_id") in valid_ids
            ]

            # Add uncertainty note about hallucinated citations
            uncertainty = parsed.get("uncertainty") or ""
            if uncertainty:
                uncertainty += " "
            uncertainty += f"[Note: Some citations were rejected as they did not match retrieved evidence.]"
            parsed["uncertainty"] = uncertainty

        return parsed

    def _build_response(
        self,
        parsed: dict[str, Any],
        conversation_id: uuid.UUID,
        evidence_items: list[dict[str, Any]],
    ) -> CopilotResponse:
        evidence_map = {e["evidence_id"]: e for e in evidence_items}

        sources = []
        for s in parsed.get("sources", []):
            eid = s.get("evidence_id") if isinstance(s, dict) else s
            if eid in evidence_map:
                ev = evidence_map[eid]
                sources.append(CitationSource(
                    evidence_id=eid,
                    title=ev["title"],
                    snippet=ev["raw_content"][:200],
                    source_name=ev["source_name"],
                    similarity=ev.get("similarity"),
                    url=ev.get("original_url"),
                ))

        return CopilotResponse(
            conversation_id=str(conversation_id),
            message_id=str(uuid.uuid4()),
            answer=parsed.get("answer", ""),
            verified_facts=parsed.get("verified_facts", []),
            analysis=parsed.get("analysis"),
            portfolio_relevance=parsed.get("portfolio_relevance"),
            uncertainty=parsed.get("uncertainty"),
            sources=sources,
            abstained=parsed.get("abstained", False),
            abstention_reason=parsed.get("abstention_reason"),
        )

    async def _persist_message(
        self,
        conversation_id: uuid.UUID,
        role: str,
        content: str,
        sources: list[CitationSource] | None = None,
        verified_facts: list[str] | None = None,
        analysis: str | None = None,
        portfolio_relevance: str | None = None,
        uncertainty: str | None = None,
        abstained: bool = False,
        abstention_reason: str | None = None,
    ):
        msg = CopilotMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
            sources=[s.model_dump() for s in sources] if sources else None,
            verified_facts=verified_facts,
            analysis=analysis,
            portfolio_relevance=portfolio_relevance,
            uncertainty=uncertainty,
            abstained=abstained,
            abstention_reason=abstention_reason,
        )
        self.db.add(msg)

    async def get_history(
        self, conversation_id: str, page: int = 1, page_size: int = 50
    ) -> tuple[list[dict[str, Any]], int]:
        cid = uuid.UUID(conversation_id)
        conv_result = await self.db.execute(
            select(CopilotConversation).where(
                CopilotConversation.id == cid,
                CopilotConversation.tenant_id == self.tenant_id,
            )
        )
        if not conv_result.scalar_one_or_none():
            return [], 0

        total_result = await self.db.execute(
            select(CopilotMessage).where(CopilotMessage.conversation_id == cid)
        )
        total = len(total_result.scalars().all())

        offset = (page - 1) * page_size
        result = await self.db.execute(
            select(CopilotMessage)
            .where(CopilotMessage.conversation_id == cid)
            .order_by(CopilotMessage.created_at.asc())
            .offset(offset)
            .limit(page_size)
        )
        messages = result.scalars().all()

        return [
            {
                "id": str(m.id),
                "role": m.role,
                "content": m.content,
                "sources": (
                    [CitationSource(**s) for s in m.sources]
                    if m.sources
                    else None
                ),
                "verified_facts": m.verified_facts,
                "analysis": m.analysis,
                "portfolio_relevance": m.portfolio_relevance,
                "uncertainty": m.uncertainty,
                "abstained": m.abstained,
                "abstention_reason": m.abstention_reason,
                "created_at": m.created_at,
            }
            for m in messages
        ], total

    async def list_conversations(
        self, page: int = 1, page_size: int = 20
    ) -> tuple[list[dict[str, Any]], int]:
        total_result = await self.db.execute(
            select(CopilotConversation).where(
                CopilotConversation.tenant_id == self.tenant_id
            )
        )
        total = len(total_result.scalars().all())

        result = await self.db.execute(
            select(CopilotConversation)
            .where(CopilotConversation.tenant_id == self.tenant_id)
            .order_by(CopilotConversation.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        convs = result.scalars().all()

        output = []
        for conv in convs:
            msg_count = await self.db.execute(
                select(CopilotMessage).where(
                    CopilotMessage.conversation_id == conv.id
                )
            )
            output.append({
                "id": str(conv.id),
                "title": conv.title,
                "mode": conv.mode,
                "message_count": len(msg_count.scalars().all()),
                "created_at": conv.created_at,
                "updated_at": conv.updated_at,
            })

        return output, total
