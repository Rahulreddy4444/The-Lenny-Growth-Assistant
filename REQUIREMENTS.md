# Requirements Traceability Matrix

| Requirement | Implementation | File(s) | Test/Verification | Status |
|---|---|---|---|---|
| RAG chat grounded in transcripts | Agent + retrieval service | backend/app/services/agent.py, retrieval.py | test_retrieval.py, manual query | Not started |
| Source citations on answers | Agent system prompt + cited_sources field | backend/app/services/agent.py, models.py | test_retrieval.py | Not started |
| "Not covered" for unsupported questions | Agent system prompt enforcement | backend/app/services/agent.py | Manual test | Not started |
| Ship 30 for 30 essay generation | Essay skill as agent tool | backend/app/services/essay.py | Manual test | Not started |
| Markdown artifact rendering | st.markdown in artifact viewer | frontend/app.py | Manual test | Not started |
| HTML artifact rendering (sanitized) | nh3 + st.components.v1.html | frontend/app.py | XSS test payload | Not started |
| Session management (create/list) | Sessions API + sidebar | backend/app/routers/sessions.py, frontend/app.py | test_sessions.py | Not started |
| Message persistence | Messages table + session history | backend/app/db/models.py | test_sessions.py | Not started |
| Provider swap (anthropic/ollama) | LLM_PROVIDER config + adapter | backend/app/services/llm.py, config.py | test_provider.py | Not started |
| Provider shown in UI | Sidebar display | frontend/app.py | Manual test | Not started |
| Transcript ingestion (idempotent) | CLI ingest script | ingestion/ingest.py | Manual re-run test | Not started |
| Chunk metadata (title, guest, URL) | Chunker with metadata extraction | ingestion/chunker.py | test_retrieval.py | Not started |
| Docker Compose one-command startup | docker-compose.yml | docker-compose.yml | Clean clone test | Not started |
| .env.example documented | All vars with comments | .env.example | Manual review | Done |
| Health endpoint | /health with status checks | backend/app/routers/health.py | curl test | Not started |
| Structured error responses | Pydantic ErrorResponse model | backend/app/models.py | test_api.py | Not started |
| Graceful error handling | Try/catch + structured logging | All backend files | Manual test | Not started |
| No committed secrets | .gitignore + .env.example only | .gitignore | grep for keys | Not started |
| PRD.md with scope cuts | All cuts documented | docs/PRD.md | Manual review | Done |
| architecture.md with decisions | ADRs documented | docs/architecture.md | Manual review | Done |
| design.md | UI design + UX flows | docs/design.md | Manual review | Done |
| Agent transcripts | Conversation logs | agent-transcripts/ | File exists | Not started |
| Automated tests | pytest suite | tests/ | pytest run | Not started |
| README.md | Setup + run instructions | README.md | Manual review | Not started |
| REQUIREMENTS.md traceability | This file | REQUIREMENTS.md | Manual review | In progress |
