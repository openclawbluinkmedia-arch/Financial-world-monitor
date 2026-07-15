from __future__ import annotations

import logging
from typing import Any

from app.ai.router import classify, generate
from app.config import get_settings

logger = logging.getLogger("fios.intelligence.classification")


class EventClassifier:
    """
    Event classification using ProsusAI/finbert for sentiment + Qwen for category.
    """

    EVENT_CATEGORIES = [
        "macro", "earnings", "m_a", "regulatory", "policy",
        "corporate_action", "market_move", "commodity", "currency",
        "geopolitical", "sector", "supply_chain", "esg", "other"
    ]

    SENTIMENT_LABELS = ["positive", "negative", "neutral"]

    def __init__(self):
        self.deployment_mode = get_settings().DEPLOYMENT_MODE.value

    async def classify_event(self, text: str, title: str = "") -> dict[str, Any]:
        """
        Classify an event: category + sentiment.
        Returns dict with category, sentiment, confidence scores.
        """
        # Combine title and text for classification
        full_text = f"{title}\n\n{text}" if title else text

        # Run category classification and sentiment in parallel
        category_result, sentiment_result = await self._classify_parallel(full_text)

        return {
            "category": category_result.get("label", "other"),
            "category_confidence": category_result.get("confidence", 0.0),
            "category_scores": category_result.get("scores", {}),
            "sentiment": sentiment_result.get("label", "neutral"),
            "sentiment_confidence": sentiment_result.get("confidence", 0.0),
            "sentiment_scores": sentiment_result.get("scores", {}),
        }

    async def _classify_parallel(self, text: str) -> tuple[dict[str, Any], dict[str, Any]]:
        """Run category and sentiment classification"""
        # Category classification via Qwen
        category_prompt = f"""Classify this financial news/event into ONE category:
Categories: {", ".join(self.EVENT_CATEGORIES)}

Text: {text[:3000]}

Respond with ONLY the category name."""

        sentiment_prompt = f"""Analyze the sentiment of this financial text:
Labels: {", ".join(self.SENTIMENT_LABELS)}

Text: {text[:3000]}

Respond with ONLY the sentiment label."""

        try:
            category_result = await classify(
                text=category_prompt,
                labels=self.EVENT_CATEGORIES,
                multi_label=False
            )
            sentiment_result = await classify(
                text=sentiment_prompt,
                labels=self.SENTIMENT_LABELS,
                multi_label=False
            )
        except Exception as e:
            logger.error(f"Classification failed: {e}")
            return (
                {"label": "other", "confidence": 0.0, "scores": {}},
                {"label": "neutral", "confidence": 0.0, "scores": {}}
            )

        return (
            {
                "label": category_result.label,
                "confidence": category_result.confidence,
                "scores": category_result.scores,
            },
            {
                "label": sentiment_result.label,
                "confidence": sentiment_result.confidence,
                "scores": sentiment_result.scores,
            }
        )


class ImpactReasoner:
    """
    Impact reasoning using Qwen (evidence-grounded) with causal chain generation.
    """

    def __init__(self):
        self.deployment_mode = get_settings().DEPLOYMENT_MODE.value

    async def reason_impact(
        self,
        event_text: str,
        event_category: str,
        evidence_texts: list[str],
        entities: list[dict[str, Any]],
        sectors: list[str],
        security_master_service,
    ) -> dict[str, Any]:
        """
        Generate impact assessment with causal chain.
        Evidence-grounded: every claim must cite evidence IDs.
        """
        # Build context from evidence
        evidence_context = "\n\n".join([
            f"[EVIDENCE {i+1}]: {text[:1500]}"
            for i, text in enumerate(evidence_texts)
        ])

        # Build entity context
        entity_context = self._build_entity_context(entities)

        prompt = f"""You are a financial intelligence analyst. Analyze the impact of this event on Indian equities.

EVENT CATEGORY: {event_category}
EVENT TEXT: {event_text[:2000]}

EVIDENCE:
{evidence_context}

ENTITIES IDENTIFIED:
{entity_context}

SECTORS INVOLVED: {", ".join(sectors) if sectors else "None"}

TASK: Provide a structured impact assessment. For EVERY factual claim, cite evidence using [EVIDENCE X] format.
If evidence is insufficient for a conclusion, state "Insufficient evidence" explicitly.

Return JSON with:
{{
  "factual_summary": "One paragraph factual summary with evidence citations",
  "direct_impacts": [
    {{"entity": "company/sector name", "impact": "description", "direction": "positive/negative/neutral", "evidence_refs": [1,2], "confidence": 0.0-1.0}}
  ],
  "indirect_impacts": [
    {{"entity": "company/sector name", "impact": "description", "direction": "positive/negative/neutral", "evidence_refs": [1,2], "confidence": 0.0-1.0}}
  ],
  "possible_beneficiaries": [
    {{"entity": "name", "reason": "why", "evidence_refs": [1], "confidence": 0.0-1.0}}
  ],
  "possible_negative_exposures": [
    {{"entity": "name", "reason": "why", "evidence_refs": [1], "confidence": 0.0-1.0}}
  ],
  "impact_direction": "positive/negative/neutral/mixed/unknown",
  "impact_horizon": "immediate/short_term/medium_term/long_term",
  "causal_chain": [
    {{"step": 1, "cause": "event", "effect": "immediate consequence", "evidence_refs": [1], "edge_type": "verified/inferred/uncertain", "confidence": 0.0-1.0}},
    {{"step": 2, "cause": "immediate consequence", "effect": "downstream effect", "evidence_refs": [1,2], "edge_type": "inferred", "confidence": 0.0-1.0}}
  ],
  "uncertainty_factors": ["list of key uncertainties"],
  "key_assumptions": ["list of assumptions made"],
  "insufficient_evidence_areas": ["areas where evidence is lacking"]
}}"""

        try:
            result = await generate(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=4096,
                temperature=0.3,
            )
            # Parse JSON from response
            import json
            content = result.content
            # Extract JSON from markdown if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                content = content.split("```")[1].split("```")[0]

            return json.loads(content.strip())
        except Exception as e:
            logger.error(f"Impact reasoning failed: {e}")
            return self._default_impact()

    def _build_entity_context(self, entities: list[dict[str, Any]]) -> str:
        lines = []
        for e in entities:
            resolution = e.get("resolution", {})
            if resolution:
                lines.append(f"- {e['text']} ({e['label']}) -> {resolution.get('company_name', 'UNKNOWN')} [{resolution.get('sector', 'UNKNOWN')}]")
            else:
                lines.append(f"- {e['text']} ({e['label']}) [UNRESOLVED]")
        return "\n".join(lines) if lines else "None"

    def _default_impact(self) -> dict[str, Any]:
        return {
            "factual_summary": "Unable to generate impact assessment.",
            "direct_impacts": [],
            "indirect_impacts": [],
            "possible_beneficiaries": [],
            "possible_negative_exposures": [],
            "impact_direction": "unknown",
            "impact_horizon": "unknown",
            "causal_chain": [],
            "uncertainty_factors": ["LLM generation failed"],
            "key_assumptions": [],
            "insufficient_evidence_areas": ["All areas"],
        }