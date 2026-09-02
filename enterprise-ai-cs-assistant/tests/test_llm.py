"""Unit tests for the OpenAI-compatible LLM client. No live API calls."""

import httpx
import pytest

from app.core.config import settings
from app.llm.base import LLMError
from app.llm.factory import get_llm_client
from app.llm.openai_compatible import OpenAICompatibleClient


def _client_with_handler(handler) -> OpenAICompatibleClient:
    transport = httpx.MockTransport(handler)
    http_client = httpx.Client(transport=transport, timeout=5.0)
    return OpenAICompatibleClient(
        api_key="test-groq-key",
        model="llama-3.1-8b-instant",
        base_url="https://api.groq.com/openai/v1",
        http_client=http_client,
    )


def test_complete_returns_message_content() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        return httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"role": "assistant", "content": "  hello from groq  "}}
                ]
            },
        )

    llm = _client_with_handler(handler)
    assert llm.complete([{"role": "user", "content": "hi"}]) == "hello from groq"


def test_complete_http_error_raises_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "nope"})

    llm = _client_with_handler(handler)
    with pytest.raises(LLMError):
        llm.complete([{"role": "user", "content": "hi"}])


def test_complete_timeout_raises_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    llm = _client_with_handler(handler)
    with pytest.raises(LLMError):
        llm.complete([{"role": "user", "content": "hi"}])


def test_complete_empty_content_raises_llm_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"choices": [{"message": {"role": "assistant", "content": "  "}}]},
        )

    llm = _client_with_handler(handler)
    with pytest.raises(LLMError):
        llm.complete([{"role": "user", "content": "hi"}])


def test_factory_requires_api_key() -> None:
    original = settings.llm_api_key
    settings.llm_api_key = ""
    try:
        with pytest.raises(LLMError) as exc_info:
            get_llm_client()
        assert exc_info.value.configured is False
    finally:
        settings.llm_api_key = original
