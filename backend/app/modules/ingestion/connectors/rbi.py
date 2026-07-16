from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

from lxml import html as lxml_html

from app.modules.evidence.models import Jurisdiction
from app.modules.ingestion.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    IngestionItem,
)

logger = logging.getLogger("fios.ingestion.connectors.rbi")

RBI_BASE = "https://www.rbi.org.in"
PRESS_RELEASE_URL = f"{RBI_BASE}/scripts/BS_PressReleaseDisplay.aspx"
NOTIFICATIONS_URL = f"{RBI_BASE}/scripts/NotificationUser.aspx"
SPEECHES_URL = f"{RBI_BASE}/scripts/BS_SpeechesView.aspx"
CIRCULARS_URL = f"{RBI_BASE}/scripts/BS_CircularIndexDisplay.aspx"


class RBIConfig(ConnectorConfig):
    name: str = "rbi"
    source_type: str = "scraper"
    base_url: str = RBI_BASE
    press_releases_url: str = PRESS_RELEASE_URL
    notifications_url: str = NOTIFICATIONS_URL
    speeches_url: str = SPEECHES_URL
    circulars_url: str = CIRCULARS_URL
    max_items: int = 50


class RBIConnector(BaseConnector):
    def __init__(self, config: RBIConfig | None = None):
        if config is None:
            config = RBIConfig()
        super().__init__(config)
        self.max_items = config.max_items

    @property
    def connector_name(self) -> str:
        return "rbi"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()

        await self._fetch_section(
            result, "press_releases", self.config.press_releases_url,
            self._parse_press_release_row,
        )
        await self._fetch_section(
            result, "notifications", self.config.notifications_url,
            self._parse_notification_row,
        )

        logger.info(f"RBIConnector fetched {len(result.items)} items")
        self.update_health(
            len(result.errors) == 0,
            str(result.errors[0][1]) if result.errors else None,
        )
        return result

    async def _fetch_section(
        self,
        result: ConnectorResult,
        section: str,
        url: str,
        row_parser,
    ) -> None:
        try:
            logger.info(f"Fetching RBI {section} from {url}")
            response = await self._get(url)
            tree = lxml_html.fromstring(response.content)
            rows = tree.xpath("//table[contains(@class, 'tablebg')]//tr")
            # Fallback: any table inside the content area
            if len(rows) < 2:
                rows = tree.xpath("//table//tr")

            count = 0
            for row in rows:
                if count >= self.max_items:
                    break
                try:
                    item = row_parser(row, section)
                    if item:
                        result.items.append(item)
                        count += 1
                except Exception as e:
                    logger.error(f"Error parsing RBI {section} row: {e}", exc_info=True)
                    result.errors.append((section, e))
        except Exception as e:
            logger.error(f"Error fetching RBI {section}: {e}", exc_info=True)
            result.errors.append((section, e))

    def _parse_press_release_row(self, row, section: str) -> IngestionItem | None:
        cells = row.xpath(".//td")
        if len(cells) < 2:
            return None

        # Cell 0: title + link
        link_tag = cells[0].xpath(".//a[@class='link2']")
        if not link_tag:
            link_tag = cells[0].xpath(".//a")
        if not link_tag:
            return None

        title = (link_tag[0].text_content() or "").strip()
        href = (link_tag[0].get("href") or "").strip()
        if not title:
            return None

        full_url = href if href.startswith("http") else f"{RBI_BASE}/scripts/{href}"

        # Cell 1 (or later): PDF link
        pdf_url = None
        for cell in cells[1:]:
            pdf_a = cell.xpath(".//a[@id]")
            if pdf_a and pdf_a[0].get("href"):
                pdf_href = pdf_a[0].get("href").strip()
                pdf_url = pdf_href if pdf_href.startswith("http") else f"{RBI_BASE}/{pdf_href.lstrip('/')}"
                break

        # Extract date from the section header row (parent context)
        date_header = row.xpath("ancestor::table//td[@class='tableheader']")
        pub_ts = None
        if date_header:
            date_text = date_header[0].text_content().strip()
            pub_ts = self._parse_date(date_text)

        metadata = {
            "section": section,
            "prid": href.split("prid=")[-1] if "prid=" in href else None,
            "pdf_url": pdf_url,
        }

        return self._build_ingestion_item(
            title=title,
            raw_content=f"Title: {title}\nDate: {date_header[0].text_content().strip() if date_header else 'Unknown'}\nPDF: {pdf_url or 'N/A'}",
            original_url=full_url,
            publisher="Reserve Bank of India",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata=metadata,
        )

    def _parse_notification_row(self, row, section: str) -> IngestionItem | None:
        cells = row.xpath(".//td")
        if len(cells) < 2:
            return None

        link_tag = cells[0].xpath(".//a")
        if not link_tag:
            return None

        title = (link_tag[0].text_content() or "").strip()
        href = (link_tag[0].get("href") or "").strip()
        if not title:
            return None

        full_url = href if href.startswith("http") else f"{RBI_BASE}/scripts/{href}"

        pdf_url = None
        for cell in cells[1:]:
            pdf_a = cell.xpath(".//a")
            if pdf_a and pdf_a[0].get("href"):
                pdf_href = pdf_a[0].get("href").strip()
                pdf_url = pdf_href if pdf_href.startswith("http") else f"{RBI_BASE}/{pdf_href.lstrip('/')}"
                break

        date_text = None
        for cell in cells:
            txt = (cell.text_content() or "").strip()
            if re.match(r"\d{1,2}\s+(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d{4}", txt, re.I):
                date_text = txt
                break

        pub_ts = self._parse_date(date_text) if date_text else None

        return self._build_ingestion_item(
            title=title,
            raw_content=f"Title: {title}\nDate: {date_text or 'Unknown'}",
            original_url=full_url,
            publisher="Reserve Bank of India",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata={
                "section": section,
                "pdf_url": pdf_url,
            },
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%b %d, %Y",
            "%d %b %Y",
            "%d-%b-%Y",
            "%d/%m/%Y",
            "%Y-%m-%d",
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
            response = await self._get(self.config.press_releases_url)
            tree = lxml_html.fromstring(response.content)
            rows = tree.xpath("//a[@class='link2']")
            count = len(rows)
            if count > 0:
                return True, f"RBI press releases accessible ({count} items)"
            return False, "RBI press release page returned no items"
        except Exception as e:
            return False, f"RBI health check failed: {e}"
