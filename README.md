# The Lenny Growth Assistant

A conversational AI assistant that answers product and growth questions grounded strictly in [Lenny's Podcast](https://www.lennyspodcast.com/) transcripts, with Ship 30 for 30 essay generation and in-app artifact rendering.

## Quick Start

```bash
# 1. Clone the repository
git clone <repo-url>
cd "The Lenny Growth Assistant"

# 2. Copy and configure environment
cp .env.example .env
# Edit .env with your settings (see .env.example for documentation)

# 3. Start all services
docker-compose up -d

# 4. Run transcript ingestion (first time only)
docker-compose exec backend python -m ingestion.ingest

# 5. Open the app
# Frontend: http://localhost:8501
# Backend API: http://localhost:8000/docs
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for full architecture documentation.

| Component | Technology | Port |
|---|---|---|
| Frontend | Streamlit | 8501 |
| Backend | FastAPI | 8000 |
| Database | PostgreSQL + pgvector | 5432 |
| Local LLM | Ollama | 11434 |

## Documentation

- [PRD](docs/PRD.md) — Product requirements, scope, risks
- [Architecture](docs/architecture.md) — System design, ADRs
- [Design](docs/design.md) — UI layout, UX flows
- [Requirements](REQUIREMENTS.md) - Traceability Matrix

## LLM Providers

| Provider | Config | Use Case |
|---|---|---|
| **Ollama** (default) | `LLM_PROVIDER=ollama` | Local inference, zero cloud dependency |
| **Anthropic Claude** | `LLM_PROVIDER=anthropic` | Higher quality, requires API key |

## Development

To develop locally without Docker:

```bash
# 1. Create a local virtual environment
python -m venv .venv
# Activate on Windows:
.\.venv\Scripts\Activate.ps1
# Activate on Mac/Linux:
source .venv/bin/activate

# 2. Install dependencies
pip install -r backend/requirements.txt -r frontend/requirements.txt -r ingestion/requirements.txt pytest

# 3. Run the tests
pytest tests/ -v
```

## License

This project is a take-home assignment. Transcript data sourced from [ChatPRD/lennys-podcast-transcripts](https://github.com/ChatPRD/lennys-podcast-transcripts).
