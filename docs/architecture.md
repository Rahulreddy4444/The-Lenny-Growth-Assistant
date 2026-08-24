# Architecture — The Lenny Growth Assistant

## System Overview

```
┌──────────────┐     ┌──────────────┐     ┌──────────────────┐
│   Streamlit  │────▶│   FastAPI     │────▶│  PostgreSQL +    │
│   Frontend   │◀────│   Backend     │◀────│  pgvector        │
│   (port 8501)│     │   (port 8000) │     │  (port 5432)     │
└──────────────┘     └──────┬───────┘     └──────────────────┘
                            │
                     ┌──────┴───────┐
                     │              │
              ┌──────▼──────┐ ┌────▼─────┐
              │  Anthropic  │ │  Ollama   │
              │  Claude API │ │  (local)  │
              │  (cloud)    │ │  port     │
              └─────────────┘ │  11434    │
                              └──────────┘
```

## Components

### Frontend (Streamlit)
- **Chat UI**: `st.chat_message` / `st.chat_input` for conversation
- **Artifact Viewer**: Side panel (`st.columns`) rendering Markdown and sanitized HTML
- **Session Management**: Sidebar with session list and creation
- **Provider Display**: Shows active LLM provider in UI

### Backend (FastAPI)
- **API Layer**: RESTful endpoints with Pydantic request/response models
- **Agent Layer**: Tool-use orchestration for retrieval and essay generation
- **LLM Service**: Provider-swap adapter supporting Anthropic and Ollama
- **Retrieval Service**: Vector similarity search over pgvector

### Database (PostgreSQL + pgvector)
- Single database for both application data and vector search
- Tables: `transcript_chunks`, `sessions`, `messages`
- HNSW index on embedding column for cosine similarity

### Ollama (Local LLM + Embeddings)
- Chat model: `llama3.1:8b`
- Embedding model: `nomic-embed-text` (768 dimensions)
- Zero cloud dependency for ingestion and local inference

---

## Data Flow

### Ingestion Pipeline
```
Transcript Repo (.md files)
    │
    ▼
Parse & Extract Metadata (episode title, guest, date, URL)
    │
    ▼
Chunk (paragraph-level, ~500-800 tokens, with overlap)
    │
    ▼
Embed via Ollama nomic-embed-text (768-dim vectors)
    │
    ▼
Upsert into pgvector (hash-based idempotency)
```

### Query Flow
```
User Question
    │
    ▼
Backend /chat endpoint
    │
    ▼
Agent orchestration loop:
    1. LLM decides to call search_transcripts tool
    2. Query embedded via same embedding model
    3. Top-k cosine similarity search in pgvector
    4. Relevant chunks returned to LLM with metadata
    5. LLM generates grounded, cited response
    6. (Optional) LLM calls generate_essay tool
    7. Response returned with citations and artifacts
    │
    ▼
Frontend renders response + artifacts
```

---

## Key Architectural Decisions

### ADR-001: Agent Layer — Claude Agent SDK

**Decision**: Use the Anthropic Claude Agent SDK (`claude-agent-sdk`) as the primary agent layer implementation.

**Context**: The assignment specifies the Claude Agent SDK. The SDK provides `@tool` decorator for custom tool definitions, `create_sdk_mcp_server` for bundling tools, and `ClaudeAgentOptions` for configuration.

**Rationale**: Direct assignment requirement. The SDK supports custom tools via MCP which can be used for retrieval and essay generation.

**Fallback**: If the Claude Agent SDK cannot support the RAG architecture (e.g., it requires the Claude Code CLI binary, doesn't support custom-only tool sets, or conflicts with the Ollama provider swap), fall back to the standard `anthropic` Python SDK with native tool-use. Document the specific blocker.

**Status**: Implementation pending — will verify SDK capabilities in Phase 3.

### ADR-002: Database — PostgreSQL with pgvector (Direct)

**Decision**: Use a plain `pgvector/pgvector:pg16` Docker image with SQLAlchemy + asyncpg, not the full self-hosted Supabase stack.

**Context**: Supabase self-hosted requires 15+ containers (auth, realtime, storage, etc.) that are unnecessary for this single-user app.

**Rationale**: Same underlying technology (PostgreSQL + pgvector), dramatically simpler to reproduce. One container vs fifteen. SQLAlchemy provides the ORM and async support we need.

**Trade-off**: No Supabase dashboard, but we don't need it — all data access is via the API.

### ADR-003: Embedding Model — nomic-embed-text via Ollama

**Decision**: Use `nomic-embed-text` through Ollama for all embedding operations.

**Context**: 768-dimension vectors, 8192 token context window, runs locally via Ollama.

**Rationale**: Zero cloud dependency for ingestion. Same model used at both ingest-time and query-time ensures consistent embeddings.

**Configuration**: Behind the provider-swap interface so a cloud embedding provider could be substituted later.

### ADR-004: HTML Artifact Security

**Decision**: Sanitize HTML server-side using `nh3` (Rust-based, Python-bound HTML sanitizer) before passing to `st.components.v1.html`.

**Context**: Streamlit's HTML component renders HTML in an iframe but does NOT enforce a script-blocking sandbox on its own. Malicious `<script>` tags would execute.

**Mitigation**: All HTML content is passed through `nh3.clean()` on the backend/frontend before rendering. This strips `<script>`, `<iframe>`, `onclick`, and other dangerous elements server-side.

**Verification**: Test with `<script>alert('xss')</script>` payload — must be visibly neutralized.

### ADR-005: Ship 30 for 30 — Extended Format

**Decision**: Implement Ship 30 for 30 essay at ~1250 words using structural principles of the format, not the original ~250-word Atomic Essay length.

**Context**: The assignment specifies ~1250 words. The original Ship 30 format targets ~250-word Atomic Essays for social media.

**Rationale**: Assignment requirement takes precedence. We retain the structural principles (hook headline, 1/3/1 rhythm, structured main points, singular takeaway) but scale to the longer format.

### ADR-006: Provider Swap Architecture

**Decision**: Single `LLMProvider` abstract interface with `AnthropicProvider` and `OllamaProvider` implementations. Configuration via `LLM_PROVIDER` env var.

**Context**: The app must support both Anthropic Claude (cloud) and Ollama (local) with no branching in business logic.

**Design**:
```python
class LLMProvider(ABC):
    async def chat(self, messages, tools, system_prompt) -> LLMResponse
    async def embed(self, text) -> list[float]

def get_provider(provider_name: str) -> LLMProvider
```

**Rationale**: Clean separation of concerns. Business logic calls `provider.chat()` without knowing which backend is used.

---

## Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Frontend | Streamlit | latest |
| Backend | FastAPI | latest |
| Agent | Claude Agent SDK (primary) / Anthropic SDK (fallback) | latest |
| Database | PostgreSQL + pgvector | 16 |
| ORM | SQLAlchemy (async) | 2.x |
| Embeddings | nomic-embed-text via Ollama | latest |
| Local LLM | llama3.1:8b via Ollama | latest |
| Cloud LLM | Anthropic Claude | claude-sonnet-4-20250514 |
| HTML Sanitizer | nh3 | latest |
| Deployment | Docker Compose | latest |
