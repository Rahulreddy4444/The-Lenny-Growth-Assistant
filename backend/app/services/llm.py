"""
LLM Provider abstraction layer.

Provides a unified interface for both Anthropic Claude and Ollama,
with no branching in business logic.

ADR-006: Provider Swap Architecture
"""

import asyncio
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

        # Sanitize messages for Ollama API
        clean_messages = []
        for m in all_messages:
            msg_dict = {"role": m["role"], "content": m.get("content") or ""}
            if m.get("tool_calls"):
                msg_dict["tool_calls"] = m["tool_calls"]
            clean_messages.append(msg_dict)

        payload = {
            "model": self.chat_model,
            "messages": clean_messages,
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
            async with httpx.AsyncClient(timeout=300) as client:
                resp = await client.post(
                    f"{self.base_url}/api/chat",
                    json=payload,
                )
                if resp.status_code >= 400:
                    logger.error(f"Ollama API error ({resp.status_code}): {resp.text}")
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
        if "tool_calls" in message:
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                tool_calls.append({
                    "id": tc.get("id", f"call_{len(tool_calls)}"),
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


class GroqProvider(LLMProvider):
    """Groq provider using OpenAI-compatible API for fast inference."""

    def __init__(self, api_key: str, model: str = "qwen/qwen3.6-27b"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://api.groq.com/openai/v1"
        logger.info(f"Groq provider initialized with model: {model}")

    async def chat(
        self,
        messages: list[dict],
        system_prompt: str = "",
        tools: list[dict] = None,
        tool_results: list[dict] = None,
    ) -> LLMResponse:
        """Send chat request to Groq API."""
        all_messages = []
        if system_prompt:
            all_messages.append({"role": "system", "content": system_prompt})
        all_messages.extend(messages)

        payload = {
            "model": self.model,
            "messages": all_messages,
            "max_tokens": 1500,
            "temperature": 0.3,
        }

        # Format tools for OpenAI/Groq compatible endpoint
        if tools:
            groq_tools = []
            for tool in tools:
                groq_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool.get("description", ""),
                        "parameters": tool.get("input_schema", {}),
                    },
                })
            payload["tools"] = groq_tools
            payload["tool_choice"] = "auto"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        max_retries = 8
        data = None

        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient(timeout=120) as client:
                    resp = await client.post(
                        f"{self.base_url}/chat/completions",
                        json=payload,
                        headers=headers
                    )
                    if resp.status_code == 429:
                        # Rate limit reached — determine retry delay from headers or body
                        retry_after = 5.0 * (attempt + 1)
                        if "retry-after" in resp.headers:
                            try:
                                retry_after = float(resp.headers["retry-after"]) + 1.0
                            except ValueError:
                                pass
                        else:
                            try:
                                err_json = resp.json()
                                msg = err_json.get("error", {}).get("message", "")
                                import re
                                match = re.search(r"try again in (\d+\.?\d*)s", msg)
                                if match:
                                    retry_after = float(match.group(1)) + 1.5
                            except Exception:
                                pass

                        # Cap retry wait to max 30 seconds
                        retry_after = min(retry_after, 30.0)

                        # Reduce max_tokens dynamically to fit under rate limits on retry
                        if "max_tokens" in payload and payload["max_tokens"] > 600:
                            payload["max_tokens"] = int(payload["max_tokens"] * 0.75)

                        logger.warning(f"Groq 429 Rate Limit (attempt {attempt+1}/{max_retries}). Retrying in {retry_after:.1f}s...")
                        await asyncio.sleep(retry_after)
                        continue

                    if resp.status_code >= 400:
                        logger.error(f"Groq API error ({resp.status_code}): {resp.text}")
                    resp.raise_for_status()
                    data = resp.json()
                    break
            except httpx.HTTPStatusError as e:
                if attempt == max_retries - 1:
                    logger.error(f"Groq API HTTP error after {max_retries} attempts: {e}")
                    raise
                await asyncio.sleep(4.0)
            except Exception as e:
                if attempt == max_retries - 1:
                    logger.error(f"Groq API connection error after {max_retries} attempts: {e}")
                    raise
                await asyncio.sleep(3.0)

        if not data:
            raise RuntimeError("Failed to get response from Groq API after retries.")

        message = data.get("choices", [{}])[0].get("message", {})
        content = message.get("content", "")
        tool_calls = []

        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                
                # Parse arguments if it's a JSON string
                arguments = fn.get("arguments", "{}")
                if isinstance(arguments, str):
                    import json
                    try:
                        arguments = json.loads(arguments)
                    except json.JSONDecodeError:
                        arguments = {}

                tool_calls.append({
                    "id": tc.get("id", ""),
                    "name": fn.get("name", ""),
                    "input": arguments,
                })

        # Fallback: Parse raw XML tool calls from content if native tool_calls are missing
        if not tool_calls and content:
            import re
            tool_blocks = re.findall(r'<tool_call>(.*?)</tool_call>', content, re.DOTALL | re.IGNORECASE)
            for block in tool_blocks:
                fn_match = re.search(r'<function=([^>]+)>', block)
                if fn_match:
                    name = fn_match.group(1).strip()
                    params = {}
                    param_matches = re.finditer(r'<parameter=([^>]+)>(.*?)</parameter>', block, re.DOTALL)
                    for p in param_matches:
                        params[p.group(1).strip()] = p.group(2).strip()
                    tool_calls.append({
                        "id": f"call_{len(tool_calls)}",
                        "name": name,
                        "input": params
                    })

        stop_reason = data.get("choices", [{}])[0].get("finish_reason", "end_turn")
        
        return LLMResponse(
            content=content or "",
            tool_calls=tool_calls,
            stop_reason=stop_reason,
            raw=data,
        )

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        """Groq does not natively provide embeddings in the same way, delegate to Ollama."""
        raise NotImplementedError(
            "Groq does not provide embeddings in this setup. "
            "Use Ollama for embeddings regardless of chat provider."
        )


class FastEmbedService:
    """Standalone embedding service using fastembed (no Ollama required)."""
    
    def __init__(self, embed_model: str = "nomic-ai/nomic-embed-text-v1.5"):
        from fastembed import TextEmbedding
        logger.info(f"Initializing FastEmbed with model: {embed_model}")
        self.model = TextEmbedding(model_name=embed_model)

    async def embed(self, text: str | list[str]) -> list[list[float]]:
        if isinstance(text, str):
            text = [text]
        # fastembed returns a generator of numpy arrays, convert to list of list of floats
        embeddings = list(self.model.embed(text))
        return [emb.tolist() for emb in embeddings]

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
    elif settings.llm_provider == "groq":
        if not settings.groq_api_key:
            raise ValueError(
                "GROQ_API_KEY is required when LLM_PROVIDER=groq"
            )
        return GroqProvider(
            api_key=settings.groq_api_key,
            model=settings.groq_model,
        )
    else:
        raise ValueError(f"Unknown LLM provider: {settings.llm_provider}")


def get_embedding_service(settings):
    """Factory function — returns the embedding service (always FastEmbed)."""
    # Force use of fastembed so it works in the cloud without Ollama!
    return FastEmbedService(embed_model="nomic-ai/nomic-embed-text-v1.5")
