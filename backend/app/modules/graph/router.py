from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/graph", tags=["graph"])


@router.get("/")
async def get_graph():
    return {"message": "Not implemented"}
