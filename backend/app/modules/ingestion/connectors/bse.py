from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx
from lxml import html

from app.modules.evidence.models import Jurisdiction, SourceType
from app.modules.ingestion.connectors.base import BaseConnector, ConnectorConfig, ConnectorResult, IngestionItem

logger = logging.getLogger("fios.ingestion.connectors.bse")


class BSEConfig(ConnectorConfig):
    name: str = "bse"
    source_type: str = "scraper"
    base_url: str = "https://www.bseindia.com"
    announcements_url: str = "https://www.bseindia.com/corporates/ann.html"
    max_pages: int = 5
    items_per_page: int = 20


class BSEConnector(BaseConnector):
    def __init__(self, config: BSEConfig | None = None):
        if config is None:
            config = BSEConfig()
        super().__init__(config)
        self.base_url = config.base_url
        self.announcements_url = config.announcements_url
        self.max_pages = config.max_pages
        self.items_per_page = config.items_per_page

    @property
    def connector_name(self) -> str:
        return "bse"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()
        try:
            logger.info(f"Fetching BSE announcements from {self.announcements_url}")
            response = await self._get(self.announcements_url)
            tree = html.fromstring(response.text)

            # Find the announcements table
            rows = tree.xpath("//table[contains(@class, 'table')]//tr")
            for row in rows[1:]:  # Skip header
                try:
                    item = self._parse_row(row)
                    if item:
                        result.items.append(item)
                except Exception as e:
                    logger.error(f"Error parsing BSE row: {e}", exc_info=True)
                    result.errors.append(("parse", e))

            logger.info(f"BSEConnector fetched {len(result.items)} items")
        except Exception as e:
            logger.error(f"Error fetching BSE announcements: {e}", exc_info=True)
            result.errors.append(("fetch", e))

        self.update_health(len(result.errors) == 0, str(result.errors[0][1]) if result.errors else None)
        return result

    def _parse_row(self, row) -> IngestionItem | None:
        cells = row.xpath(".//td")
        if len(cells) < 4:
            return None

        company = cells[0].text_content().strip()
        subject = cells[1].text_content().strip()
        date_str = cells[2].text_content().strip()
        link_elem = cells[3].xpath(".//a[@href]")
        pdf_url = link_elem[0].get("href") if link_elem else None

        if not company or not subject:
            return None

        pub_ts = self._parse_date(date_str)
        title = f"{company}: {subject}"
        content = f"Company: {company}\nSubject: {subject}\nDate: {date_str}"

        if pdf_url and not pdf_url.startswith("http"):
            pdf_url = f"{self.base_url}{pdf_url}"

        return self._build_ingestion_item(
            title=title,
            raw_content=content,
            original_url=pdf_url,
            publisher="bseindia.com",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata={
                "company": company,
                "subject": subject,
                "pdf_url": pdf_url,
            },
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%d %b %Y",
            "%d-%b-%Y",
            "%d/%m/%Y",
            "%Y-%m-%d",
        ]
        for fmt in formats:
            try:
                return datetime.strptime(date_str.strip(), fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        logger.warning(f"Could not parse BSE date: {date_str}")
        return None

    async def health_check(self) -> tuple[bool, str]:
        try:
            response = await self._get(self.announcements_url)
            tree = html.fromstring(response.text)
            rows = tree.xpath("//table[contains(@class, 'table')]//tr")
            return True, f"BSE announcements page accessible ({len(rows)} rows found)"
        except Exception as e:
            return False, f"BSE health check failed: {e}"