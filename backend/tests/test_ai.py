from __future__ import annotations

import pytest

from app.config import Settings


@pytest.mark.asyncio
async def test_ai_router_has_adapters(settings: Settings):
    from app.ai.router import _get_adapters

    adapters = _get_adapters()
    assert len(adapters) > 0


@pytest.mark.asyncio
async def test_ai_router_dev_mode(settings: Settings):
    from app.ai.router import _get_adapters

    adapters = _get_adapters()
    assert len(adapters) == 2
    assert adapters[0].adapter_name == "nvidia_nim"
    assert adapters[1].adapter_name == "openrouter"


@pytest.mark.asyncio
async def test_ai_router_customer_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("DEPLOYMENT_MODE", "customer")
    # Force re-evaluation
    from app.config import get_settings
    get_settings.cache_clear()
    from app.ai.router import _get_adapters

    adapters = _get_adapters()
    assert len(adapters) == 1
    assert adapters[0].adapter_name == "vllm"
