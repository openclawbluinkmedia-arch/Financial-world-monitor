from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/portfolios", tags=["portfolios"])


@router.get("/")
async def list_portfolios():
    return {"message": "Not implemented"}
