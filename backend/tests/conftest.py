"""Pytest configuration and test fixtures."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.core.database import engine


@pytest_asyncio.fixture
async def async_client():
    """Async test client fixture."""
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        yield client
    await engine.dispose()
