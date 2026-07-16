from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from lxml import html

from app.modules.evidence.models import Jurisdiction
from app.modules.ingestion.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    IngestionItem,
)

logger = logging.getLogger("fios.ingestion.connectors.bse")

BSE_BASE = "https://www.bseindia.com"
BSE_ANN_HTML = f"{BSE_BASE}/corporates/ann.html"
# BSE has a JS-rendered announcements page.  The HTML page itself returns
# a shell; the actual data is loaded via XHR to api.bseindia.com.
# We attempt the JSON API first with browser-like headers, then fall
# back to the HTML page for whatever we can extract.
BSE_API = "https://api.bseindia.com/BseAnnAPI/AnnApiServlet"


class BSEConfig(ConnectorConfig):
    name: str = "bse"
    source_type: str = "api"
    base_url: str = BSE_BASE
    announcements_url: str = BSE_ANN_HTML
    api_url: str = BSE_API
    max_items: int = 50
    browser_headers: dict[str, str] = None

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if self.browser_headers is None:
            self.browser_headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Referer": "https://www.bseindia.com/corporates/ann.html",
                "Origin": "https://www.bseindia.com",
            }


class BSEConnector(BaseConnector):
    def __init__(self, config: BSEConfig | None = None):
        if config is None:
            config = BSEConfig()
        super().__init__(config)
        self.api_url = config.api_url
        self.browser_headers = config.browser_headers or {}
        self.max_items = config.max_items
        self._degraded = False

    @property
    def connector_name(self) -> str:
        return "bse"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()

        # Try JSON API first
        api_ok = await self._try_api(result)
        if api_ok and len(result.items) > 0:
            logger.info(f"BSE API returned {len(result.items)} items")
            self._degraded = False
            self.update_health(True, None)
            return result

        # Fallback: try HTML page scrape
        logger.info("BSE JSON API failed — trying HTML fallback")
        await self._try_html(result)

        if not result.items:
            logger.warning("BSE: no real items — adding MOCK placeholder")
            result.items.append(self._generate_mock_item())
            result.health_status = "degraded"
            self._degraded = True

        logger.info(f"BSEConnector fetched {len(result.items)} items (degraded={self._degraded})")
        self.update_health(
            not self._degraded,
            "All data sources failed — returning mock" if self._degraded else None,
        )
        return result

    async def _try_api(self, result: ConnectorResult) -> bool:
        try:
            # BSE JSON API endpoints (known to require specific headers)
            api_urls = [
                (f"{self.api_url}?annType=all&segment=Equity", {}),
            ]
            for url, extra_headers in api_urls:
                headers = {**self.browser_headers, **extra_headers}
                response = await self._get(url, headers=headers)
                ct = response.headers.get("content-type", "")
                if "json" in ct.lower():
                    data = response.json()
                    items = (
                        data if isinstance(data, list)
                        else data.get("data", data.get("items", []))
                    )
                    if isinstance(items, list) and items:
                        for ann in items[:self.max_items]:
                            item = self._parse_api_item(ann)
                            if item:
                                result.items.append(item)
                        return True
                # Some BSE APIs return JSONP — check for callback wrapper
                text = response.text.strip()
                if text.startswith("jQuery") or text.startswith("callback"):
                    try:
                        json_str = text[text.index("(") + 1 : text.rindex(")")]
                        data = json.loads(json_str)
                        items = data if isinstance(data, list) else data.get("data", [])
                        if isinstance(items, list) and items:
                            for ann in items[:self.max_items]:
                                item = self._parse_api_item(ann)
                                if item:
                                    result.items.append(item)
                            return True
                    except (ValueError, json.JSONDecodeError):
                        pass
            return False
        except Exception as e:
            logger.error(f"BSE API error: {e}")
            return False

    def _parse_api_item(self, ann: dict) -> IngestionItem | None:
        company = ann.get("COMPANY_NAME", ann.get("company", ann.get("symbol", ""))).strip()
        subject = ann.get("SUBJECT", ann.get("subject", ann.get("desc", ""))).strip()
        date_str = ann.get("ANNOUNCEMENT_DATE", ann.get("date", ann.get("DT", ""))).strip()
        attch = ann.get("ATTACHMENT", ann.get("attachment", ann.get("ATTACH_FILE", ""))).strip()

        if not company or not subject:
            return None

        pub_ts = self._parse_date(date_str) if date_str else None
        title = f"{company}: {subject}"

        pdf_url = None
        if attch:
            pdf_url = attch if attch.startswith("http") else f"{BSE_BASE}{attch}"

        return self._build_ingestion_item(
            title=title,
            raw_content=f"Company: {company}\nSubject: {subject}\nDate: {date_str or 'Unknown'}",
            original_url=pdf_url,
            publisher="bseindia.com",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata={
                "company": company,
                "subject": subject,
                "pdf_url": pdf_url,
                "degraded": self._degraded,
            },
        )

    async def _try_html(self, result: ConnectorResult) -> None:
        try:
            response = await self._post(
                self.announcements_url,
                data={"FromDate": "", "ToDate": "", "scrip_cd": "", "segment": "Equity"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            tree = html.fromstring(response.content)
            # The ann.html page is JS-rendered so tables may not be present.
            # Try to find any data-bearing elements.
            rows = tree.xpath("//table//tr")
            for row in rows[:self.max_items]:
                try:
                    item = self._parse_html_row(row)
                    if item:
                        result.items.append(item)
                except Exception as e:
                    logger.error(f"BSE HTML parse error: {e}")
        except Exception as e:
            logger.error(f"BSE HTML fetch error: {e}")

    def _parse_html_row(self, row) -> IngestionItem | None:
        cells = row.xpath(".//td")
        if len(cells) < 3:
            return None
        company = (cells[0].text_content() or "").strip()
        subject = (cells[1].text_content() or "").strip()
        if not company or not subject:
            return None
        date_str = (cells[2].text_content() or "").strip() if len(cells) > 2 else ""
        pub_ts = self._parse_date(date_str) if date_str else None

        pdf_url = None
        if len(cells) > 3:
            links = cells[3].xpath(".//a/@href")
            if links:
                pdf_url = links[0] if links[0].startswith("http") else f"{BSE_BASE}{links[0]}"

        return self._build_ingestion_item(
            title=f"{company}: {subject}",
            raw_content=f"Company: {company}\nSubject: {subject}\nDate: {date_str}",
            original_url=pdf_url,
            publisher="bseindia.com",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata={"company": company, "subject": subject, "pdf_url": pdf_url},
        )

    def _generate_mock_item(self) -> IngestionItem:
        return self._build_ingestion_item(
            title="[MOCK] BSE Corporate Announcement",
            raw_content=(
                "BSE JSON API unavailable. HTML fallback also failed."
                " Real data unavailable."
            ),
            original_url=None,
            publisher="bseindia.com",
            publication_ts=datetime.now(timezone.utc),
            jurisdiction=Jurisdiction.IN,
            metadata={"degraded": True, "mock": True},
            is_mock=True,
        )

    def _parse_date(self, date_str: str) -> datetime | None:
        formats = [
            "%d %b %Y", "%d-%b-%Y", "%d/%m/%Y", "%Y-%m-%d",
            "%d-%b-%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S",
        ]
        date_str = date_str.strip().replace("  ", " ")
        for fmt in formats:
            try:
                return datetime.strptime(date_str, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
        return None

    async def health_check(self) -> tuple[bool, str]:
        if self._degraded:
            return False, "BSE connector degraded — returning mock data only"
        try:
            response = await self._get(
                self.api_url,
                params={"annType": "all", "segment": "Equity"},
                headers=self.browser_headers,
            )
            if response.status_code == 200:
                ct = response.headers.get("content-type", "")
                if "json" in ct.lower():
                    return True, "BSE JSON API accessible"
                # JSONP wrapped
                text = response.text.strip()
                if text.startswith("jQuery") or text.startswith("callback"):
                    return True, "BSE JSONP API accessible"
            return False, f"BSE API returned status {response.status_code} — DEGRADED"
        except Exception as e:
            return False, f"BSE health check failed: {e} — DEGRADED"
