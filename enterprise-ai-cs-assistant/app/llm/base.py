"""Provider-agnostic LLM types."""

from typing import Protocol


class LLMError(Exception):
    """Raised when the model cannot be called or returns nothing usable."""

    def __init__(self, message: str, *, configured: bool = True) -> None:
        super().__init__(message)
        self.configured = configured


class LLMClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str:
        """Return assistant text for a chat-completions style message list."""
