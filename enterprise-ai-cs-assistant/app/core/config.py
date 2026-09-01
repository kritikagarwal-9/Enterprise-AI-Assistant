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
    api_auth_key: str = ""
    chroma_path: str = "chroma_db"


settings = Settings()
