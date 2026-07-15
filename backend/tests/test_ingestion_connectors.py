from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.evidence.models import Jurisdiction, SourceType
from app.modules.ingestion.connectors.rbi import RBIConnector, RBIConfig
from app.modules.ingestion.connectors.sebi import SEBIConnector, SEBIConfig
from app.modules.ingestion.connectors.bse import BSEConnector, BSEConfig
from app.modules.ingestion.connectors.nse import NSEConnector, NSEConfig
from app.modules.ingestion.connectors.gdelt import GDELTConnector, GDELTConfig
from app.modules.ingestion.connectors.world_monitor import WorldMonitorConnector, WorldMonitorConfig
from app.modules.ingestion.connectors.base import ConnectorConfig


@pytest.mark.asyncio
async def test_rbi_connector_initialization():
    config = RBIConfig()
    connector = RBIConnector(config)
    assert connector.connector_name == "rbi"
    assert len(connector.rss_feeds) == 4


@pytest.mark.asyncio
async def test_sebi_connector_initialization():
    config = SEBIConfig()
    connector = SEBIConnector(config)
    assert connector.connector_name == "sebi"
    assert len(connector.rss_feeds) == 5


@pytest.mark.asyncio
async def test_bse_connector_initialization():
    config = BSEConfig()
    connector = BSEConnector(config)
    assert connector.connector_name == "bse"


@pytest.mark.asyncio
async def test_nse_connector_initialization():
    config = NSEConfig()
    connector = NSEConnector(config)
    assert connector.connector_name == "nse"


@pytest.mark.asyncio
async def test_gdelt_connector_initialization():
    config = GDELTConfig()
    connector = GDELTConnector(config)
    assert connector.connector_name == "gdelt"


@pytest.mark.asyncio
async def test_world_monitor_connector_initialization():
    config = WorldMonitorConfig()
    connector = WorldMonitorConnector(config)
    assert connector.connector_name == "world_monitor"
    assert "events" in connector.endpoints


@pytest.mark.asyncio
async def test_rbi_health_check_mock():
    config = RBIConfig()
    connector = RBIConnector(config)

    with patch.object(connector, '_get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss><channel><title>RBI</title><item><title>Test</title><link>http://test.com</link></item></channel></rss>"""
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is True
        assert "accessible" in msg


@pytest.mark.asyncio
async def test_sebi_health_check_mock():
    config = SEBIConfig()
    connector = SEBIConnector(config)

    with patch.object(connector, '_get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss><channel><title>SEBI</title><item><title>Test</title><link>http://test.com</link></item></channel></rss>"""
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is True


@pytest.mark.asyncio
async def test_nse_health_check_degraded():
    config = NSEConfig()
    connector = NSEConnector(config)

    with patch.object(connector, '_get') as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 403
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is False
        assert "DEGRADED" in msg


@pytest.mark.asyncio
async def test_gdelt_health_check_mock():
    config = GDELTConfig()
    connector = GDELTConnector(config)

    with patch.object(connector, '_get') as mock_get:
        mock_response = MagicMock()
        mock_response.text = """<?xml version="1.0"?>
        <rss><channel><title>GDELT</title><item><title>Test</title><link>http://test.com</link></item></channel></rss>"""
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is True


@pytest.mark.asyncio
async def test_world_monitor_health_check_mock():
    config = WorldMonitorConfig()
    connector = WorldMonitorConnector(config)

    with patch.object(connector, '_get') as mock_get:
        mock_response = AsyncMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is True
        assert "healthy" in msg.lower()