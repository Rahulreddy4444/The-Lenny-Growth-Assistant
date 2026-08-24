"""
LLM Provider abstraction layer.

Provides a unified interface for both Anthropic Claude and Ollama,
with no branching in business logic.

ADR-006: Provider Swap Architecture
"""

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)


class LLMResponse:
    """Unified response from any LLM provider."""

    def __init__(
        self,
        content: str = "",
        tool_calls: list[dict] = None,
        stop_reason: str = "end_turn",
        raw: Any = None,
    ):
        self.content = content
        self.tool_calls = tool_calls or []
        self.stop_reason = stop_reason
        self.raw = raw


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        tools: list[dict] = None,
        tool_results: list[dict] = None,
    ) -> LLMResponse:
        """Send a chat completion request."""
        ...

    @abstractmethod
    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Generate embeddings for text(s)."""
        ...


class AnthropicProvider(LLMProvider):
    """Anthropic Claude provider using the anthropic SDK with tool-use."""

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        import anthropic
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        logger.info(f"Anthropic provider initialized with model: {model}")

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        tools: list[dict] = None,
        tool_results: list[dict] = None,
    ) -> LLMResponse:
        """Send chat request to Anthropic Claude with tool-use support."""
        kwargs = {
            "model": self.model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system_prompt:
            kwargs["system"] = system_prompt
        if tools:
            kwargs["tools"] = tools

        try:
            response = self.client.messages.create(**kwargs)
        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

        # Parse response
        content_text = ""
        tool_calls = []
        for block in response.content:
            if block.type == "text":
                content_text += block.text
            elif block.type == "tool_use":
                tool_calls.append({
                    "id": block.id,
                    "name": block.name,
                    "input": block.input,
                })

        return LLMResponse(
            content=content_text,
            tool_calls=tool_calls,
            stop_reason=response.stop_reason,
            raw=response,
        )

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Anthropic doesn't offer embeddings — delegate to Ollama."""
        raise NotImplementedError(
            "Anthropic does not provide embeddings. "
            "Use Ollama for embeddings regardless of chat provider."
        )


class OllamaProvider(LLMProvider):
    """Ollama provider for local LLM inference and embeddings."""

    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        chat_model: str = "llama3.1:8b",
        embed_model: str = "nomic-embed-text",
    ):
        self.base_url = base_url.rstrip("/")
        self.chat_model = chat_model
        self.embed_model = embed_model
        logger.info(f"Ollama provider initialized: chat={chat_model}, embed={embed_model}")

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        tools: list[dict] = None,
        tool_results: list[dict] = None,
    ) -> LLMResponse:
        """Send chat request to Ollama."""
        # Prepend system message if provided
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload = {
            "model": self.chat_model,
            "messages": all_messages,
            "stream": False,
        }

        # Ollama supports tools in OpenAI-compatible format
        if tools:
            # Convert Anthropic tool format to Ollama/OpenAI format
            ollama_tools = []
            for tool in tools:
                ollama_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                })
            payload["tools"] = ollama_tools

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?"
            )
        except Exception as e:
            logger.error(f"Ollama chat error: {e}")
            raise

        # Parse response
        message = data.get("message", {})
        content = message.get("content", "")
        tool_calls = []

        # Parse tool calls if present
        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                tool_calls.append({
                    "id": fn.get("name", ""),  # Ollama doesn't always provide IDs
                    "name": fn.get("name", ""),
                    "input": fn.get("arguments", {}),
                })

        stop_reason = "tool_use" if tool_calls else "end_turn"
        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=data,
        )

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Generate embeddings via Ollama."""
        if isinstance(text, str):
            text = [text]

        payload = {
            "model": self.embed_model,
            "input": text,
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                resp = await client.post(
                    f"{self.base_url}/api/embed",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
        except httpx.ConnectError:
            raise ConnectionError(
                f"Cannot connect to Ollama at {self.base_url}. Is Ollama running?"
            )

        return data["embeddings"]


class EmbeddingService:
    """Standalone embedding service — always uses Ollama regardless of chat provider."""

    def __init__(self, base_url: str, embed_model: str):
        self._ollama = OllamaProvider(base_url=base_url, embed_model=embed_model)

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        return await self._ollama.embed(text)


def get_chat_provider(settings) -> LLMProvider:
    """Factory function — returns the configured chat LLM provider."""
    if settings.llm_provider == "anthropic":
        if not settings.anthropic_api_key:
            raise ValueError(
                "ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic"
            )
        return AnthropicProvider(
            api_key=settings.anthropic_api_key,
            model=settings.anthropic_model,
        )
    elif settings.llm_provider == "ollama":
        return OllamaProvider(
            base_url=settings.ollama_base_url,
            chat_model=settings.ollama_chat_model,
            embed_model=settings.ollama_embed_model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def get_embedding_service(settings) -> EmbeddingService:
    """Factory function — returns the embedding service (always Ollama)."""
    return EmbeddingService(
        base_url=settings.ollama_base_url,
        embed_model=settings.ollama_embed_model,
    )
