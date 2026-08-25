# Architecture Document — The Lenny Growth Assistant

## System Architecture

```
┌──────────────────┐       ┌─────────────────┐       ┌───────────────────────┐
│ Streamlit UI     │◄─────►│ FastAPI Backend │◄─────►│ PostgreSQL + pgvector │
│ (Port 8501)      │       │ (Port 8000)     │       │ (Port 5433 / 5432)    │
└──────────────────┘       └────────┬────────┘       └───────────────────────┘
                                    │
                         ┌──────────┴──────────┐
                         │ Provider-Swap Layer │
                         ├─────────────────────┤
                         │ • Ollama (Local)    │
                         │ • Anthropic Claude  │
                         │ • Groq (Cloud)      │
                         └─────────────────────┘
```

## Component Breakdown
1. **Frontend**: Streamlit application with chat interface, session persistence, active provider indicator, and artifact panel.
2. **Backend**: FastAPI with async SQLAlchemy 2.0 and Pydantic schemas (`/health`, `/sessions`, `/chat`).
3. **Agent Layer**: Tool calling loop (`search_transcripts`, `generate_ship30_essay`) with Claude Agent SDK support and multi-provider adapter fallback.
4. **Database & Ingestion**: PostgreSQL with `pgvector`, HNSW cosine index, and chunk-hash idempotent deduplication.
5. **Security**: Server-side HTML sanitization with `nh3` library to neutralize untrusted scripts or malicious HTML tags.
