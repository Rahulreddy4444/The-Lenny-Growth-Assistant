# Design Document — The Lenny Growth Assistant

## UI Layout

The interface uses a two-panel layout built with Streamlit's `st.columns`:

```
┌─────────────────────────────────────────────────────────────────┐
│  🎙️ The Lenny Growth Assistant          [Provider: Ollama 🟢]  │
├───────────────┬─────────────────────────────────────────────────┤
│               │                                                 │
│  Sessions     │   Chat Panel (2/3 width)                        │
│  ─────────    │   ┌───────────────────────────────────────────┐ │
│  📝 Session 1 │   │ 🤖 Welcome! Ask me about product...      │ │
│  📝 Session 2 │   │                                           │ │
│  📝 Session 3 │   │ 👤 How do top PMs approach retention?     │ │
│               │   │                                           │ │
│  [+ New]      │   │ 🤖 Based on Lenny's Podcast transcripts...│ │
│               │   │    [Episode: "...", Guest: "..."]         │ │
│               │   │                                           │ │
│  ─────────    │   │ 👤 Turn that into a Ship 30 essay         │ │
│  Settings     │   │                                           │ │
│  Provider:    │   │ 🤖 Here's your essay: [View Artifact]     │ │
│  [Ollama ▼]   │   └───────────────────────────────────────────┘ │
│               │   ┌───────────────────────────────────────────┐ │
│               │   │ 💬 Type your message...            [Send] │ │
│               │   └───────────────────────────────────────────┘ │
├───────────────┴─────────────────────────────────────────────────┤
│                                                                 │
│   Artifact Viewer (expands when artifact is present)            │
│   ┌───────────────────────────────────────────────────────────┐ │
│   │  📄 Ship 30 Essay: "How Top PMs..."                      │ │
│   │  ─────────────────────────────────────────────            │ │
│   │  (Rendered Markdown or sanitized HTML)                    │ │
│   │                                                           │ │
│   └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## UX Flows

### 1. New Conversation
1. User clicks "+ New Session" in sidebar
2. New session created via `POST /sessions`
3. Chat panel clears, welcome message appears
4. User types question in chat input

### 2. Ask a Grounded Question
1. User types: "What does Lenny say about product-market fit?"
2. Message sent to `POST /chat` with session_id
3. Backend: agent searches transcripts, composes cited answer
4. Response appears in chat with source citations (episode title, guest)
5. Citations link to source metadata

### 3. Generate Ship 30 Essay
1. After receiving a grounded answer, user types: "Turn that into a Ship 30 essay"
2. Agent invokes essay generation tool with the grounded content
3. Essay returned as a Markdown artifact
4. Artifact viewer panel shows the rendered essay
5. Chat shows a summary with "View Artifact" link

### 4. Out-of-Scope Question
1. User asks: "What is the capital of France?"
2. Agent searches transcripts, finds no relevant chunks
3. Response: "I couldn't find information about this in Lenny's Podcast transcripts. I can only answer questions grounded in the podcast content."

### 5. Switch Provider
1. User selects different provider from sidebar dropdown
2. Provider change takes effect on next message
3. Active provider label updates in header

### 6. HTML Artifact with Security
1. Agent generates or user requests HTML content
2. Backend sanitizes HTML via `nh3` (strips scripts, event handlers)
3. Sanitized HTML renders in `st.components.v1.html` iframe
4. Any `<script>` tags are visibly stripped

## Visual Design

- **Color Scheme**: Clean, professional — dark sidebar, light main panel
- **Typography**: System fonts for fast loading
- **Citations**: Styled as subtle cards with episode info
- **Artifacts**: Bordered panel with clear "Artifact" label
- **Status Indicators**: Green/red dots for provider and system status
