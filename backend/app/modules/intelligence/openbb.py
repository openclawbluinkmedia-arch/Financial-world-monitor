from __future__ import annotations

import logging
from typing import Any

import httpx

from app.config import get_settings

logger = logging.getLogger("fios.intelligence.openbb")


class OpenBBClient:
    """
    Client for OpenBB Platform API.
    OpenBB runs as a separate AGPLv3 service; FIOS communicates via REST/MCP only.
    """

    def __init__(self):
        settings = get_settings()
        self.base_url = getattr(settings, 'OPENBB_BASE_URL', 'http://openbb:8000')
        self.api_key = getattr(settings, 'OPENBB_API_KEY', '')
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        self._client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(30.0),
            headers={"Authorization": f"Bearer {self.api_key}"} if self.api_key else {},
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()

    async def get_security_master(self) -> list[dict[str, Any]]:
        """
        Fetch security master from OpenBB.
        Expected response: list of {symbol, name, exchange, sector, industry, ...}
        """
        if not self._client:
            raise RuntimeError("OpenBBClient not initialized. Use async context manager.")

        try:
            response = await self._client.get("/api/v1/securities/master")
            response.raise_for_status()
            data = response.json()
            return data.get("securities", [])
        except Exception as e:
            logger.error(f"OpenBB security master fetch failed: {e}")
            return []

    async def get_company_fundamentals(self, symbol: str, exchange: str = "NSE") -> dict[str, Any] | None:
        """Get company fundamentals from OpenBB"""
        if not self._client:
            raise RuntimeError("OpenBBClient not initialized. Use async context manager.")

        try:
            response = await self._client.get(
                f"/api/v1/equity/fundamentals/{symbol}",
                params={"exchange": exchange}
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"OpenBB fundamentals fetch failed for {symbol}: {e}")
            return None

    async def search_securities(self, query: str) -> list[dict[str, Any]]:
        """Search securities in OpenBB"""
        if not self._client:
            raise RuntimeError("OpenBBClient not initialized. Use async context manager.")

        try:
            response = await self._client.get(
                "/api/v1/securities/search",
                params={"q": query}
            )
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            logger.warning(f"OpenBB search failed for {query}: {e}")
            return []

    async def get_sector_performance(self, sector: str) -> dict[str, Any] | None:
        """Get sector performance data"""
        if not self._client:
            raise RuntimeError("OpenBBClient not initialized. Use async context manager.")

        try:
            response = await self._client.get(
                f"/api/v1/sector/performance/{sector}"
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.warning(f"OpenBB sector performance failed for {sector}: {e}")
            return None