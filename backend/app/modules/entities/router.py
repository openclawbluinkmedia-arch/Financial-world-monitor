from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/entities", tags=["entities"])


@router.get("/")
async def list_entities():
    return {"message": "Not implemented"}
