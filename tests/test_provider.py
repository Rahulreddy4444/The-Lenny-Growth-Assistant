"""
Tests for provider routing — verifies the provider swap mechanism.
"""

import pytest
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestProviderConfig:
    """Test LLM provider configuration and factory."""

    def test_ollama_provider_creation(self):
        from backend.app.services.llm import OllamaProvider
        provider = OllamaProvider(
            base_url="http://localhost:11434",
            chat_model="llama3.1:8b",
            embed_model="nomic-embed-text",
        )
        assert provider.chat_model == "llama3.1:8b"
        assert provider.embed_model == "nomic-embed-text"

    def test_anthropic_provider_requires_key(self):
        from backend.app.services.llm import get_chat_provider
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.llm_provider = "anthropic"
        settings.anthropic_api_key = None

        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY is required"):
            get_chat_provider(settings)

    def test_unknown_provider_raises(self):
        from backend.app.services.llm import get_chat_provider
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.llm_provider = "invalid"

        with pytest.raises(ValueError, match="Unknown LLM provider"):
            get_chat_provider(settings)

    def test_ollama_factory(self):
        from backend.app.services.llm import get_chat_provider, OllamaProvider
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.llm_provider = "ollama"
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_chat_model = "llama3.1:8b"
        settings.ollama_embed_model = "nomic-embed-text"

        provider = get_chat_provider(settings)
        assert isinstance(provider, OllamaProvider)

    def test_embedding_service_creation(self):
        from backend.app.services.llm import get_embedding_service
        from unittest.mock import MagicMock

        settings = MagicMock()
        settings.ollama_base_url = "http://localhost:11434"
        settings.ollama_embed_model = "nomic-embed-text"

        service = get_embedding_service(settings)
        assert service is not None


class TestEssaySkill:
    """Test Ship 30 for 30 essay tool definition."""

    def test_essay_tool_definition(self):
        from backend.app.services.essay import get_essay_tool_definition
        tool_def = get_essay_tool_definition()

        assert tool_def["name"] == "generate_ship30_essay"
        assert "input_schema" in tool_def
        assert "topic" in tool_def["input_schema"]["properties"]
        assert "grounded_content" in tool_def["input_schema"]["properties"]

    def test_essay_prompt_building(self):
        from backend.app.services.essay import build_essay_prompt
        prompt = build_essay_prompt(
            topic="Product-market fit",
            grounded_content="Brian Chesky says...",
            sources=[{"episode_title": "Test", "guest": "Brian", "content_preview": "..."}],
        )
        assert "Product-market fit" in prompt
        assert "Brian Chesky says" in prompt
        assert "Test" in prompt


class TestSearchTool:
    """Test search tool definition."""

    def test_search_tool_definition(self):
        from backend.app.services.agent import get_search_tool_definition
        tool_def = get_search_tool_definition()

        assert tool_def["name"] == "search_transcripts"
        assert "input_schema" in tool_def
        assert "query" in tool_def["input_schema"]["properties"]
