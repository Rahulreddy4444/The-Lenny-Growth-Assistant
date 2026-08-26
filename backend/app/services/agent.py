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

SYSTEM_PROMPT = """You are The Lenny Growth Assistant — an expert AI assistant answering product, growth, and startup questions grounded STRICTLY in Lenny's Podcast transcripts.

## Core Rules:
1. **Searching Transcripts**: Use `search_transcripts` to find relevant podcast transcript excerpts.
   - Extract only the core subject/keywords (e.g., "Brian Chesky founder led product management", NEVER include formatting words like "Ship 30", "essay", or "artifact" in the query).
   - If the user asks to turn a PREVIOUS answer or conversation history into an essay/artifact, DO NOT search again — immediately format the existing context into the artifact.
2. **Grounding & Citations**: Ground every insight in the podcast transcripts and cite sources: *(Source: "[Episode Title]" with [Guest])*.
3. **Not Covered**: If a topic is genuinely not found in the podcast transcripts after searching, state: "I couldn't find information about this topic in Lenny's Podcast transcripts."

4. **Ship 30 for 30 Essay Architecture**:
When asked to write a Ship 30 for 30 essay, post, framework, or artifact:
   - Wrap the entire generated content inside `<artifact type="markdown" title="A Compelling, Specific Headline">...</artifact>`.
   - Write an in-depth, high-value, actionable essay (~800–1200 words) strictly following the Ship 30 for 30 architecture:
     * **1. Headline**: `# [Clear, Promise-Driven Title: What It's About, Who It's For, What They Gain]`
     * **2. 1/3/1 Intro**:
       - 1 punchy, counter-intuitive opening sentence (the hook).
       - 3 sentences expanding on the common mistake, establishing the stakes, and building credibility.
       - 1 sentence transition introducing the core pillars.
     * **3. Main Body (3 to 5 Actionable Pillars)**:
       - Each pillar MUST use a bold numbered heading: `### 1. [Bold Actionable Subheading]`
       - Explain the principle directly in second person ("you").
       - Provide 2-4 tactical bullet points with **bold lead-ins** for maximum readability.
       - Include direct quotes or concrete examples from the podcast with inline attribution: `> "[Direct Quote]"` *(Source: "[Episode Title]" with [Guest])*.
     * **4. Conclusion — Single Specific Takeaway**:
       - `### The 1 Thing to Implement in the Next 24 Hours`
       - Provide ONE concrete, tactical exercise the reader can execute immediately.
       - End with a motivating forward-looking statement.
   - Always format in clean Markdown with bolding, blockquotes (`>`), lists (`*`), and section headers (`###`).

5. **HTML Code Artifacts**: For HTML/interactive widgets, wrap inside `<artifact type="html" title="Title">...</artifact>`.
6. Output your response directly without `<think>` blocks."""


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
        self._last_search_results = []
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
        MAX_TOOL_ITERATIONS = 4
        # Prune conversation history to last 4 turns to preserve context while keeping token usage low
        recent_messages = []
        for m in messages[-4:]:
            content = m.get("content", "")
            recent_messages.append({
                "role": m.get("role"),
                "content": content,
            })

        current_messages = list(recent_messages)
        search_count = 0

        # Check if the user's latest prompt is asking to format existing conversation context
        last_user_prompt = messages[-1].get("content", "").lower() if messages else ""
        is_formatting_followup = (
            len(messages) > 1 and 
            any(phrase in last_user_prompt for phrase in [
                "turn that into", "turn this into", "make an essay", "write a ship 30", 
                "write an essay", "create an essay", "make a ship 30", "format as", "create an artifact"
            ])
        )

        for iteration in range(MAX_TOOL_ITERATIONS):
            # If it's a follow-up formatting request or if search already completed, synthesize directly
            if (is_formatting_followup and iteration == 0) or search_count >= 1:
                active_tools = None
            else:
                active_tools = self.tools

            # Call the LLM
            response = await self.provider.chat(
                messages=current_messages,
                system_prompt=SYSTEM_PROMPT,
                tools=active_tools,
            )

            # If no tool calls, we have the final response
            if not response.tool_calls:
                result_text = response.content
                break

            # Count searches
            for tc in response.tool_calls:
                if tc.get("name") == "search_transcripts":
                    search_count += 1

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
                is_ollama = self.settings.llm_provider == "ollama"
                formatted_tool_calls = []
                for i, tc in enumerate(response.tool_calls):
                    inp = tc.get("input", {})
                    if is_ollama:
                        args = inp if isinstance(inp, dict) else (json.loads(inp) if inp else {})
                    else:
                        if isinstance(inp, dict):
                            args = json.dumps(inp)
                        else:
                            try:
                                args = json.dumps(json.loads(inp))
                            except Exception:
                                import ast
                                try:
                                    args = json.dumps(ast.literal_eval(inp))
                                except Exception:
                                    args = json.dumps({"query": str(inp)})
                    formatted_tool_calls.append({
                        "id": tc.get("id") or f"call_{i}",
                        "type": "function",
                        "function": {
                            "name": tc["name"],
                            "arguments": args,
                        },
                    })

                # Append assistant message
                current_messages.append({
                    "role": "assistant",
                    "content": response.content or "",
                    "tool_calls": formatted_tool_calls,
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

        return self._build_response(result_text)

    def _clean_model_text(self, text: str) -> str:
        """Strip <think>...</think> reasoning blocks and raw tool_call tags from model output."""
        import re
        
        # First strip raw <tool_call> tags completely
        cleaned = re.sub(r'<tool_call>.*?</tool_call>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        original_without_tools = cleaned
        
        # Then strip closed <think>...</think>
        cleaned = re.sub(r'<think>.*?</think>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        # Strip unclosed <think> at the start if any
        if cleaned.strip().startswith('<think>'):
            cleaned = re.sub(r'<think>.*?(?=\n\n|\n[#A-Z<]|$)', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
        
        result = cleaned.strip()
        if not result and original_without_tools.strip():
            # If the model put its ENTIRE response inside the <think> block, return the inner text
            result = re.sub(r'</?think>', '', original_without_tools, flags=re.IGNORECASE).strip()
            
        return result

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
                    return "No relevant transcript chunks found for this query. State that this topic is not covered in Lenny's Podcast transcripts."

                output = "Found the following relevant transcript excerpts from Lenny's Podcast:\n\n"
                for i, chunk in enumerate(results[:3], 1):
                    content = chunk['content'].strip()
                    if len(content) > 700:
                        content = content[:700] + "..."
                    output += f"### Source {i}: \"{chunk['episode_title']}\" (with {chunk['guest']})\n"
                    output += f"Date: {chunk['publish_date']}\n"
                    if chunk.get('youtube_url'):
                        output += f"URL: {chunk['youtube_url']}\n"
                    if chunk.get('section_timestamp'):
                        output += f"Timestamp: {chunk['section_timestamp']}\n"
                    output += f"\n{content}\n\n---\n\n"

                output += "\nInstructions: Answer the user's question directly and thoroughly using the transcript excerpts above. Cite your sources inline using: *(Source: \"[Episode Title]\" with [Guest])*. Do not call any further tools."
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
        text = self._clean_model_text(text)

        if "<artifact" in text.lower():
            # First try standard closed tag
            match = re.search(
                r'<artifact(?:\s+type=[\'"]?(\w+)[\'"]?)?(?:\s+title=[\'"]?([^\'">]*)[\'"]?)?[^>]*>(.*?)</artifact>',
                text,
                re.DOTALL | re.IGNORECASE,
            )
            if not match:
                # Try unclosed tag capturing until end of text
                match = re.search(
                    r'<artifact(?:\s+type=[\'"]?(\w+)[\'"]?)?(?:\s+title=[\'"]?([^\'">]*)[\'"]?)?[^>]*>(.*)$',
                    text,
                    re.DOTALL | re.IGNORECASE,
                )

            if match:
                art_type = match.group(1) or "markdown"
                title = match.group(2) or "Generated Essay"
                # Strip placeholder title if the model literally wrote "Your Title"
                if title.lower() in ["your title", "your title here", "untitled"]:
                    # Try to extract the first # Header as title
                    first_header = re.search(r'^#+\s+(.+)$', match.group(3).strip(), re.MULTILINE)
                    if first_header:
                        title = first_header.group(1).strip()
                    else:
                        title = "Ship 30 for 30 Essay"

                content = match.group(3).strip()
                if content and len(content) > 30:
                    return {
                        "type": art_type.lower(),
                        "title": title.strip(),
                        "content": content,
                    }

        # Fallback 1: Detect HTML codeblocks
        html_block = re.search(r'```html\s*(<!DOCTYPE html.*?|.*?<html.*?)```', text, re.DOTALL | re.IGNORECASE)
        if html_block:
            return {
                "type": "html",
                "title": "HTML Preview",
                "content": html_block.group(1).strip(),
            }

        # Fallback 2: Detect Ship 30 essays or structured long-form documents generated without <artifact> tags
        if ("subheading" in text.lower() or "takeaway" in text.lower() or "headline:" in text.lower() or "1/3/1" in text.lower()) and len(text) > 300:
            title = "Ship 30 for 30 Essay"
            title_m = re.search(r'(?:Headline|Title):\s*([^\n\r]+)', text, re.IGNORECASE)
            if title_m:
                title = title_m.group(1).strip()
            else:
                header_m = re.search(r'^#+\s+(.+)$', text, re.MULTILINE)
                if header_m:
                    title = header_m.group(1).strip()

            # Clean preamble up to the start of the essay
            start_match = re.search(r'(?:Headline|Title|Intro|#+\s+|Subheading 1|\*\*1\.)', text, re.IGNORECASE)
            essay_content = text[start_match.start():].strip() if start_match else text.strip()

            return {
                "type": "markdown",
                "title": title.strip() or "Ship 30 for 30 Essay",
                "content": essay_content,
            }

        return None

    def _build_response(self, text: str) -> dict:
        """Build a standard response dict from text output."""
        cleaned_text = self._clean_model_text(text)
        artifact = self._extract_artifact(cleaned_text)
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

        clean_content = cleaned_text.strip()
        if not clean_content:
            clean_content = "I couldn't find information about this topic in Lenny's Podcast transcripts."
            
        if artifact:
            clean_content = (
                f"📄 **{artifact.get('title', 'Ship 30 for 30 Essay')}** has been generated! "
                f"It is now rendered in the **Artifact Viewer** on the right ➡️"
            )

        return {
            "content": clean_content.strip(),
            "cited_sources": cited_sources,
            "artifact": artifact,
        }
