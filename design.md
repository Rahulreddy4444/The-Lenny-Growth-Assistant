# Design Document — The Lenny Growth Assistant

> Note: Detailed version maintained in [docs/design.md](docs/design.md).

## UI/UX Principles & Information Architecture
- **Two-Column Layout**: Left sidebar for persistent multi-turn session switching and live system status (DB, Ollama, active provider). Main content area for conversation with side-by-side artifact viewer when artifacts are active.
- **Visual Citations**: Sources formatted with episode title, guest name, timestamp, and clickable YouTube links.
- **Artifact Viewer**: Seamless Markdown and HTML rendering next to the chat without context loss or navigation.
- **Security Isolation**: Server-side HTML sanitization using `nh3` to prevent script execution while preserving clean formatting.

## Key Interaction States
1. **Empty / Welcome State**: Prompts user to start a session with example questions.
2. **Thinking / Loading State**: Spinner with progress indication during vector search and inference.
3. **Citation State**: Expandable references accordion for deep inspection of retrieved chunks.
4. **Artifact State**: Expands side panel (3:2 column ratio) showing essays or HTML snippets with closing toggle.
5. **Fallback State**: Clear and polite notification when a topic is not covered in the podcast knowledge base.
