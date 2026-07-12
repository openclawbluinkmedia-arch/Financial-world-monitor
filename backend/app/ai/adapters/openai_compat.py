from __future__ import annotations

import logging
from typing import Any

import httpx

from app.ai.base import (
    ClassifyResult,
    EmbedResult,
    GenerateResult,
    ModelAdapter,
    RerankResult,
)

logger = logging.getLogger("fios.ai.openai_compat")


class OpenAICompatibleAdapter(ModelAdapter):
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model_slug: str,
        adapter_name: str = "openai_compat",
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model_slug = model_slug
        self.adapter_name = adapter_name
        self._client = httpx.AsyncClient(timeout=120.0)

    async def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.6,
        **kwargs: Any,
    ) -> GenerateResult:
        payload = {
            "model": self.model_slug,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "top_p": kwargs.get("top_p", 0.95),
            "top_k": kwargs.get("top_k", 20),
            "presence_penalty": kwargs.get("presence_penalty", 0),
            "repetition_penalty": kwargs.get("repetition_penalty", 1),
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(
            f"{self.base_url}/chat/completions",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        choice = data["choices"][0]
        content = choice.get("message", {}).get("content", "")
        usage = data.get("usage", {})
        return GenerateResult(content=content, model=self.model_slug, usage=usage)

    async def embed(self, texts: list[str]) -> EmbedResult:
        payload = {
            "model": self.model_slug,
            "input": texts,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(
            f"{self.base_url}/embeddings",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        vectors = [item["embedding"] for item in data["data"]]
        return EmbedResult(vectors=vectors, model=self.model_slug)

    async def rerank(
        self, query: str, documents: list[str], top_k: int | None = None
    ) -> RerankResult:
        payload: dict[str, Any] = {
            "model": self.model_slug,
            "query": query,
            "documents": documents,
        }
        if top_k is not None:
            payload["top_k"] = top_k
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        resp = await self._client.post(
            f"{self.base_url}/rerank",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])
        scores = [r["relevance_score"] for r in results]
        indices = [r["index"] for r in results]
        return RerankResult(scores=scores, indices=indices)

    async def classify(
        self,
        text: str,
        labels: list[str],
        multi_label: bool = False,
    ) -> ClassifyResult:
        prompt = (
            f"Classify the following text into one of these categories: {', '.join(labels)}.\n\n"
            f"Text: {text}\n\n"
            f"Answer with only the category label."
        )
        result = await self.generate(messages=[{"role": "user", "content": prompt}])
        label = result.content.strip()
        return ClassifyResult(label=label, confidence=1.0)
