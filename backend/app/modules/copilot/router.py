from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.modules.auth.service import AuthContext, AuthContextRequired
from app.modules.copilot.schemas import (
    CopilotConversationSummary,
    CopilotMessageOut,
    CopilotQuery,
    CopilotResponse,
)
from app.modules.copilot.service import CopilotPipeline

logger = logging.getLogger("fios.copilot.router")

router = APIRouter(prefix="/copilot", tags=["copilot"])


@router.post("/chat", response_model=CopilotResponse)
async def chat(
    body: CopilotQuery,
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(AuthContextRequired()),
):
    """Submit a query to the FIOS copilot."""
    pipeline = CopilotPipeline(db, auth.tenant_id, auth.user_id, auth.role)
    response = await pipeline.run(body.message, body.mode, body.conversation_id)
    return response


@router.get("/conversations", response_model=list[CopilotConversationSummary])
async def list_conversations(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(AuthContextRequired()),
):
    """List all copilot conversations for this tenant."""
    pipeline = CopilotPipeline(db, auth.tenant_id, auth.user_id, auth.role)
    items, total = await pipeline.list_conversations(page, page_size)
    return items


@router.get("/conversations/{conversation_id}/messages", response_model=list[CopilotMessageOut])
async def get_messages(
    conversation_id: str,
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    auth: AuthContext = Depends(AuthContextRequired()),
):
    """Get messages for a conversation."""
    pipeline = CopilotPipeline(db, auth.tenant_id, auth.user_id, auth.role)
    items, total = await pipeline.get_history(conversation_id, page, page_size)
    if not items and total == 0:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return items
