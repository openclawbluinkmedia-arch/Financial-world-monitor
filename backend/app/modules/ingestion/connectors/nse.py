from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.modules.evidence.models import Jurisdiction
from app.modules.ingestion.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    IngestionItem,
)

logger = logging.getLogger("fios.ingestion.connectors.nse")

NSE_BASE = "https://www.nseindia.com"
NSE_HOMEPAGE = f"{NSE_BASE}/"
# The equities corporate-announcements API returns a JSON array of items.
NSE_ANNOUNCEMENTS_API = f"{NSE_BASE}/api/corporate-announcements-equities"


class NSEConfig(ConnectorConfig):
    name: str = "nse"
    source_type: str = "api"
    base_url: str = NSE_BASE
    announcements_api: str = NSE_ANNOUNCEMENTS_API
    browser_headers: dict[str, str] = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://www.nseindia.com/companies-listing/corporate-filings-announcements",
    }
    max_items: int = 50


class NSEConnector(BaseConnector):
    def __init__(self, config: NSEConfig | None = None):
        if config is None:
            config = NSEConfig()
        super().__init__(config)
        self.api_url = config.announcements_api
        self.browser_headers = config.browser_headers
        self.max_items = config.max_items
        self._primed = False

    @property
    def connector_name(self) -> str:
        return "nse"

    async def _prime_session(self) -> bool:
        """NSE requires a session cookie set by visiting the homepage first."""
        if self._primed:
            return True
        try:
            logger.info("Priming NSE session — visiting homepage for cookies")
            resp = await self._get(NSE_HOMEPAGE, headers={
                "User-Agent": self.browser_headers["User-Agent"],
            })
            resp.raise_for_status()
            self._primed = True
            logger.info("NSE session primed successfully")
            return True
        except Exception as e:
            logger.warning(f"NSE session priming failed: {e}")
            return False

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()

        # Prime session cookie
        primed = await self._prime_session()
        if not primed:
            logger.warning("NSE: cannot prime session — returning mock")
            result.items.append(self._generate_mock_item())
            result.health_status = "degraded"
            self.update_health(False, "Session priming failed")
            return result

        # Fetch announcements
        try:
            logger.info(f"Fetching NSE announcements from {self.api_url}")
            response = await self._get(
                self.api_url,
                params={"index": "equities"},
                headers=self.browser_headers,
            )
            response.raise_for_status()
            data = response.json()

            # The NSE API returns a flat list or {"data": [...]}
            items_data = data if isinstance(data, list) else data.get("data", data.get("items", []))

            if not isinstance(items_data, list):
                logger.warning(f"NSE API returned unexpected format: {type(data)}")
                result.errors.append(("parse", ValueError("Unexpected API response format")))
                items_data = []

            count = 0
            for ann in items_data:
                if count >= self.max_items:
                    break
                try:
                    item = self._parse_announcement(ann)
                    if item:
                        result.items.append(item)
                        count += 1
                except Exception as e:
                    logger.error(f"NSE parse error: {e}")

            logger.info(f"NSEConnector fetched {len(result.items)} items")
        except Exception as e:
            logger.error(f"NSE fetch error: {e}")
            result.errors.append(("fetch", e))

        if not result.items:
            logger.warning("NSE: no real items — adding MOCK placeholder")
            result.items.append(self._generate_mock_item())
            result.health_status = "degraded"

        self.update_health(
            len([e for e in result.errors if e[0] != "mock"]) == 0,
            str(result.errors[0][1]) if result.errors else None,
        )
        return result

    def _parse_announcement(self, ann: dict) -> IngestionItem | None:
        symbol = ann.get("symbol", ann.get("company", "")).strip()
        subject = ann.get("subject", ann.get("purpose", ann.get("desc", ""))).strip()
        date_str = ann.get("disseminationDate", ann.get("dissemDT", ann.get("date", ""))).strip()
        attachment = ann.get("attachment", ann.get("attach", "")).strip()

        if not symbol or not subject:
            return None

        pub_ts = self._parse_date(date_str) if date_str else None
        title = f"{symbol}: {subject}"
        content = f"Symbol: {symbol}\nSubject: {subject}\nDate: {date_str or 'Unknown'}"

        pdf_url = None
        if attachment:
            pdf_url = attachment if attachment.startswith("http") else f"{NSE_BASE}{attachment}"

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
                "pdf_url": pdf_url,
            },
        )

    def _generate_mock_item(self) -> IngestionItem:
        return self._build_ingestion_item(
            title="[MOCK] NSE Corporate Announcement",
            raw_content="NSE API unavailable. Mock data returned.",
            original_url=None,
            publisher="nseindia.com",
            publication_ts=datetime.now(timezone.utc),
            jurisdiction=Jurisdiction.IN,
            metadata={"degraded": True, "mock": True},
            is_mock=True,
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%d-%b-%Y %H:%M:%S",
            "%d-%b-%Y",
            "%d/%m/%Y",
            "%Y-%m-%d",
            "%Y-%m-%d %H:%M:%S",
        ]
        date_str = date_str.strip().replace("  ", " ")
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def health_check(self) -> tuple[bool, str]:
        try:
            primed = await self._prime_session()
            if not primed:
                return False, "NSE session priming failed — DEGRADED"
            response = await self._get(
                self.api_url,
                params={"index": "equities"},
                headers=self.browser_headers,
            )
            if response.status_code == 200:
                data = response.json()
                items = data if isinstance(data, list) else data.get("data", [])
                count = len(items) if isinstance(items, list) else 0
                return True, f"NSE API accessible ({count} announcements)"
            return False, f"NSE API returned {response.status_code} — DEGRADED"
        except Exception as e:
            return False, f"NSE health check failed: {e} — DEGRADED"

    async def __aenter__(self):
        # Reset primed flag on new session
        self._primed = False
        return await super().__aenter__()
