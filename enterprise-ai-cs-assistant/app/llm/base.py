"""Provider-agnostic LLM types."""

from typing import Any, Protocol


class LLMError(Exception):
    """Raised when the model cannot be called or returns nothing usable."""

    def __init__(self, message: str, *, configured: bool = True) -> None:
        super().__init__(message)
        self.configured = configured


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return assistant text for a chat-completions style message list."""

    def complete_with_tools(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Return the raw assistant message (role/content/tool_calls) so the
        caller can execute any requested tool calls itself. Used by the
        orchestrator, not by simple single-turn callers.
        """
