from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("/")
async def list_sources():
    return {"message": "Not implemented"}
