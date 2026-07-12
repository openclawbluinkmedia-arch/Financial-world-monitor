"""
Local embeddings via sentence-transformers (BAAI/bge-m3).
Always runs on CPU — never sends evidence text to a third-party cloud.

NOTE: The model is lazy-loaded on first call to avoid importing
sentence-transformers at module load time. The first call will
download the model if not cached.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from app.config import get_settings

logger = logging.getLogger("fios.ai.embeddings")

settings = get_settings()


@lru_cache()
def _get_embedding_model():
    from sentence_transformers import SentenceTransformer

    logger.info(
        "Loading embedding model %s (CPU, this may take a moment on first call)",
        settings.EMBEDDING_MODEL,
    )
    model = SentenceTransformer(
        settings.EMBEDDING_MODEL,
        device="cpu",
    )
    logger.info("Embedding model loaded successfully")
    return model


async def embed_texts(texts: list[str]) -> list[list[float]]:
    model = _get_embedding_model()
    embeddings = model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
    return embeddings.tolist()


async def embed_query(text: str) -> list[float]:
    result = await embed_texts([text])
    return result[0]
