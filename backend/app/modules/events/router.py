from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/events", tags=["events"])


@router.get("/")
async def list_events():
    return {"message": "Not implemented"}
