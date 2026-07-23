"""
Remote embeddings via NVIDIA NIM /embeddings endpoint (OpenAI-compatible).
Never loads a local model — calls the API on every request.
"""

from __future__ import annotations

import logging

import httpx

from app.config import get_settings

logger = logging.getLogger("fios.ai.embeddings")
settings = get_settings()


async def embed_texts(texts: list[str]) -> list[list[float]]:
    url = f"{settings.effective_embedding_api_url}/embeddings"
    api_key = settings.effective_embedding_api_key
    payload = {
        "model": settings.EMBEDDING_MODEL,
        "input": texts,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        vectors = [item["embedding"] for item in data["data"]]
    return vectors


async def embed_query(text: str) -> list[float]:
    result = await embed_texts([text])
    return result[0]
