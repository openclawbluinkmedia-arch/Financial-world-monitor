from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from urllib.parse import urljoin

from lxml import html as lxml_html

from app.modules.evidence.models import Jurisdiction
from app.modules.ingestion.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    IngestionItem,
)

logger = logging.getLogger("fios.ingestion.connectors.sebi")

SEBI_BASE = "https://www.sebi.gov.in"
SITEMAP_URL = f"{SEBI_BASE}/sitemap.xml"
# These RSS endpoints are confirmed dead (404).  We keep them for reference
# but the connector will fall back to sitemap-based discovery.
DEAD_RSS_FEEDS = {
    "circulars": f"{SEBI_BASE}/sebiweb/rss/rss_circulars.xml",
    "press_releases": f"{SEBI_BASE}/sebiweb/rss/rss_pressreleases.xml",
    "orders": f"{SEBI_BASE}/sebiweb/rss/rss_orders.xml",
    "legal": f"{SEBI_BASE}/sebiweb/rss/rss_legal.xml",
    "news": f"{SEBI_BASE}/sebiweb/rss/rss_news.xml",
}


class SEBIConfig(ConnectorConfig):
    name: str = "sebi"
    source_type: str = "scraper"
    base_url: str = SEBI_BASE
    sitemap_url: str = SITEMAP_URL
    max_items: int = 50


class SEBIConnector(BaseConnector):
    def __init__(self, config: SEBIConfig | None = None):
        if config is None:
            config = SEBIConfig()
        super().__init__(config)
        self.max_items = config.max_items
        self._sitemap_available = False

    @property
    def connector_name(self) -> str:
        return "sebi"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()

        try:
            await self._fetch_from_sitemap(result)
        except Exception as e:
            logger.error(f"SEBI sitemap fetch failed: {e}")
            result.errors.append(("sitemap", e))

        if not result.items:
            logger.warning("SEBI: no real items fetched — adding MOCK placeholder")
            result.items.append(self._generate_mock_item())
            result.health_status = "degraded"

        logger.info(
            f"SEBIConnector fetched {len(result.items)} items "
            f"(degraded={not self._sitemap_available})"
        )
        self.update_health(
            self._sitemap_available,
            "Sitemap unavailable — returning mock data" if not self._sitemap_available else None,
        )
        return result

    async def _fetch_from_sitemap(self, result: ConnectorResult) -> None:
        logger.info(f"Fetching SEBI sitemap from {self.config.sitemap_url}")
        response = await self._get(self.config.sitemap_url)
        content_type = response.headers.get("content-type", "")

        if "xml" not in content_type.lower() and not response.text.strip().startswith("<?xml"):
            logger.warning("SEBI sitemap did not return XML — cannot parse")
            return

        # Extract URLs from sitemap
        tree = lxml_html.fromstring(response.content)
        # Sitemap uses <loc> tags
        all_urls = tree.xpath("//ns:loc/text() | //loc/text()",
                              namespaces={"ns": "http://www.sitemaps.org/schemas/sitemap/0.9"})
        if not all_urls:
            all_urls = re.findall(r"<loc>(.*?)</loc>", response.text)

        logger.info(f"SEBI sitemap contains {len(all_urls)} URLs")

        # Filter for circulars / press-releases / orders
        relevant = [
            u for u in all_urls
            if any(kw in u.lower() for kw in
                   ["circular", "press-release", "order", "legal", "notification"])
        ]
        logger.info(f"Filtered to {len(relevant)} relevant SEBI document URLs")

        if not relevant:
            self._sitemap_available = False
            logger.warning("No relevant SEBI document URLs found in sitemap")
            return

        self._sitemap_available = True

        count = 0
        for url in relevant[:self.max_items]:
            try:
                item = await self._fetch_document_page(url)
                if item:
                    result.items.append(item)
                    count += 1
            except Exception as e:
                logger.error(f"Error fetching SEBI document {url}: {e}")
                result.errors.append(("fetch_page", e))

    async def _fetch_document_page(self, url: str) -> IngestionItem | None:
        try:
            response = await self._get(url)
        except Exception:
            return None

        tree = lxml_html.fromstring(response.content)

        # Extract title
        title_tag = tree.xpath("//h1/text() | //title/text()")
        title = (title_tag[0] if title_tag else "Untitled").strip()
        if not title or title == "Untitled":
            return None

        # Extract date
        date_str = None
        date_el = tree.xpath(
            "//*[contains(@class, 'date')]/text()"
            " | //*[contains(@class, 'Date')]/text()"
            " | //time/@datetime"
        )
        if date_el:
            date_str = date_el[0].strip()
        pub_ts = self._parse_date(date_str) if date_str else None

        # Extract body text
        body_el = tree.xpath("//div[contains(@class, 'content')] | //article | //main")
        body = ""
        if body_el:
            body = (body_el[0].text_content() or "").strip()[:2000]

        # Extract PDF links
        pdf_links = tree.xpath("//a[contains(@href, '.pdf')]/@href")
        pdf_url = urljoin(url, pdf_links[0]) if pdf_links else None

        # Determine category from URL
        cat = "general"
        if "circular" in url.lower():
            cat = "circular"
        elif "press-release" in url.lower():
            cat = "press_release"
        elif "order" in url.lower():
            cat = "order"
        elif "legal" in url.lower():
            cat = "legal"

        return self._build_ingestion_item(
            title=title,
            raw_content=(
                f"Title: {title}\nDate: {date_str or 'Unknown'}"
                f"\nCategory: {cat}\n{body[:1000]}"
            ),
            original_url=url,
            publisher="sebi.gov.in",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata={
                "category": cat,
                "pdf_url": pdf_url,
                "source": "sitemap",
            },
        )

    def _generate_mock_item(self) -> IngestionItem:
        return self._build_ingestion_item(
            title="[MOCK] SEBI document — RSS feeds unavailable, sitemap fallback failed",
            raw_content=(
                "SEBI RSS feeds are returning 404. Sitemap-based document"
                " discovery also failed. Real data unavailable."
            ),
            original_url=None,
            publisher="sebi.gov.in",
            publication_ts=datetime.now(timezone.utc),
            jurisdiction=Jurisdiction.IN,
            metadata={"degraded": True, "mock": True},
            is_mock=True,
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%d %b %Y",
            "%Y-%m-%d",
            "%d-%b-%Y",
            "%d/%m/%Y",
            "%b %d, %Y",
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
            response = await self._get(self.config.sitemap_url)
            ct = response.headers.get("content-type", "").lower()
            if "xml" in ct or response.text.strip().startswith("<?xml"):
                locs = re.findall(r"<loc>(.*?)</loc>", response.text)
                doc_count = sum(
                    1 for u in locs
                    if "circular" in u.lower() or "press-release" in u.lower()
                )
                return True, (
                    f"SEBI sitemap accessible ({len(locs)} URLs,"
                    f" {doc_count} documents)"
                )
            return False, "SEBI sitemap returned non-XML content — DEGRADED"
        except Exception as e:
            return False, f"SEBI health check failed: {e} — DEGRADED"
