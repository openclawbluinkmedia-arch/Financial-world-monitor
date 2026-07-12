# FIOS Architecture

## Overview

FIOS is a modular-monolith B2B financial-intelligence platform designed for privacy-first,
self-hosted deployment. The system is split into two deployable units (frontend + backend)
that share a single Postgres database and Redis cache.

```
┌──────────┐     ┌──────────┐     ┌──────────┐
│ Frontend │────▶│ Backend  │────▶│ Postgres │
│ (Next.js)│     │ (FastAPI)│     │ (pgvector)│
└──────────┘     │          │     └──────────┘
                 │ Modules: │     ┌──────────┐
                 │ auth     │────▶│ Redis    │
                 │ tenants  │     └──────────┘
                 │ sources  │
                 │ ...      │     ┌──────────────────┐
                 │ ai       │────▶│ NVIDIA NIM (dev) │
                 └──────────┘     │ OpenRouter (dev) │
                                  │ vLLM (customer)  │
                                  └──────────────────┘
```

## Backend Modules

| Module       | Purpose                                      |
|-------------|----------------------------------------------|
| auth        | User authentication & authorization          |
| tenants     | Multi-tenant organizations                   |
| sources     | Data source configuration                    |
| ingestion   | Data ingestion pipeline management           |
| documents   | Document storage & retrieval                 |
| events      | Global/local event management                |
| entities    | Entity resolution & management               |
| evidence    | Evidence collection & vector storage         |
| ai          | Model abstraction layer (generate, embed,    |
|             | rerank, classify)                            |
| impact      | Impact scoring & analysis                    |
| graph       | Entity relationship graph                    |
| portfolios  | Portfolio management                         |
| alerts      | Alert generation & routing                   |
| audit       | Audit logging                                |

## Design Decisions

- **Modular monolith**: Modules communicate via Python imports and database
  transactions. No inter-service RPC until a clear scaling need emerges.
- **Async-first**: FastAPI async handlers throughout, with asyncpg and aioredis.
- **Embeddings on CPU**: sentence-transformers with BAAI/bge-m3 runs locally
  to keep all evidence text off third-party networks and guarantee identical
  vector spaces across dev and customer deployments.
- **Model abstraction**: The `backend/app/ai/` layer provides a unified
  interface (`generate`, `embed`, `rerank`, `classify`) with swappable
  adapters selected by the `DEPLOYMENT_MODE` env var.
