# Product Requirements Document — The Lenny Growth Assistant

## Overview

A conversational web application that answers product and growth questions grounded strictly in Lenny's Podcast transcripts. The assistant can turn any grounded answer into a Ship 30 for 30–style essay and render Markdown/HTML artifacts in an in-app viewer beside the chat.

## User

A single evaluator assessing a Forward Deployed Engineer take-home. No multi-user requirements.

## Problem Statement

Lenny's Podcast has 200+ episodes with deep product, growth, and strategy insights from top operators. Finding specific, citable answers across this corpus requires manually searching and reading transcripts. There is no grounded, source-cited search tool that synthesizes answers from the transcripts while maintaining fidelity to the source material.

## Success Metrics

1. An evaluator can ask a product/growth question and receive a cited, grounded answer within 60 seconds.
2. The assistant explicitly refuses to answer when transcripts don't support a question rather than hallucinating.
3. A grounded answer can be transformed into a structured ~1250-word essay with one click.
4. Markdown and HTML artifacts render in-app beside the chat without navigation.
5. The full stack starts with one `docker-compose up` command from a clean clone.

## Assumptions

- Evaluator has Docker and Docker Compose installed.
- Evaluator has Ollama installed locally OR will use the Docker Compose Ollama service.
- For Anthropic provider: evaluator has a valid API key.
- Transcripts are publicly available at https://github.com/ChatPRD/lennys-podcast-transcripts.
- Evaluator machine can run at least an 8B parameter model via Ollama (fallback: smaller model).

---

## Scope: In

| Feature | Description |
|---|---|
| **RAG chat** | Conversational Q&A grounded in Lenny's Podcast transcripts with source citations |
| **Ship 30 for 30 essay** | Transform a grounded answer into a ~1250-word structured essay |
| **Artifact viewer** | In-app Markdown/HTML rendering beside the chat |
| **Session management** | Create, list, and switch between chat sessions |
| **Provider switching** | Toggle between Anthropic Claude and Ollama (local LLM) |
| **Transcript ingestion** | One-time CLI script to chunk, embed, and store transcripts |
| **Docker Compose deploy** | One-command startup for the full stack |
| **Health endpoint** | System status for DB, Ollama, and LLM provider |

## Scope: Out (Locked Scope Cuts)

| Cut | Reason |
|---|---|
| **No auth / no multi-user accounts** | Single evaluator, session-based only — auth adds complexity with zero evaluation value |
| **No reranking or hybrid search** | Top-k cosine similarity over pgvector is sufficient for the transcript corpus size (~200 episodes) |
| **No streaming responses** | Not required unless trivial to add — batch responses are acceptable for the demo |
| **No fine-tuning or custom embedding training** | Out of scope; off-the-shelf nomic-embed-text provides adequate retrieval quality |
| **No live-refresh ingestion pipeline** | Ingestion runs as a one-time/on-demand script — transcripts update infrequently |
| **No Kubernetes / complex infra** | Docker Compose is sufficient for single-machine evaluation |
| **No real-time collaboration** | Single user, single session at a time |

---

## Risks

| Risk | Impact | Mitigation |
|---|---|---|
| **Hallucination** | Agent fabricates information not in transcripts | System prompt enforces strict grounding; must cite source chunks; explicit "not covered" for unsupported questions |
| **Latency** | Local LLM (8B) may be slow on CPU-only machines | Document expected latency; recommend GPU; Anthropic provider as fast alternative |
| **Cost** | Anthropic API usage incurs per-token costs | Default to Ollama (free, local); Anthropic is opt-in |
| **Local model quality** | llama3.1:8b may produce lower quality answers than Claude | Clearly show active provider in UI; evaluate both and document quality gap |
| **Data leakage** | Transcripts sent to cloud LLM | Ollama keeps all data local; Anthropic usage sends chunks to API — document this trade-off |
| **Unsafe HTML rendering** | XSS via HTML artifacts in Streamlit | Server-side sanitization via `nh3` before rendering; scripts stripped; documented in architecture.md |
| **Ollama unavailability** | Ollama not installed or model not pulled | Health endpoint checks Ollama status; graceful error message; documented setup steps |
| **Database connection failure** | PostgreSQL unreachable | Health endpoint checks DB; structured error responses; retry logic |

---

## Known Limitations

_Updated as development progresses._

- Ship 30 for 30 format adapted to ~1250 words (original format is ~250-word Atomic Essays); structural principles retained at longer length.
- HTML artifact security relies on server-side `nh3` sanitization since Streamlit's `st.components.v1.html` does not enforce a script-blocking sandbox on its own.
