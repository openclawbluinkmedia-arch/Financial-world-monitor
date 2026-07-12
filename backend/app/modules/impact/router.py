from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/impact", tags=["impact"])


@router.get("/")
async def list_impacts():
    return {"message": "Not implemented"}
