from __future__ import annotations

import hashlib
import logging
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlparse

import httpx
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential_jitter,
)

from app.modules.evidence.models import Jurisdiction, SourceType

logger = logging.getLogger("fios.ingestion.connectors")


class ConnectorConfig:
    def __init__(
        self,
        name: str = "",
        source_type: str = "",
        base_url: str | None = None,
        schedule_cron: str | None = None,
        rate_limit_per_minute: int = 60,
        timeout_seconds: int = 30,
        retry_attempts: int = 3,
        retry_base_delay: float = 1.0,
        custom_headers: dict[str, str] | None = None,
        **kwargs: Any,
    ):
        # Use class defaults if not provided
        cls = self.__class__
        if not name and hasattr(cls, 'name'):
            name = getattr(cls, 'name', '')
        if not source_type and hasattr(cls, 'source_type'):
            source_type = getattr(cls, 'source_type', '')
        if base_url is None and hasattr(cls, 'base_url'):
            base_url = getattr(cls, 'base_url', None)

        self.name = name
        self.source_type = source_type
        self.base_url = base_url
        self.schedule_cron = schedule_cron
        self.rate_limit_per_minute = rate_limit_per_minute
        self.timeout_seconds = timeout_seconds
        self.retry_attempts = retry_attempts
        self.retry_base_delay = retry_base_delay
        self.custom_headers = custom_headers or {}

        # Copy other class attributes
        for key, value in cls.__dict__.items():
            if not key.startswith('_') and key not in (
                'name', 'source_type', 'base_url', 'schedule_cron',
                'rate_limit_per_minute', 'timeout_seconds',
                'retry_attempts', 'retry_base_delay', 'custom_headers',
                '__module__', '__qualname__', '__annotations__', '__dict__',
                '__weakref__', '__doc__', '__init__'
            ):
                if not callable(value) and key not in kwargs and not hasattr(self, key):
                    setattr(self, key, value)

        for k, v in kwargs.items():
            setattr(self, k, v)


@dataclass
class IngestionItem:
    source_id: uuid.UUID
    source_name: str
    original_url: str | None
    publisher: str | None
    title: str
    raw_content: str
    publication_ts: datetime | None
    jurisdiction: Jurisdiction
    source_type: SourceType
    content_hash: str = ""
    near_dup_hash: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    is_mock: bool = False

    def __post_init__(self):
        if not self.content_hash:
            self.content_hash = self.compute_content_hash(self.raw_content)
        if self.near_dup_hash is None:
            self.near_dup_hash = self.compute_near_dup_hash(self.raw_content)

    @staticmethod
    def compute_content_hash(content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    @staticmethod
    def compute_near_dup_hash(content: str) -> str | None:
        try:
            from simhash import Simhash
            return str(Simhash(content).value)
        except Exception:
            return None


@dataclass
class ConnectorResult:
    items: list[IngestionItem] = field(default_factory=list)
    errors: list[tuple[str, Exception]] = field(default_factory=list)
    health_status: str = "healthy"
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def success_count(self) -> int:
        return len(self.items)

    @property
    def error_count(self) -> int:
        return len(self.errors)


class BaseConnector(ABC):
    def __init__(self, config: ConnectorConfig):
        self.config = config
        self.name = config.name
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(config.timeout_seconds),
            follow_redirects=True,
        )
        self._semaphore: Any = None
        self._last_run_at: datetime | None = None
        self._consecutive_failures = 0
        self._last_error: str | None = None

    async def __aenter__(self):
        import asyncio
        self._semaphore = asyncio.Semaphore(max(1, int(self.config.rate_limit_per_minute / 60)))
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    @property
    @abstractmethod
    def connector_name(self) -> str:
        pass

    @abstractmethod
    async def fetch(self) -> ConnectorResult:
        pass

    @abstractmethod
    async def health_check(self) -> tuple[bool, str]:
        pass

    def _make_evidence_id(self, source_name: str, url: str | None, title: str) -> str:
        content = f"{source_name}:{url or ''}:{title}"
        return hashlib.sha256(content.encode()).hexdigest()[:32]

    def _compute_content_hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _compute_near_dup_hash(self, content: str) -> str:
        from simhash import Simhash
        return str(Simhash(content).value)

    def _normalize_text(self, text: str) -> str:
        import re
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", text)
        return text.strip()

    def _extract_publisher(self, url: str | None) -> str | None:
        if not url:
            return None
        try:
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except Exception:
            return None

    def _build_ingestion_item(
        self,
        title: str,
        raw_content: str,
        original_url: str | None,
        publisher: str | None,
        publication_ts: datetime | None,
        jurisdiction: Jurisdiction,
        metadata: dict[str, Any] | None = None,
        is_mock: bool = False,
    ) -> IngestionItem:
        return IngestionItem(
            source_id=uuid.uuid4(),
            source_name=self.config.name,
            original_url=original_url,
            publisher=publisher,
            title=title,
            raw_content=raw_content,
            publication_ts=publication_ts,
            jurisdiction=jurisdiction,
            source_type=SourceType(self.config.source_type),
            metadata=metadata or {},
            is_mock=is_mock,
        )

    def update_health(self, success: bool, error: str | None = None):
        self._last_run_at = datetime.now(timezone.utc)
        if success:
            self._consecutive_failures = 0
            self._last_error = None
        else:
            self._consecutive_failures += 1
            self._last_error = error

    def get_health_status(self) -> dict[str, Any]:
        if self._consecutive_failures == 0:
            status = "healthy"
        elif self._consecutive_failures <= 2:
            status = "degraded"
        else:
            status = "failed"
        return {
            "connector": self.connector_name,
            "status": status,
            "last_run_at": self._last_run_at.isoformat() if self._last_run_at else None,
            "consecutive_failures": self._consecutive_failures,
            "last_error": self._last_error,
        }

    @retry(
        wait=wait_exponential_jitter(initial=1, max=60),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError)),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        if self._semaphore:
            async with self._semaphore:
                return await self._client.request(method, url, **kwargs)
        return await self._client.request(method, url, **kwargs)

    async def _get(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._make_request("GET", url, **kwargs)

    async def _post(self, url: str, **kwargs: Any) -> httpx.Response:
        return await self._make_request("POST", url, **kwargs)
