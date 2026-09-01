"""API tests for health and authenticated /ask stub."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)

TEST_API_KEY = "test-local-api-key"


@pytest.fixture(autouse=True)
def set_api_auth_key() -> None:
    original = settings.api_auth_key
    settings.api_auth_key = TEST_API_KEY
    yield
    settings.api_auth_key = original


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_ask_without_api_key_returns_401() -> None:
    response = client.post("/ask", json={"question": "What plans do you offer?"})
    assert response.status_code == 401


def test_ask_with_wrong_api_key_returns_401() -> None:
    response = client.post(
        "/ask",
        json={"question": "What plans do you offer?"},
        headers={"X-API-Key": "wrong-key"},
    )
    assert response.status_code == 401


def test_ask_with_valid_api_key_returns_stub() -> None:
    response = client.post(
        "/ask",
        json={"question": "What plans do you offer?", "customer_id": "cust_001"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "stub"
    assert "answer" in body
    assert body["sources"] == []
    assert body["ticket_id"] is None
