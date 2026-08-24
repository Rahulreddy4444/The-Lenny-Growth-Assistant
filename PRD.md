# Product Requirements Document — The Lenny Growth Assistant

> Note: Detailed version maintained in [docs/PRD.md](docs/PRD.md).

## Overview

A conversational web application that answers product and growth questions grounded strictly in Lenny's Podcast transcripts. The assistant can turn any grounded answer into a Ship 30 for 30–style essay and render Markdown/HTML artifacts in an in-app viewer beside the chat.

## User & Problem
- **User**: Product managers, growth leads, founders, and evaluators seeking actionable product/growth advice.
- **Problem**: Finding specific, citable operator advice across 200+ podcast episodes requires manual searching. The assistant provides grounded answers with direct citations to guests, episode titles, timestamps, and YouTube links.

## Success Metrics
1. **Grounded Response Time**: Grounded answer with citations returned in < 60 seconds.
2. **Grounding Accuracy & Hallucination Prevention**: Explicitly states when questions are not covered in the transcript corpus.
3. **Artifact Generation**: One-click transformation into a structured ~1250-word Ship 30 for 30 essay.
4. **Isolated Rendering**: Markdown and sanitized HTML render side-by-side with script blocking.
5. **One-Command Startup**: Fully boots via `docker-compose up -d --build`.

## Assumptions
- Evaluator has Docker & Docker Compose installed.
- Evaluator has Ollama installed locally or will use Docker Compose Ollama service.
- Cloud LLMs (Anthropic Claude, Groq) supported with API key configuration in `.env`.

## Scope In & Out
- **Included**: RAG search with pgvector (cosine similarity), Ship 30 essay generation skill, in-app artifact viewer, session switching, provider swap (Ollama, Anthropic, Groq), health monitoring.
- **Excluded**: Multi-tenant authentication, custom model fine-tuning, complex Kubernetes deployments.

## Risks & Mitigations
- **Hallucination**: System prompt enforcing strict grounding; requires inline source citations.
- **Latency / Rate Limits**: Automatic backoff and retries on API rate limits; lightweight chunk previews.
- **Security / Untrusted HTML**: Server-side HTML sanitization using `nh3` stripping scripts and iframes.
