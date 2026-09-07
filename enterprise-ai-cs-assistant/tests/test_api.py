"""API tests for health and authenticated /ask. LLM and RAG are faked.

These test the HTTP layer end to end (auth, error mapping, request/response
shape). The orchestrator's own decision logic (tool calling, escalation,
refusal) is covered in tests/test_orchestrator.py, so the fakes here just
need to exercise a plain answer, a failure, and an unconfigured LLM.
"""

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.llm.base import LLMError
from app.llm.factory import get_llm_client
from app.main import app

client = TestClient(app)

TEST_API_KEY = "test-local-api-key"


class FakeLLM:
    """No tool calls, just a direct final answer."""

    def complete(self, messages: list[dict[str, str]]) -> str:  # pragma: no cover
        raise AssertionError("orchestrator should use complete_with_tools")

    def complete_with_tools(self, messages, tools) -> dict:
        return {"role": "assistant", "content": "fake answer", "tool_calls": []}


class FailingLLM:
    def complete(self, messages: list[dict[str, str]]) -> str:  # pragma: no cover
        raise AssertionError("orchestrator should use complete_with_tools")

    def complete_with_tools(self, messages, tools) -> dict:
        raise LLMError("upstream")


@pytest.fixture(autouse=True)
def set_api_auth_key() -> None:
    original = settings.api_auth_key
    settings.api_auth_key = TEST_API_KEY
    yield
    settings.api_auth_key = original


@pytest.fixture(autouse=True)
def mock_retrieve(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.agent.orchestrator.retrieve", lambda question, n_results=4: [])


@pytest.fixture
def fake_llm():
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


def test_ask_passes_retrieved_context_to_llm(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    hits = [
        {"text": "Starter is $29 per month.", "source": "plans.md", "distance": 0.1},
        {"text": "Pro includes 25 seats.", "source": "plans.md", "distance": 0.2},
        {"text": "Boards hold tasks.", "source": "product-overview.md", "distance": 0.3},
    ]
    monkeypatch.setattr("app.agent.orchestrator.retrieve", lambda question, n_results=4: hits,)

    class RecordingLLM:
        def __init__(self) -> None:
            self.messages = None

        def complete(self, messages):  # pragma: no cover
            raise AssertionError("orchestrator should use complete_with_tools")

        def complete_with_tools(self, messages, tools):
            self.messages = messages
            return {"role": "assistant", "content": "grounded answer", "tool_calls": []}

    recorder = RecordingLLM()
    app.dependency_overrides[get_llm_client] = lambda: recorder
    try:
        response = client.post(
            "/ask",
            json={"question": "What plans do you offer?"},
            headers={"X-API-Key": TEST_API_KEY},
        )
    finally:
        app.dependency_overrides.pop(get_llm_client, None)

    assert response.status_code == 200
    body = response.json()
    assert body["answer"] == "grounded answer"
    assert body["sources"] == ["plans.md", "product-overview.md"]
    assert recorder.messages is not None
    user_content = recorder.messages[1]["content"]
    assert "Starter is $29 per month." in user_content
    assert "Pro includes 25 seats." in user_content
    assert "What plans do you offer?" in user_content
    assert "plans.md" in user_content


def test_ask_with_no_retrieval_results_still_calls_llm(fake_llm: None) -> None:
    response = client.post(
        "/ask",
        json={"question": "What is the capital of France?"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["sources"] == []
    assert body["action"] == "answer"


def test_ask_with_whitespace_only_question_returns_422() -> None:
    response = client.post(
        "/ask",
        json={"question": "   "},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 422


def test_ask_when_orchestrator_raises_unexpected_error_returns_clean_500(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _boom(question, llm, customer_id=None):
        raise RuntimeError("something unexpected broke")

    monkeypatch.setattr("app.api.routes.handle_question", _boom)

    # Starlette's ServerErrorMiddleware re-raises the original exception
    # after sending the handler's response (so an ASGI server can still log
    # it) -- the default TestClient would surface that as a raised
    # exception in the test instead of a response. Real deployments still
    # receive the clean 500 JSON before that re-raise happens; this client
    # is configured to observe that response the same way a real client
    # would.
    no_raise_client = TestClient(app, raise_server_exceptions=False)
    response = no_raise_client.post(
        "/ask",
        json={"question": "What plans do you offer?"},
        headers={"X-API-Key": TEST_API_KEY},
    )
    assert response.status_code == 500
    assert response.json() == {"detail": "Internal server error"}
