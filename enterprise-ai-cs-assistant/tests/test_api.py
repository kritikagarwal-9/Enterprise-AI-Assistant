"""API tests for health and authenticated /ask. LLM is faked; no live Groq calls."""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm.base import LLMError
from app.llm.factory import get_llm_client
from app.main import app

client = TestClient(app)

TEST_API_KEY = "test-local-api-key"


class FakeLLM:
    def complete(self, messages: list[dict[str, str]]) -> str:
        return "fake answer"


@pytest.fixture(autouse=True)
def set_api_auth_key() -> None:
    original = settings.api_auth_key
    settings.api_auth_key = TEST_API_KEY
    yield
    settings.api_auth_key = original


@pytest.fixture
def fake_llm() -> None:
    app.dependency_overrides[get_llm_client] = lambda: FakeLLM()
    yield
    app.dependency_overrides.pop(get_llm_client, None)


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


def test_ask_with_valid_api_key_returns_llm_answer(fake_llm: None) -> None:
    response = client.post(
        "/ask",
        json={"question": "What plans do you offer?", "customer_id": "cust_001"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["action"] == "answer"
    assert body["answer"] == "fake answer"
    assert body["sources"] == []
    assert body["ticket_id"] is None


def test_ask_when_llm_not_configured_returns_503() -> None:
    original = settings.llm_api_key
    settings.llm_api_key = ""
    app.dependency_overrides.pop(get_llm_client, None)
    try:
        response = client.post(
            "/ask",
            json={"question": "What plans do you offer?"},
            headers={"X-API-Key": TEST_API_KEY},
        )
    finally:
        settings.llm_api_key = original
    assert response.status_code == 503
    assert response.json()["detail"] == "LLM not configured"


def test_ask_when_llm_upstream_fails_returns_502() -> None:
    class FailingLLM:
        def complete(self, messages: list[dict[str, str]]) -> str:
            raise LLMError("upstream")

    app.dependency_overrides[get_llm_client] = lambda: FailingLLM()
    try:
        response = client.post(
            "/ask",
            json={"question": "What plans do you offer?"},
            headers={"X-API-Key": TEST_API_KEY},
        )
    finally:
        app.dependency_overrides.pop(get_llm_client, None)
    assert response.status_code == 502
    assert response.json()["detail"] == "Upstream LLM failed"
