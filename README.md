# FIOS — Financial Intelligence Operating System

Privacy-first, self-hostable B2B financial-intelligence platform for Indian equities.

## Architecture

```
User → FastAPI Backend → Intelligence Pipeline → Events → Portfolio Impact Engine
                    ↓                          ↑
             PostgreSQL (pgvector) ← Evidence from RSS/API/Scrapers
                    ↓
    Auth (JWT) → Tenant Isolation → Audit Log → Results
```

## Quick Start

```bash
cp .env.example .env  # Edit secrets
docker compose up -d   # Start Postgres + Redis
pip install -e "backend/[dev]"
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

See [QUICKSTART.md](docs/QUICKSTART.md) for full setup.

## Key Features

- **Portfolio Impact**: Upload CSV portfolios → get event-driven exposure classification
- **6 Exposure Levels**: DIRECTLY_AFFECTED, INDIRECTLY_AFFECTED, POSSIBLE_BENEFICIARY, POSSIBLE_NEGATIVE_EXPOSURE, UNCERTAIN, NO_MATERIAL_EVIDENCE
- **AI Pipeline**: Event classification + entity extraction + impact reasoning + validation
- **Evidence Grounding**: Every claim cites sources; citations validated against DB
- **Tenant Isolation**: All data scoped by tenant_id at query level
- **Privacy First**: No PII collection; local embeddings; customer mode uses self-hosted LLM
- **Audit Trail**: All portfolio operations logged to audit_logs table

## Models

See [docs/MODEL_STRATEGY.md](docs/MODEL_STRATEGY.md) and [docs/MODEL_EVALUATION.md](docs/MODEL_EVALUATION.md).

## License

FIOS is proprietary. Dependencies include Apache 2.0 (Qwen, sentence-transformers), MIT (bge-m3, GLiNER), and AGPLv3 (WorldMonitor, OpenBB — accessed via REST only, no code linkage).
