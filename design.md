# Design Document — The Lenny Growth Assistant

## UI/UX Principles & Information Architecture
- **Two-Column Layout**: Left sidebar for persistent multi-turn session switching and live system status (DB, Ollama, active provider). Main content area for conversation with side-by-side artifact viewer when artifacts are active.
- **Visual Citations**: Sources formatted as dedicated HTML `citation-card` components with episode title, guest name, timestamp, and clickable YouTube links, cleanly nested inside an expandable accordion.
- **Artifact Viewer**: Seamless Markdown and HTML rendering next to the chat without context loss. Features a polished header and secure rendering indicators.
- **Custom Theming & CSS**: Overrides default Streamlit styles with custom typography (Inter font), distinct user/assistant chat bubbles, and dynamic CSS variables (`var(--text-color)`) that natively support Light and Dark modes.
- **Security Isolation**: Server-side HTML sanitization using `nh3` to prevent script execution while preserving clean formatting.

## Key Interaction States
1. **Empty / Welcome State**: Polished landing screen with a descriptive title, subtitle, and interactive 4-grid example prompts that auto-start a session on click.
2. **Thinking / Loading State**: Spinner with progress indication during vector search and inference.
3. **Citation State**: Expandable references accordion for deep inspection of retrieved chunks.
4. **Artifact State**: Expands side panel (3:2 column ratio) showing essays or HTML snippets with closing toggle.
5. **Fallback State**: Clear and polite notification when a topic is not covered in the podcast knowledge base.
