from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from app.modules.evidence.models import Jurisdiction, SourceType
from app.modules.ingestion.connectors.base import BaseConnector, ConnectorConfig, ConnectorResult, IngestionItem

logger = logging.getLogger("fios.ingestion.connectors.world_monitor")


class WorldMonitorConfig(ConnectorConfig):
    name: str = "world_monitor"
    source_type: str = "world_monitor"
    base_url: str = "http://worldmonitor:8080"
    api_key: str | None = None
    endpoints: dict[str, str] = {
        "events": "/api/v1/events",
        "finance": "/api/v1/finance/events",
        "geopolitics": "/api/v1/geopolitics/events",
    }
    timeout: int = 60


class WorldMonitorConnector(BaseConnector):
    def __init__(self, config: WorldMonitorConfig | None = None):
        if config is None:
            config = WorldMonitorConfig()
        super().__init__(config)
        self.base_url = config.base_url.rstrip("/")
        self.api_key = config.api_key
        self.endpoints = config.endpoints
        self.timeout = config.timeout

    @property
    def connector_name(self) -> str:
        return "world_monitor"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()
        for endpoint_name, endpoint_path in self.endpoints.items():
            try:
                items = await self._fetch_endpoint(endpoint_name, endpoint_path)
                result.items.extend(items)
                logger.info(f"WorldMonitor {endpoint_name}: fetched {len(items)} items")
            except Exception as e:
                logger.error(f"WorldMonitor {endpoint_name} fetch failed: {e}")
                result.errors.append((endpoint_name, e))

        self.update_health(len(result.errors) == 0, str(result.errors[0][1]) if result.errors else None)
        return result

    async def _fetch_endpoint(self, endpoint_name: str, endpoint_path: str) -> list[IngestionItem]:
        url = f"{self.base_url}{endpoint_path}"
        headers = {"Accept": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        response = await self._get(url, headers=headers)
        data = response.json()

        items = []
        events = data.get("events", data.get("data", []))
        for event in events:
            try:
                item = self._parse_event(event, endpoint_name)
                if item:
                    items.append(item)
            except Exception as e:
                logger.error(f"Error parsing WorldMonitor event: {e}", exc_info=True)

        return items

    def _parse_event(self, event: dict, endpoint_name: str) -> IngestionItem | None:
        title = event.get("title", "").strip()
        url = event.get("url", "").strip()
        published = event.get("published_at", event.get("date", "")).strip()
        summary = event.get("summary", event.get("description", "")).strip()
        source = event.get("source", "").strip()

        if not title:
            return None

        pub_ts = self._parse_date(published)
        content = f"{title}\n\n{summary}\n\nSource: {source}"
        publisher = source or "World Monitor"

        jurisdiction = Jurisdiction.GLOBAL
        if event.get("country"):
            country = event["country"].upper()
            if country in [j.value for j in Jurisdiction]:
                jurisdiction = Jurisdiction(country)

        return self._build_ingestion_item(
            title=title,
            raw_content=content,
            original_url=url,
            publisher=publisher,
            publication_ts=pub_ts,
            jurisdiction=jurisdiction,
            metadata={
                "wm_endpoint": endpoint_name,
                "wm_event_type": event.get("event_type"),
                "wm_actors": event.get("actors"),
                "wm_location": event.get("location"),
                "wm_severity": event.get("severity"),
            },
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def health_check(self) -> tuple[bool, str]:
        try:
            url = f"{self.base_url}/health"
            response = await self._get(url)
            data = response.json()
            status = data.get("status", "unknown")
            if status == "healthy":
                return True, "World Monitor service healthy"
            return False, f"World Monitor status: {status}"
        except Exception as e:
            return False, f"World Monitor health check failed: {e}"