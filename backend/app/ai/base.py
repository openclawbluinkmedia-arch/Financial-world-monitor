from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class GenerateResult:
    content: str
    model: str
    usage: dict[str, int] = field(default_factory=dict)


@dataclass
class EmbedResult:
    vectors: list[list[float]]
    model: str


@dataclass
class RerankResult:
    scores: list[float]
    indices: list[int]


@dataclass
class ClassifyResult:
    label: str
    confidence: float
    scores: dict[str, float] = field(default_factory=dict)


class ModelAdapter(ABC):
    adapter_name: str = "base"

    @abstractmethod
    async def generate(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = 4096,
        temperature: float = 0.6,
        **kwargs: Any,
    ) -> GenerateResult:
        ...

    @abstractmethod
    async def embed(self, texts: list[str]) -> EmbedResult:
        ...

    @abstractmethod
    async def rerank(
        self, query: str, documents: list[str], top_k: int | None = None
    ) -> RerankResult:
        ...

    @abstractmethod
    async def classify(
        self,
        text: str,
        labels: list[str],
        multi_label: bool = False,
    ) -> ClassifyResult:
        ...
