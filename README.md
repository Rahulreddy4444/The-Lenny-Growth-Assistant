# 🎙️ The Lenny Growth Assistant

A full-stack, AI-powered conversational web application that answers product and growth questions grounded strictly in [Lenny's Podcast](https://www.lennyspodcast.com/) transcripts, with Ship 30 for 30 essay generation and in-app artifact rendering.

Built for the **Forward Deployed Engineer** Take-Home Assessment.

---

## 📑 Table of Contents
- [Quick Start](#-quick-start)
- [Architecture & Tech Stack](#-architecture--tech-stack)
- [Flexible LLM Configuration](#-flexible-llm-configuration)
- [Deliverables & Documentation](#-deliverables--documentation)
- [Manual Test Plan](#-manual-test-plan)
- [Automated Testing](#-automated-testing)
- [Troubleshooting](#-troubleshooting)

---

## 🚀 Quick Start

### 1. One-Command Docker Startup (Recommended)
```bash
# 1. Clone the repository
git clone <repo-url>
cd "The Lenny Growth Assistant"

# 2. Configure environment
cp .env.example .env

# 3. Start the full stack
docker-compose up -d --build

# 4. Ingest transcripts into pgvector (first time only)
docker-compose exec backend python -m ingestion.ingest
```

- **Frontend UI:** [http://localhost:8501](http://localhost:8501)
- **FastAPI Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

### 2. Local Development Startup
```bash
# 1. Start Database & Ollama via Docker
docker-compose up -d postgres ollama

# 2. Setup Virtual Environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1   # Windows
# source .venv/bin/activate    # Mac/Linux

# 3. Install Dependencies
pip install -r backend/requirements.txt -r frontend/requirements.txt -r ingestion/requirements.txt pytest

# 4. Ingest Transcripts
python -m ingestion.ingest

# 5. Start Backend & Frontend
# Terminal 1:
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
# Terminal 2:
streamlit run frontend/app.py
```

---

## 🏗️ Architecture & Tech Stack

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

- **Backend**: FastAPI with async SQLAlchemy 2.0 and Pydantic validation contracts.
- **Agent Layer**: Claude Agent SDK integration with fallback to standard tool-use loop.
- **Database**: PostgreSQL with `pgvector` extension and HNSW cosine similarity index.
- **Frontend**: Streamlit with two-column layout, session persistence, and artifact rendering.
- **Security**: Server-side HTML sanitization with `nh3` to block XSS and malicious scripts.

---

## 🔄 Flexible LLM Configuration

The application allows seamless switching of the underlying LLM provider in `.env` without modifying code:

| Provider | Setting in `.env` | Description |
| :--- | :--- | :--- |
| **Ollama** (Local Demo) | `LLM_PROVIDER=ollama` | Local offline inference with `llama3.1:8b` & `nomic-embed-text`. |
| **Groq** (Fast Cloud) | `LLM_PROVIDER=groq` | Ultra-fast cloud inference with `qwen/qwen3.6-27b` or `openai/gpt-oss-120b`. |
| **Anthropic** (Cloud) | `LLM_PROVIDER=anthropic` | High-reasoning inference with `claude-sonnet-4-20250514`. |

---

## 📚 Deliverables & Documentation

All deliverables required by the Forward Deployed Engineer specification are provided:

1. [PRD.md](PRD.md) (`docs/PRD.md`) — User discovery brief, success metrics, assumptions, scope, risks.
2. [architecture.md](architecture.md) (`docs/architecture.md`) — System topology, DB schema, data flows, ADRs.
3. [design.md](design.md) (`docs/design.md`) — UI/UX principles, layout, interaction states, and accessibility.
4. [REQUIREMENTS.md](REQUIREMENTS.md) — Complete Requirements Traceability Matrix.
5. [agent-transcripts/](agent-transcripts/) — Logged agent reasoning traces and failure corrections.

---

## 🧪 Manual Test Plan

1. **Grounded Question & Citation Test:**
   - Ask: *"What are Brian Chesky's key product insights?"*
   - Verify: Response cites the specific Brian Chesky episode, timestamps, and includes clickable YouTube links.
2. **Out-of-Scope Gaps Test:**
   - Ask: *"Who won the 2022 FIFA World Cup?"*
   - Verify: Assistant explicitly states that this is not covered in Lenny's Podcast transcripts.
3. **Ship 30 for 30 Essay Skill:**
   - Ask: *"Turn your previous answer into a Ship 30 for 30 essay."*
   - Verify: Side-by-side artifact viewer opens displaying a structured Markdown essay with headline hook, bullet takeaways, and bold highlights.
4. **Session Switching Test:**
   - Click `+ New Session`, ask a different question, and click between sessions in the sidebar to verify conversation history preservation.
5. **HTML Sanitization Security Test:**
   - Ask: *"Generate an HTML card with a button and a `<script>` tag."*
   - Verify: HTML renders in the artifact viewer with any `<script>` tags stripped by `nh3`.

---

## 🤖 Automated Testing

Run the full pytest suite (27 unit and integration tests):

```bash
pytest tests/ -v
```

---

## 🔧 Troubleshooting

- **Port Conflict on 5432:** If a local PostgreSQL instance is running on your host machine, `docker-compose.yml` maps PostgreSQL to host port `5433` to prevent collisions.
- **Ollama Models Downloading:** On first startup, the Ollama container pulls `nomic-embed-text` and `llama3.1:8b`. Check progress via `docker-compose logs -f ollama`.
- **Groq Rate Limits (429):** The backend includes automatic backoff and retry logic with token-optimized prompt chunking.
