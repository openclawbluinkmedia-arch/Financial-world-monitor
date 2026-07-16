from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class CopilotQuery(BaseModel):
    conversation_id: str | None = None
    message: str = Field(..., min_length=1, max_length=10000)
    mode: str = Field(default="market_intelligence", pattern=r"^(market_intelligence|portfolio_impact)$")


class CitationSource(BaseModel):
    evidence_id: str
    title: str
    snippet: str
    source_name: str
    similarity: float | None = None
    url: str | None = None


class CopilotResponse(BaseModel):
    conversation_id: str
    message_id: str
    answer: str
    verified_facts: list[str] = []
    analysis: str | None = None
    portfolio_relevance: str | None = None
    uncertainty: str | None = None
    sources: list[CitationSource] = []
    abstained: bool = False
    abstention_reason: str | None = None


class CopilotConversationSummary(BaseModel):
    id: str
    title: str
    mode: str
    message_count: int
    created_at: datetime
    updated_at: datetime


class CopilotMessageOut(BaseModel):
    id: str
    role: str
    content: str
    sources: list[CitationSource] | None = None
    verified_facts: list[str] | None = None
    analysis: str | None = None
    portfolio_relevance: str | None = None
    uncertainty: str | None = None
    abstained: bool = False
    abstention_reason: str | None = None
    created_at: datetime
