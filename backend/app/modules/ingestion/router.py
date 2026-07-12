from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/ingestion", tags=["ingestion"])


@router.get("/")
async def list_runs():
    return {"message": "Not implemented"}
