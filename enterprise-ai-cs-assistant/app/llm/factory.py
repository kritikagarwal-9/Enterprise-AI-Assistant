"""Build an LLM client from settings. No FastAPI types here."""

from app.core.config import settings
from app.llm.base import LLMClient, LLMError
from app.llm.openai_compatible import OpenAICompatibleClient

PROVIDER_BASE_URLS = {
    "groq": "https://api.groq.com/openai/v1",
    "openai": "https://api.openai.com/v1",
}

DEFAULT_MODEL = "llama-3.1-8b-instant"


def get_llm_client() -> LLMClient:
    api_key = settings.llm_api_key.strip()
    if not api_key:
        raise LLMError("LLM_API_KEY is empty", configured=False)

    provider = (settings.llm_provider or "groq").strip().lower()
    base_url = (settings.llm_base_url or "").strip()
    if not base_url:
        base_url = PROVIDER_BASE_URLS.get(provider, PROVIDER_BASE_URLS["groq"])

    model = (settings.llm_model or DEFAULT_MODEL).strip() or DEFAULT_MODEL
    return OpenAICompatibleClient(
        api_key=api_key,
        model=model,
        base_url=base_url,
    )
