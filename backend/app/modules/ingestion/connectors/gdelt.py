from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser

from app.modules.evidence.models import Jurisdiction
from app.modules.ingestion.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    IngestionItem,
)

logger = logging.getLogger("fios.ingestion.connectors.gdelt")


class GDELTConfig(ConnectorConfig):
    name: str = "gdelt"
    source_type: str = "gdelt"
    base_url: str = "https://api.gdeltproject.org/api/v2/summary/summary"
    query: str = "finance OR banking OR economy OR market OR stock OR trade"
    mode: str = "artlist"
    format: str = "rss"
    max_records: int = 250
    timespan_hours: int = 24


class GDELTConnector(BaseConnector):
    def __init__(self, config: GDELTConfig | None = None):
        if config is None:
            config = GDELTConfig()
        super().__init__(config)
        self.base_url = config.base_url
        self.query = config.query
        self.mode = config.mode
        self.format = config.format
        self.max_records = config.max_records
        self.timespan_hours = config.timespan_hours

    @property
    def connector_name(self) -> str:
        return "gdelt"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()
        try:
            params = {
                "query": self.query,
                "mode": self.mode,
                "format": self.format,
                "maxrecords": self.max_records,
                "timespan": f"{self.timespan_hours}H",
            }
            logger.info(f"Fetching GDELT events: {params}")
            response = await self._get(self.base_url, params=params)
            feed = feedparser.parse(response.text)

            for entry in feed.entries:
                try:
                    item = self._parse_entry(entry)
                    if item:
                        result.items.append(item)
                except Exception as e:
                    logger.error(f"Error parsing GDELT entry: {e}", exc_info=True)
                    result.errors.append(("parse", e))

            logger.info(f"GDELTConnector fetched {len(result.items)} items")
        except Exception as e:
            logger.error(f"Error fetching GDELT events: {e}", exc_info=True)
            result.errors.append(("fetch", e))

        self.update_health(len(result.errors) == 0, str(result.errors[0][1]) if result.errors else None)
        return result

    def _parse_entry(self, entry: dict) -> IngestionItem | None:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        published = entry.get("published", "").strip()
        summary = entry.get("summary", "").strip()

        if not title or not link:
            return None

        pub_ts = self._parse_date(published)
        content = f"{title}\n\n{summary}"

        return self._build_ingestion_item(
            title=title,
            raw_content=content,
            original_url=link,
            publisher="GDELT Project",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.GLOBAL,
            metadata={
                "gdelt_query": self.query,
                "gdelt_mode": self.mode,
            },
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%a, %d %b %Y %H:%M:%S %Z",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%d %H:%M:%S",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def health_check(self) -> tuple[bool, str]:
        try:
            params = {
                "query": self.query,
                "mode": self.mode,
                "format": self.format,
                "maxrecords": 10,
            }
            response = await self._get(self.base_url, params=params)
            feed = feedparser.parse(response.text)
            return True, f"GDELT API accessible ({len(feed.entries)} test records)"
        except Exception as e:
            return False, f"GDELT health check failed: {e}"
