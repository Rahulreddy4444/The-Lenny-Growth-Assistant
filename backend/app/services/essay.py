"""
Ship 30 for 30 essay generation skill.

Encodes the Ship 30 for 30 writing rules as a structured prompt template,
exposed as a callable tool the agent can invoke.

ADR-005: Extended format (~1250 words using Ship 30 structural principles).
"""

SHIP30_SYSTEM_PROMPT = """You are an expert essay writer who specializes in the Ship 30 for 30 writing format.

## Ship 30 for 30 Format Rules

You MUST follow these structural rules when generating an essay:

### 1. Hook Headline
- The headline must be CLEAR, not "clever"
- It must explicitly state: WHAT the essay is about, WHO it is for, and WHAT the reader gains
- Format: Use a compelling, specific promise

### 2. Introduction (1/3/1 rhythm)
- One powerful opening sentence (the hook)
- Three sentences expanding the promise and establishing credibility
- One sentence transitioning to the main content

### 3. Main Body — 3 to 5 Structured Points
- Each point gets its own **bold subheading**
- Use the format: Subheading → Explanation → Example/Evidence → Actionable takeaway
- Include bullet points for actionable steps
- **Bold key phrases** for skimmability
- Cite specific sources from the provided transcript content

### 4. Conclusion — Single Specific Takeaway
- One clear, actionable takeaway the reader can implement immediately
- Do NOT summarize all points — pick the ONE most important insight
- End with a forward-looking statement

### 5. Formatting Requirements
- Target length: approximately 1,250 words
- Use Markdown formatting throughout
- Use ## for the title, ### for section headings
- Use **bold** for key phrases and emphasis
- Use bullet points (- ) for lists and action items
- Use > blockquotes for direct quotes from podcast transcripts
- Include source citations in the format: *(Source: [Episode Title] with [Guest])*

### 6. Voice and Tone
- Write in second person ("you") to address the reader directly
- Be concrete and specific — avoid vague generalities
- Every claim must be grounded in the provided transcript content
- If you reference advice, attribute it to the specific guest who said it
"""


def get_essay_tool_definition() -> dict:
    """Return the tool definition for Ship 30 for 30 essay generation."""
    return {
        "name": "generate_ship30_essay",
        "description": (
            "Generate a Ship 30 for 30 style essay (~1250 words) from a grounded answer "
            "about product/growth topics. The essay will have a hook headline, structured "
            "main points with bold subheadings, bullet points, source citations from "
            "Lenny's Podcast transcripts, and a single specific takeaway. "
            "Use this tool when the user asks to turn an answer into an essay, "
            "write an essay, or create a Ship 30 piece."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": "The topic or question the essay should address",
                },
                "grounded_content": {
                    "type": "string",
                    "description": (
                        "The grounded answer content with source citations "
                        "that the essay should be based on"
                    ),
                },
                "sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "episode_title": {"type": "string"},
                            "guest": {"type": "string"},
                            "content_preview": {"type": "string"},
                        },
                    },
                    "description": "Source citations from transcript chunks",
                },
            },
            "required": ["topic", "grounded_content"],
        },
    }


def build_essay_prompt(topic: str, grounded_content: str, sources: list[dict] = None) -> str:
    """Build the prompt for essay generation."""
    source_text = ""
    if sources:
        source_text = "\n\n## Available Sources:\n"
        for src in sources:
            source_text += (
                f"- **{src.get('episode_title', 'Unknown')}** "
                f"with {src.get('guest', 'Unknown')}: "
                f"{src.get('content_preview', '')}\n"
            )

    return f"""Write a Ship 30 for 30 style essay on the following topic.

## Topic
{topic}

## Grounded Content (use this as your source material — do not make up information)
{grounded_content}
{source_text}

Generate the essay now, following all Ship 30 for 30 format rules strictly.
Target approximately 1,250 words. Use Markdown formatting.
Every claim must cite a specific source from the content above."""
