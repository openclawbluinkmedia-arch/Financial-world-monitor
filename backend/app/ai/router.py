"""
Model Abstraction Layer — single interface for generating, embedding, reranking, classifying.

Provider selection is driven entirely by the DEPLOYMENT_MODE env flag.
Model slugs are read from .env — never hard-coded in business logic.

Dev mode:   NVIDIA NIM (primary) -> OpenRouter (fallback on rate-limit/error)
Customer mode: self-hosted vLLM (no external API calls)

NOTE: Free tiers (NVIDIA NIM, OpenRouter) are for dev/demo on public or synthetic data ONLY.
Real customer data must run in DEPLOYMENT_MODE=customer with a self-hosted vLLM endpoint.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

from app.ai.adapters.openai_compat import OpenAICompatibleAdapter
from app.ai.adapters.vllm import VLLMAdapter
from app.ai.base import (
    ClassifyResult,
    EmbedResult,
    GenerateResult,
    ModelAdapter,
    RerankResult,
)
from app.config import get_settings

logger = logging.getLogger("fios.ai.router")


def _build_dev_adapter() -> list[ModelAdapter]:
    primary = OpenAICompatibleAdapter(
        base_url=get_settings().NVIDIA_BASE_URL,
        api_key=get_settings().NVIDIA_API_KEY,
        model_slug=get_settings().NVIDIA_MODEL_SLUG,
        adapter_name="nvidia_nim",
    )
    fallback = OpenAICompatibleAdapter(
        base_url=get_settings().OPENROUTER_BASE_URL,
        api_key=get_settings().OPENROUTER_API_KEY,
        model_slug=get_settings().OPENROUTER_MODEL_SLUG,
        adapter_name="openrouter",
    )
    return [primary, fallback]


def _build_customer_adapter() -> list[ModelAdapter]:
    return [
        VLLMAdapter(
            base_url=get_settings().VLLM_BASE_URL,
            model_slug=get_settings().VLLM_MODEL_SLUG,
        )
    ]


def _get_adapters() -> list[ModelAdapter]:
    if get_settings().is_customer:
        return _build_customer_adapter()
    return _build_dev_adapter()


async def generate(
    messages: list[dict[str, str]],
    max_tokens: int = 4096,
    temperature: float = 0.6,
    **kwargs: Any,
) -> GenerateResult:
    adapters = _get_adapters()
    last_error: Exception | None = None
    for adapter in adapters:
        try:
            return await adapter.generate(
                messages=messages, max_tokens=max_tokens, temperature=temperature, **kwargs
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            last_error = e
            logger.warning(
                "Adapter %s failed with %s, trying next...", adapter.adapter_name, e
            )
    msg = f"All adapters failed. Last error: {last_error}"
    logger.error(msg)
    raise RuntimeError(msg) from last_error


async def embed(texts: list[str]) -> EmbedResult:
    from app.ai.embeddings import embed_texts

    vectors = await embed_texts(texts)
    return EmbedResult(vectors=vectors, model=get_settings().EMBEDDING_MODEL)


async def rerank(
    query: str, documents: list[str], top_k: int | None = None
) -> RerankResult:
    adapters = _get_adapters()
    last_error: Exception | None = None
    for adapter in adapters:
        try:
            return await adapter.rerank(query=query, documents=documents, top_k=top_k)
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            last_error = e
            logger.warning(
                "Adapter %s rerank failed with %s, trying next...",
                adapter.adapter_name,
                e,
            )
    msg = f"All adapters failed for rerank. Last error: {last_error}"
    logger.error(msg)
    raise RuntimeError(msg) from last_error


async def classify(
    text: str,
    labels: list[str],
    multi_label: bool = False,
) -> ClassifyResult:
    adapters = _get_adapters()
    last_error: Exception | None = None
    for adapter in adapters:
        try:
            return await adapter.classify(
                text=text, labels=labels, multi_label=multi_label
            )
        except (httpx.HTTPStatusError, httpx.RequestError) as e:
            last_error = e
            logger.warning(
                "Adapter %s classify failed with %s, trying next...",
                adapter.adapter_name,
                e,
            )
    msg = f"All adapters failed for classify. Last error: {last_error}"
    logger.error(msg)
    raise RuntimeError(msg) from last_error
