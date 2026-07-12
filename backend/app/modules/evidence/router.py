from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/evidence", tags=["evidence"])


@router.get("/")
async def list_evidence():
    return {"message": "Not implemented"}
