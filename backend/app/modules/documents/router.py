from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("/")
async def list_documents():
    return {"message": "Not implemented"}
