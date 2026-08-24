"""
Application configuration via pydantic-settings.
All config values from environment variables with sensible defaults.
"""

import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # LLM Provider
    llm_provider: str = "ollama"  # "anthropic", "ollama", or "groq"

    # Anthropic
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-20250514"

    # Groq
    groq_api_key: Optional[str] = None
    groq_model: str = "llama3-70b-8192"

    # Ollama
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "llama3.1:8b"
    ollama_embed_model: str = "nomic-embed-text"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/lenny"
    database_url_sync: str = "postgresql://postgres:postgres@localhost:5432/lenny"

    # Backend
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000

    # Frontend
    backend_url: str = "http://localhost:8000"

    # Retrieval
    retrieval_top_k: int = 5
    embedding_dim: int = 768

    # Logging
    log_level: str = "INFO"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
