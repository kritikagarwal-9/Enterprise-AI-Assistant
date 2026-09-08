"""Loads settings from .env using pydantic-settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    llm_api_key: str = ""
    llm_provider: str = "groq"
    llm_model: str = "openai/gpt-oss-20b"
    llm_base_url: str = ""
    api_auth_key: str = ""
    customer_api_keys: str = ""
    chroma_path: str = "chroma_db"


settings = Settings()
