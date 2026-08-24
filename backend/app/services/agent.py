"""
Agent orchestration service.

PRIMARY: Attempts to use claude-agent-sdk with custom MCP tools.
FALLBACK: If claude-agent-sdk is unavailable or incompatible, falls back to
         the standard anthropic Python SDK with native tool-use loop.

The agent:
1. Receives a conversation history
2. Decides whether to search transcripts (retrieval tool)
3. Generates grounded, cited responses
4. Can invoke the Ship 30 for 30 essay tool
5. Explicitly says "not covered" when transcripts don't support an answer
"""

import json
import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.config import Settings, get_settings
from backend.app.services.llm import get_chat_provider, get_embedding_service, LLMProvider, LLMResponse
from backend.app.services.retrieval import search_transcripts
from backend.app.services.essay import (
    get_essay_tool_definition,
    build_essay_prompt,
    SHIP30_SYSTEM_PROMPT,
)

logger = logging.getLogger(__name__)

# ── System prompt enforcing grounding ──────────────────────────────────────────

SYSTEM_PROMPT = """You are The Lenny Growth Assistant — answering product and growth questions grounded STRICTLY in Lenny's Podcast transcripts.
Rules:
1. Search transcripts with `search_transcripts` before answering product/growth questions.
2. Ground claims in retrieved transcripts. Cite sources inline: *(Source: "[Episode Title]" with [Guest])*.
3. If not covered, state clearly: "I couldn't find information about this topic in Lenny's Podcast transcripts."
4. When asked for an essay or Ship 30, use `generate_ship30_essay` and wrap in `<artifact type="markdown" title="...">...</artifact>`.
5. Keep answers concise, actionable, and formatted in Markdown."""


# ── Tool definitions ──────────────────────────────────────────────────────────

def get_search_tool_definition() -> dict:
    """Return the tool definition for transcript search."""
    return {
        "name": "search_transcripts",
        "description": (
            "Search Lenny's Podcast transcripts for content relevant to a query. "
            "Returns the top matching transcript chunks with episode metadata "
            "(title, guest, date, YouTube URL). Use this tool BEFORE answering "
            "any product, growth, or startup question to ground your response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query to find relevant transcript content",
                },
            },
            "required": ["query"],
        },
    }


# ── Agent Service ─────────────────────────────────────────────────────────────

