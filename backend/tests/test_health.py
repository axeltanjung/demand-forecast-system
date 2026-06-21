# Health and smoke tests for the FastAPI backend
# Co-authored with CoCo
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def test_health(client):
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"


async def test_skus(client):
    response = await client.get("/skus")
    assert response.status_code == 200
    data = response.json()
    assert "skus" in data
    assert isinstance(data["skus"], list)
