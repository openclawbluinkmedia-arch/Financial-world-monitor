from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/")
async def list_audit_logs():
    return {"message": "Not implemented"}
