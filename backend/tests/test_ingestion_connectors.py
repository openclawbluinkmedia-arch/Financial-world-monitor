from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.modules.ingestion.connectors.bse import BSEConfig, BSEConnector
from app.modules.ingestion.connectors.gdelt import GDELTConfig, GDELTConnector
from app.modules.ingestion.connectors.nse import NSEConfig, NSEConnector
from app.modules.ingestion.connectors.rbi import RBIConfig, RBIConnector
from app.modules.ingestion.connectors.sebi import SEBIConfig, SEBIConnector
from app.modules.ingestion.connectors.world_monitor import WorldMonitorConfig, WorldMonitorConnector


@pytest.mark.asyncio
async def test_rbi_connector_initialization():
    config = RBIConfig()
    connector = RBIConnector(config)
    assert connector.connector_name == "rbi"


@pytest.mark.asyncio
async def test_sebi_connector_initialization():
    config = SEBIConfig()
    connector = SEBIConnector(config)
    assert connector.connector_name == "sebi"
    assert connector.config.sitemap_url == "https://www.sebi.gov.in/sitemap.xml"


@pytest.mark.asyncio
async def test_bse_connector_initialization():
    config = BSEConfig()
    connector = BSEConnector(config)
    assert connector.connector_name == "bse"
    assert "api.bseindia.com" in connector.api_url


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
        mock_response.content = b"""<html><body>
        <table class="tablebg"><tr><th>Title</th></tr>
        <tr><td><a class="link2" href="test.aspx">Test Press Release</a></td></tr>
        </table></body></html>"""
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is True
        assert "RBI" in msg


@pytest.mark.asyncio
async def test_sebi_health_check_mock():
    config = SEBIConfig()
    connector = SEBIConnector(config)

    with patch.object(connector, '_get') as mock_get:
        mock_response = MagicMock()
        mock_response.headers = {"content-type": "application/xml"}
        mock_response.text = """<?xml version="1.0"?>
        <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
        <url><loc>https://www.sebi.gov.in/circular.html</loc></url>
        </urlset>"""
        mock_response.content = mock_response.text.encode()
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is True


@pytest.mark.asyncio
async def test_nse_health_check_degraded():
    config = NSEConfig()
    connector = NSEConnector(config)

    with patch.object(connector, '_get') as mock_get:
        # First call: session priming succeeds
        priming_resp = MagicMock()
        priming_resp.status_code = 200
        priming_resp.raise_for_status = MagicMock()
        # Second call: API returns 403
        api_resp = MagicMock()
        api_resp.status_code = 403
        mock_get.side_effect = [priming_resp, api_resp]

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
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "healthy"}
        mock_get.return_value = mock_response

        healthy, msg = await connector.health_check()
        assert healthy is True
        assert "healthy" in msg.lower()