class AgentService:
    """Orchestrates the agent loop with tool-use."""

    def __init__(self, settings: Settings = None):
        self.settings = settings or get_settings()
        self.provider = get_chat_provider(self.settings)
        self.embedding_service = get_embedding_service(self.settings)
        self.tools = [
            get_search_tool_definition(),
            get_essay_tool_definition(),
        ]
        self._last_search_results = []  # Cache for essay generation

    async def run(self, messages: list[dict], db: AsyncSession) -> dict:
        """
        Run the agent loop.

        Returns a dict with:
            content: str — the assistant's response text
            cited_sources: list[dict] — source citations
            artifact: dict|None — {type, content, title} if an artifact was generated
        """
        # Try claude-agent-sdk first for anthropic, otherwise use standard tool-use loop
        if self.settings.llm_provider == "anthropic":
            try:
                return await self._run_with_agent_sdk(messages, db)
            except ImportError as e:
                logger.warning(f"claude-agent-sdk not available: {e}. Falling back to standard tool-use loop.")
                return await self._run_standard_tool_loop(messages, db)
            except Exception as e:
                logger.warning(f"claude-agent-sdk failed: {e}. Falling back to standard tool-use loop.")
                return await self._run_standard_tool_loop(messages, db)
        else:
            return await self._run_standard_tool_loop(messages, db)

    async def _run_with_agent_sdk(self, messages: list[dict], db: AsyncSession) -> dict:
        """
        Attempt to use claude-agent-sdk with custom MCP tools.

        The SDK bundles the Claude Code CLI and provides @tool decorator
        for custom tools and create_sdk_mcp_server for bundling.
        """
        from claude_agent_sdk import tool, create_sdk_mcp_server, ClaudeAgentOptions, query as sdk_query

        # Define tools as SDK-compatible functions
        @tool
        async def search_transcripts_tool(query: str) -> str:
            """Search Lenny's Podcast transcripts for relevant content."""
            results = await search_transcripts(query, db, self.embedding_service, self.settings.retrieval_top_k)
            self._last_search_results = results
            if not results:
                return "No relevant transcript chunks found for this query."

            output = "Found the following relevant transcript excerpts:\n\n"
            for i, chunk in enumerate(results[:4], 1):
                content = chunk['content'].strip()
                if len(content) > 1200:
                    content = content[:1200] + "..."
                output += f"### Source {i}: {chunk['episode_title']} (with {chunk['guest']})\n"
                output += f"Date: {chunk['publish_date']} | "
                if chunk.get('youtube_url'):
                    output += f"URL: {chunk['youtube_url']}\n"
                output += f"\n{content}\n\n---\n\n"
            return output

        @tool
        async def generate_essay_tool(topic: str, grounded_content: str, sources: str = "") -> str:
            """Generate a Ship 30 for 30 style essay from grounded content."""
            source_list = json.loads(sources) if sources else []
            return build_essay_prompt(topic, grounded_content, source_list)

        # Create MCP server with our tools
        mcp_server = create_sdk_mcp_server(tools=[search_transcripts_tool, generate_essay_tool])

        # Build conversation prompt
        conversation = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}"
            for m in messages
        )

        # Run the agent
        options = ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            mcp_servers={"lenny_tools": mcp_server},
            allowed_tools=["mcp__lenny_tools__search_transcripts_tool", "mcp__lenny_tools__generate_essay_tool"],
            max_turns=10,
        )

        result_text = ""
        async for message in sdk_query(prompt=conversation, options=options):
            if hasattr(message, 'content') and message.content:
                result_text += str(message.content)

        # Build response
        return self._build_response(result_text)

    async def _run_standard_tool_loop(self, messages: list[dict], db: AsyncSession) -> dict:
        """
        Standard tool-use loop using LLMProvider abstraction.

        Works with both Anthropic SDK (native tool-use) and Ollama (OpenAI-compatible).
        """
        MAX_TOOL_ITERATIONS = 3
        cited_sources = []
        artifact = None

        # Start the conversation
        current_messages = list(messages)

        for iteration in range(MAX_TOOL_ITERATIONS):
            # Call the LLM
            response = await self.provider.chat(
                messages=current_messages,
                system_prompt=SYSTEM_PROMPT,
                tools=self.tools,
            )

            # If no tool calls, we have the final response
            if not response.tool_calls:
                result_text = response.content
                break

            # Process tool calls
            if self.settings.llm_provider == "anthropic":
                # Anthropic tool format
                current_messages.append({
                    "role": "assistant",
                    "content": response.raw.content if response.raw else [{"type": "text", "text": response.content}],
                })
                for tc in response.tool_calls:
                    tool_result = await self._execute_tool(tc, db)
                    current_messages.append({
                        "role": "user",
                        "content": [
                            {
                                "type": "tool_result",
                                "tool_use_id": tc["id"],
                                "content": tool_result,
                            }
                        ],
                    })
            else:
                # OpenAI / Groq / Ollama tool format
                current_messages.append({
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": [
                        {
                            "id": tc.get("id") or f"call_{i}",
                            "type": "function",
                            "function": {
                                "name": tc["name"],
                                "arguments": json.dumps(tc["input"]) if isinstance(tc.get("input"), dict) else str(tc.get("input", "{}")),
                            },
                        }
                        for i, tc in enumerate(response.tool_calls)
                    ],
                })

                for i, tc in enumerate(response.tool_calls):
                    call_id = tc.get("id") or f"call_{i}"
                    tool_result = await self._execute_tool(tc, db)
                    current_messages.append({
                        "role": "tool",
                        "tool_call_id": call_id,
                        "name": tc["name"],
                        "content": str(tool_result),
                    })
        else:
            # Max iterations reached
            result_text = response.content or "I was unable to complete the analysis within the allowed steps."

        # Build cited sources from last search results
        for chunk in self._last_search_results:
            cited_sources.append({
                "episode_title": chunk["episode_title"],
                "guest": chunk["guest"],
                "publish_date": chunk.get("publish_date"),
                "youtube_url": chunk.get("youtube_url"),
                "section_timestamp": chunk.get("section_timestamp"),
                "content_preview": chunk["content"][:200],
            })

        # Extract artifact from response
        artifact = self._extract_artifact(result_text)

        # Clean artifact markers from the main content if artifact was extracted
        clean_content = result_text
        if artifact:
            import re
            clean_content = re.sub(
                r'<artifact[^>]*>.*?</artifact>',
                f'\n\n📄 **Artifact generated:** {artifact.get("title", "Untitled")}\n',
                result_text,
                flags=re.DOTALL,
            )

        return {
            "content": clean_content.strip(),
            "cited_sources": cited_sources,
            "artifact": artifact,
        }

    async def _execute_tool(self, tool_call: dict, db: AsyncSession) -> str:
        """Execute a tool call and return the result as a string."""
        name = tool_call["name"]
        args = tool_call.get("input", {})

        logger.info(f"Executing tool: {name} with args: {json.dumps(args)[:200]}")

        try:
            if name == "search_transcripts":
                query = args.get("query", "")
                results = await search_transcripts(
                    query, db, self.embedding_service, self.settings.retrieval_top_k
                )
                self._last_search_results = results

                if not results:
                    return "No relevant transcript chunks found for this query."

                # Return top chunks with concise excerpt to keep prompt compact and stay within API token limits
                output = "Found the following relevant transcript excerpts:\n\n"
                for i, chunk in enumerate(results[:3], 1):
                    content = chunk['content'].strip()
                    if len(content) > 700:
                        content = content[:700] + "..."
                    output += f"### Source {i}: {chunk['episode_title']} (with {chunk['guest']})\n"
                    output += f"Date: {chunk['publish_date']}\n"
                    if chunk.get('youtube_url'):
                        output += f"URL: {chunk['youtube_url']}\n"
                    if chunk.get('section_timestamp'):
                        output += f"Timestamp: {chunk['section_timestamp']}\n"
                    output += f"\n{content}\n\n---\n\n"
                return output

            elif name == "generate_ship30_essay":
                topic = args.get("topic", "")
                grounded_content = args.get("grounded_content", "")
                sources = args.get("sources", [])
                return build_essay_prompt(topic, grounded_content, sources)

            else:
                return f"Unknown tool: {name}"

        except Exception as e:
            logger.error(f"Tool execution error ({name}): {e}")
            return f"Tool error: {str(e)}"

    def _extract_artifact(self, text: str) -> dict | None:
        """Extract artifact from response text if present."""
        import re

        # Match <artifact type="..." title="...">content</artifact>
        pattern = r'<artifact\s+type="(\w+)"\s+title="([^"]*)">(.*?)</artifact>'
        match = re.search(pattern, text, re.DOTALL)

        if match:
            return {
                "type": match.group(1),
                "title": match.group(2),
                "content": match.group(3).strip(),
            }

        return None

    def _build_response(self, text: str) -> dict:
        """Build a standard response dict from text output."""
        artifact = self._extract_artifact(text)
        cited_sources = []
        for chunk in self._last_search_results:
            cited_sources.append({
                "episode_title": chunk["episode_title"],
                "guest": chunk["guest"],
                "publish_date": chunk.get("publish_date"),
                "youtube_url": chunk.get("youtube_url"),
                "section_timestamp": chunk.get("section_timestamp"),
                "content_preview": chunk["content"][:200],
            })

        clean_content = text
        if artifact:
            import re
            clean_content = re.sub(
                r'<artifact[^>]*>.*?</artifact>',
                f'\n\n📄 **Artifact generated:** {artifact.get("title", "Untitled")}\n',
                text,
                flags=re.DOTALL,
            )

        return {
            "content": clean_content.strip(),
            "cited_sources": cited_sources,
            "artifact": artifact,
        }
