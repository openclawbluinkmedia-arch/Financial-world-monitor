from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login")
async def login():
    return {"message": "Not implemented"}


@router.post("/register")
async def register():
    return {"message": "Not implemented"}
