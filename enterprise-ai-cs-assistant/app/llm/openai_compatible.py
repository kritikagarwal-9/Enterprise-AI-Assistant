"""OpenAI-compatible chat completions client (Groq, OpenAI, and similar)."""

from __future__ import annotations

from typing import Any

import httpx

from app.llm.base import LLMError

DEFAULT_TIMEOUT_SECONDS = 30.0


class OpenAICompatibleClient:
    def __init__(
        self,
        api_key: str,
        model: str,
        base_url: str,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout
        self._http_client = http_client

    def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        client = self._http_client or httpx.Client(timeout=self._timeout)
        owns_client = self._http_client is None
        try:
            response = client.post(url, headers=headers, json=payload)
        except httpx.TimeoutException as exc:
            raise LLMError("LLM request timed out") from exc
        except httpx.HTTPError as exc:
            raise LLMError("LLM request failed") from exc
        finally:
            if owns_client:
                client.close()

        if response.status_code >= 400:
            raise LLMError("Upstream LLM failed")

        try:
            return response.json()
        except ValueError as exc:
            raise LLMError("Upstream LLM failed") from exc

    def complete(self, messages: list[dict[str, str]]) -> str:
        data = self._post({"model": self._model, "messages": messages})
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Upstream LLM failed") from exc

        if content is None or not str(content).strip():
            raise LLMError("Upstream LLM failed")
        return str(content).strip()

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        data = self._post(
            {
                "model": self._model,
                "messages": messages,
                "tools": tools,
            }
        )
        try:
            message = data["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMError("Upstream LLM failed") from exc

        if not isinstance(message, dict):
            raise LLMError("Upstream LLM failed")
        # A message must have either text content or at least one tool call.
        if not message.get("content") and not message.get("tool_calls"):
            raise LLMError("Upstream LLM failed")
        return message
