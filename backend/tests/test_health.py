"""Test root and health check endpoints."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Test GET / returns API metadata."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "FixMyCampus AI"
    assert data["status"] == "running"
    assert "api_v1" in data


@pytest.mark.asyncio
async def test_health_endpoint_root(async_client: AsyncClient):
    """Test GET /health returns application status."""
    response = await async_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data
    assert "database" in data
    assert data["ai_subsystem"] == "not_configured"


@pytest.mark.asyncio
async def test_health_endpoint_v1(async_client: AsyncClient):
    """Test GET /api/v1/health returns application status."""
    response = await async_client.get("/api/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data
    assert "environment" in data
