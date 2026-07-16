from __future__ import annotations

import logging
from datetime import datetime, timezone

import feedparser

from app.modules.evidence.models import Jurisdiction, SourceType
from app.modules.ingestion.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    IngestionItem,
)

logger = logging.getLogger("fios.ingestion.connectors.rbi")


class RBIConfig(ConnectorConfig):
    name: str = "rbi"
    source_type: str = "rss"
    rss_feeds: dict[str, str] = {
        "press_releases": "https://www.rbi.org.in/scripts/BS_PressReleaseDisplay.aspx?prid=all",
        "notifications": "https://www.rbi.org.in/scripts/NotificationUser.aspx?Id=12345",
        "speeches": "https://www.rbi.org.in/scripts/BS_SpeechesView.aspx?Id=12345",
        "circulars": "https://www.rbi.org.in/scripts/BS_CircularIndexDisplay.aspx?Id=12345",
    }
    max_items_per_feed: int = 50


class RBIConnector(BaseConnector):
    def __init__(self, config: RBIConfig | None = None):
        if config is None:
            config = RBIConfig()
        super().__init__(config)
        self.rss_feeds = config.rss_feeds
        self.max_items = config.max_items_per_feed

    @property
    def connector_name(self) -> str:
        return "rbi"

    async def fetch(self) -> ConnectorResult:
        result = ConnectorResult()
        for feed_name, feed_url in self.rss_feeds.items():
            try:
                logger.info(f"Fetching RBI feed: {feed_name} from {feed_url}")
                response = await self._get(feed_url)
                feed = feedparser.parse(response.text)

                if feed.bozo and feed.bozo_exception:
                    logger.warning(f"RBI feed {feed_name} parse warning: {feed.bozo_exception}")

                for entry in feed.entries[:self.max_items]:
                    try:
                        item = self._parse_entry(entry, feed_name)
                        if item:
                            result.items.append(item)
                    except Exception as e:
                        logger.error(f"Error parsing RBI entry: {e}", exc_info=True)
                        result.errors.append((feed_name, e))
            except Exception as e:
                logger.error(f"Error fetching RBI feed {feed_name}: {e}", exc_info=True)
                result.errors.append((feed_name, e))

        logger.info(f"RBIConnector fetched {len(result.items)} items")
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

        jurisdiction = Jurisdiction.IN
        source_type = SourceType.RSS

        extra_meta = {
            "feed_name": feed_name,
            "feed_url": self.rss_feeds.get(feed_name, ""),
            "tags": [tag.get("term", "") for tag in entry.get("tags", [])],
            "author": entry.get("author", ""),
        }

        return self._build_ingestion_item(
            title=title,
            raw_content=f"{title}\n\n{content}",
            original_url=link or None,
            publisher="Reserve Bank of India",
            publication_ts=pub_ts,
            jurisdiction=jurisdiction,
            metadata=extra_meta,
        )

    def _categorize(self, title: str, content: str) -> str:
        text = f"{title} {content}".lower()
        if any(kw in text for kw in ["monetary policy", "repo rate", "reverse repo", "crr", "slr"]):
            return "monetary_policy"
        if any(kw in text for kw in ["circular", "direction", "guidelines", "master direction"]):
            return "regulation"
        if any(kw in text for kw in ["speech", "address", "remarks", "governor", "deputy governor"]):
            return "speech"
        if any(kw in text for kw in ["notification", "press release", "statement"]):
            return "notification"
        return "general"

    async def health_check(self) -> tuple[bool, str]:
        try:
            feed_url = next(iter(self.rss_feeds.values()))
            response = await self._get(feed_url)
            feed = feedparser.parse(response.text)
            if feed.bozo and feed.bozo_exception:
                return False, f"RSS parse error: {feed.bozo_exception}"
            return True, f"RBI RSS feeds accessible ({len(feed.entries)} entries in sample)"
        except Exception as e:
            return False, f"RBI health check failed: {e}"
