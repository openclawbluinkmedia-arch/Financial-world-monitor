from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import httpx
import pytest

from app.modules.evidence.models import Jurisdiction, SourceType
from app.modules.ingestion.connectors.base import (
    BaseConnector,
    ConnectorConfig,
    ConnectorResult,
    IngestionItem,
)
from app.modules.ingestion.connectors.bse import BSEConfig, BSEConnector
from app.modules.ingestion.connectors.gdelt import GDELTConfig, GDELTConnector
from app.modules.ingestion.connectors.nse import NSEConfig, NSEConnector
from app.modules.ingestion.connectors.rbi import RBIConfig, RBIConnector
from app.modules.ingestion.connectors.sebi import SEBIConfig, SEBIConnector
from app.modules.ingestion.connectors.world_monitor import WorldMonitorConfig, WorldMonitorConnector


class MockConnector(BaseConnector):
    @property
    def connector_name(self) -> str:
        return "mock"

    async def fetch(self):
        return ConnectorResult(items=[
            IngestionItem(
                source_id=uuid.uuid4(),
                source_name="Test",
                original_url="http://test.com/1",
                publisher="Test Publisher",
                title="Test Item",
                raw_content="Test content",
                publication_ts=datetime.now(timezone.utc),
                jurisdiction=Jurisdiction.IN,
                source_type=SourceType.RSS,
            )
        ])

    async def health_check(self):
        return True, "OK"


@pytest.mark.asyncio
async def test_base_connector_content_hash():
    item = IngestionItem(
        source_id=uuid.uuid4(),
        source_name="Test",
        original_url="http://test.com",
        publisher="Test",
        title="Test",
        raw_content="Hello World",
        publication_ts=datetime.now(timezone.utc),
        jurisdiction=Jurisdiction.IN,
        source_type=SourceType.RSS,
    )
    assert len(item.content_hash) == 64
    assert item.near_dup_hash is not None


@pytest.mark.asyncio
async def test_content_hash_deterministic():
    item1 = IngestionItem(
        source_id=uuid.uuid4(),
        source_name="Test",
        original_url="http://test.com",
        publisher="Test",
        title="Test",
        raw_content="Same content",
        publication_ts=datetime.now(timezone.utc),
        jurisdiction=Jurisdiction.IN,
        source_type=SourceType.RSS,
    )
    item2 = IngestionItem(
        source_id=uuid.uuid4(),
        source_name="Test",
        original_url="http://test.com",
        publisher="Test",
        title="Test",
        raw_content="Same content",
        publication_ts=datetime.now(timezone.utc),
        jurisdiction=Jurisdiction.IN,
        source_type=SourceType.RSS,
    )
    assert item1.content_hash == item2.content_hash


@pytest.mark.asyncio
async def test_near_dup_hash():
    item1 = IngestionItem(
        source_id=uuid.uuid4(),
        source_name="Test",
        original_url="http://test.com",
        publisher="Test",
        title="Test",
        raw_content="The quick brown fox jumps over the lazy dog",
        publication_ts=datetime.now(timezone.utc),
        jurisdiction=Jurisdiction.IN,
        source_type=SourceType.RSS,
    )
    item2 = IngestionItem(
        source_id=uuid.uuid4(),
        source_name="Test",
        original_url="http://test.com",
        publisher="Test",
        title="Test",
        raw_content="The quick brown fox jumps over the lazy dog.",
        publication_ts=datetime.now(timezone.utc),
        jurisdiction=Jurisdiction.IN,
        source_type=SourceType.RSS,
    )
    assert item1.near_dup_hash == item2.near_dup_hash


@pytest.mark.asyncio
async def test_rbi_connector_init():
    config = RBIConfig()
    connector = RBIConnector(config)
    assert connector.connector_name == "rbi"
    assert "press_releases" in connector.rss_feeds


@pytest.mark.asyncio
async def test_sebi_connector_init():
    config = SEBIConfig()
    connector = SEBIConnector(config)
    assert connector.connector_name == "sebi"
    assert "circulars" in connector.rss_feeds


@pytest.mark.asyncio
async def test_bse_connector_init():
    config = BSEConfig()
    connector = BSEConnector(config)
    assert connector.connector_name == "bse"


@pytest.mark.asyncio
async def test_nse_connector_degraded_mode():
    config = NSEConfig()
    connector = NSEConnector(config)
    assert connector.connector_name == "nse"
    mock_item = connector._generate_mock_item()
    assert mock_item.is_mock is True
    assert "MOCK" in mock_item.title


@pytest.mark.asyncio
async def test_gdelt_connector_init():
    config = GDELTConfig()
    connector = GDELTConnector(config)
    assert connector.connector_name == "gdelt"
    assert connector.query == "finance OR banking OR economy OR market OR stock OR trade"
    assert connector.max_records == 250


@pytest.mark.asyncio
async def test_world_monitor_connector_init():
    config = WorldMonitorConfig()
    connector = WorldMonitorConnector(config)
    assert connector.connector_name == "world_monitor"
    assert "events" in connector.endpoints


@pytest.mark.asyncio
async def test_evidence_id_generation():
    connector = MockConnector(ConnectorConfig(name="test", source_type="rss"))
    eid1 = connector._make_evidence_id("SourceA", "http://url.com", "Title")
    eid2 = connector._make_evidence_id("SourceA", "http://url.com", "Title")
    eid3 = connector._make_evidence_id("SourceA", "http://url.com", "Different")
    assert eid1 == eid2
    assert eid1 != eid3
    assert len(eid1) == 32


@pytest.mark.asyncio
async def test_connector_health_tracking():
    connector = MockConnector(ConnectorConfig(name="test", source_type="rss"))
    assert connector._consecutive_failures == 0
    assert connector.get_health_status()["status"] == "healthy"

    connector.update_health(False, "Error 1")
    assert connector._consecutive_failures == 1
    assert connector.get_health_status()["status"] == "degraded"

    connector.update_health(False, "Error 2")
    assert connector._consecutive_failures == 2
    assert connector.get_health_status()["status"] == "degraded"

    connector.update_health(False, "Error 3")
    assert connector._consecutive_failures == 3
    assert connector.get_health_status()["status"] == "failed"

    connector.update_health(True, None)
    assert connector._consecutive_failures == 0
    assert connector.get_health_status()["status"] == "healthy"


@pytest.mark.asyncio
async def test_retry_backoff():
    config = ConnectorConfig(name="test", source_type="rss", retry_attempts=3, retry_base_delay=0.01)
    connector = MockConnector(config)
    call_count = 0

    async def failing_request(method: str, url: str, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.RequestError("Network error")

    # Patch the underlying client instead of the retry-wrapped method
    original_client = connector._client
    mock_client = AsyncMock()
    mock_client.request = failing_request
    connector._client = mock_client

    try:
        async with connector:
            await connector._get("http://test.com")
    except Exception:
        pass

    connector._client = original_client
    assert call_count == 3
