from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.modules.evidence.models import Jurisdiction, SourceType
from app.modules.ingestion.connectors.base import BaseConnector, ConnectorConfig, ConnectorResult, IngestionItem

logger = logging.getLogger("fios.ingestion.connectors.nse")


class NSEConfig(ConnectorConfig):
    name: str = "nse"
    source_type: str = "api"
    base_url: str = "https://www.nseindia.com"
    announcements_api: str = "https://www.nseindia.com/api/corporate-announcements"
    equity_announcements_api: str = "https://www.nseindia.com/api/corporate-announcements-equities"
    headers: dict[str, str] = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
    }
    max_pages: int = 3
    page_size: int = 50


class NSEConnector(BaseConnector):
    def __init__(self, config: NSEConfig | None = None):
        if config is None:
            config = NSEConfig()
        super().__init__(config)
        self.base_url = config.base_url
        self.announcements_api = config.announcements_api
        self.equity_api = config.equity_announcements_api
        self.custom_headers = config.headers
        self.max_pages = config.max_pages
        self.page_size = config.page_size
        self._degraded = False

    @property
    def connector_name(self) -> str:
        return "nse"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()

        if self._degraded:
            logger.warning("NSEConnector is in degraded mode - returning mock data")
            result.items.append(self._generate_mock_item())
            result.health_status = "degraded"
            self.update_health(False, "Degraded mode active")
            return result

        for url in [self.announcements_api, self.equity_api]:
            try:
                items = await self._fetch_announcements(url)
                result.items.extend(items)
                logger.info(f"NSE announcements from {url}: {len(items)} items")
            except Exception as e:
                logger.error(f"NSE fetch failed for {url}: {e}")
                result.errors.append((url, e))
                self._degraded = True

        if self._degraded:
            result.health_status = "degraded"
            result.items.append(self._generate_mock_item())

        self.update_health(not self._degraded, str(result.errors[0][1]) if result.errors else None)
        return result

    async def _fetch_announcements(self, url: str) -> list[IngestionItem]:
        headers = dict(self.custom_headers)
        response = await self._get(url, headers=headers)

        if response.status_code in (401, 403):
            logger.warning("NSE session expired, reinitializing")
            self._degraded = True
            return []

        data = response.json()
        items = []

        for ann in data.get("data", [])[:self.page_size * self.max_pages]:
            try:
                item = self._parse_announcement(ann)
                if item:
                    items.append(item)
            except Exception as e:
                logger.error(f"Error parsing NSE announcement: {e}", exc_info=True)

        return items

    def _parse_announcement(self, ann: dict) -> IngestionItem | None:
        symbol = ann.get("symbol", "").strip()
        subject = ann.get("subject", "").strip()
        description = ann.get("desc", "").strip()
        date_str = ann.get("dissemDT", ann.get("date", "")).strip()
        attachment = ann.get("attach", "").strip()

        if not symbol or not subject:
            return None

        pub_ts = self._parse_date(date_str)
        title = f"{symbol}: {subject}"
        content = f"Symbol: {symbol}\nSubject: {subject}\nDescription: {description}\nDate: {date_str}"

        pdf_url = None
        if attachment:
            pdf_url = attachment if attachment.startswith("http") else f"{self.base_url}{attachment}"

        return self._build_ingestion_item(
            title=title,
            raw_content=content,
            original_url=pdf_url,
            publisher="nseindia.com",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata={
                "symbol": symbol,
                "subject": subject,
                "attachment": attachment,
                "degraded": self._degraded,
            },
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%d-%b-%Y %H:%M:%S",
            "%d-%b-%Y",
            "%d/%m/%Y",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        logger.warning(f"Could not parse NSE date: {date_str}")
        return None

    def _generate_mock_item(self) -> IngestionItem:
        return self._build_ingestion_item(
            title="[MOCK] NSE Corporate Announcement - Sample",
            raw_content="This is mock data because NSE connector is in degraded mode. Real data unavailable.",
            original_url=None,
            publisher="nseindia.com",
            publication_ts=datetime.now(timezone.utc),
            jurisdiction=Jurisdiction.IN,
            metadata={"degraded": True, "mock": True},
            is_mock=True,
        )

    async def health_check(self) -> tuple[bool, str]:
        if self._degraded:
            return False, "NSE connector degraded - returning mock data only"
        try:
            headers = {"Referer": self.custom_headers.get("Referer", "")}
            response = await self._get(self.announcements_api, headers=headers, params={"index": "equities"})
            if response.status_code == 200:
                data = response.json()
                count = len(data.get("data", []))
                return True, f"NSE API accessible ({count} announcements)"
            elif response.status_code in (401, 403):
                self._degraded = True
                return False, f"NSE authentication required (status {response.status_code}) - DEGRADED"
            else:
                return False, f"NSE API error: {response.status_code}"
        except Exception as e:
            self._degraded = True
            return False, f"NSE health check failed: {e} - DEGRADED"