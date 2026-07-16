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

logger = logging.getLogger("fios.ingestion.connectors.sebi")


class SEBIConfig(ConnectorConfig):
    name: str = "sebi"
    source_type: str = "rss"
    rss_feeds: dict[str, str] = {
        "circulars": "https://www.sebi.gov.in/sebiweb/rss/rss_circulars.xml",
        "press_releases": "https://www.sebi.gov.in/sebiweb/rss/rss_pressreleases.xml",
        "orders": "https://www.sebi.gov.in/sebiweb/rss/rss_orders.xml",
        "legal": "https://www.sebi.gov.in/sebiweb/rss/rss_legal.xml",
        "news": "https://www.sebi.gov.in/sebiweb/rss/rss_news.xml",
    }
    max_items_per_feed: int = 50


class SEBIConnector(BaseConnector):
    def __init__(self, config: SEBIConfig | None = None):
        if config is None:
            config = SEBIConfig()
        super().__init__(config)
        self.rss_feeds = config.rss_feeds
        self.max_items = config.max_items_per_feed

    @property
    def connector_name(self) -> str:
        return "sebi"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()
        for feed_name, feed_url in self.rss_feeds.items():
            try:
                logger.info(f"Fetching SEBI feed: {feed_name} from {feed_url}")
                response = await self._get(feed_url)
                feed = feedparser.parse(response.text)

                if feed.bozo and feed.bozo_exception:
                    logger.warning(f"SEBI feed {feed_name} parse warning: {feed.bozo_exception}")

                for entry in feed.entries[:self.max_items]:
                    try:
                        item = self._parse_entry(entry, feed_name)
                        if item:
                            result.items.append(item)
                    except Exception as e:
                        logger.error(f"Error parsing SEBI entry: {e}", exc_info=True)
                        result.errors.append((feed_name, e))
            except Exception as e:
                logger.error(f"Error fetching SEBI feed {feed_name}: {e}", exc_info=True)
                result.errors.append((feed_name, e))

        logger.info(f"SEBIConnector fetched {len(result.items)} items")
        self.update_health(len(result.errors) == 0, str(result.errors[0][1]) if result.errors else None)
        return result

    def _parse_entry(self, entry: dict, feed_name: str) -> IngestionItem | None:
        title = entry.get("title", "").strip()
        if not title:
            return None

        link = entry.get("link", "").strip()
        content = entry.get("summary", entry.get("description", ""))
        published = entry.get("published_parsed") or entry.get("updated_parsed")

        pub_ts = None
        if published:
            try:
                pub_ts = datetime(*published[:6], tzinfo=timezone.utc)
            except Exception:
                pass

        return self._build_ingestion_item(
            title=title,
            raw_content=f"{title}\n\n{content}",
            original_url=link or None,
            publisher="sebi.gov.in",
            publication_ts=pub_ts,
            jurisdiction=Jurisdiction.IN,
            metadata={
                "feed_name": feed_name,
                "feed_url": self.rss_feeds.get(feed_name),
                "tags": [tag.get("term", "") for tag in entry.get("tags", [])],
                "author": entry.get("author", ""),
            },
        )

    async def health_check(self) -> tuple[bool, str]:
        try:
            feed_url = next(iter(self.rss_feeds.values()))
            response = await self._get(feed_url)
            feed = feedparser.parse(response.text)
            if feed.bozo and feed.bozo_exception:
                return False, f"RSS parse error: {feed.bozo_exception}"
            return True, f"SEBI RSS feeds accessible ({len(feed.entries)} entries in sample)"
        except Exception as e:
            return False, f"SEBI health check failed: {e}"
