"""Tests for hybrid search endpoint."""
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.config import settings


@pytest.mark.asyncio
async def test_search_endpoint_auth_and_query():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        # 1. Test missing API Key returns 403 Forbidden
        res_no_auth = await client.get("/search?q=test")
        assert res_no_auth.status_code == 403

        # 2. Test valid API Key returns 200 list
        res_valid = await client.get(
            "/search?q=vLLM",
            headers={"X-API-Key": settings.api_secret_key},
        )
        assert res_valid.status_code == 200
        data = res_valid.json()
        assert isinstance(data, list)
