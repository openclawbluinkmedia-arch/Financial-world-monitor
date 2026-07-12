# FIOS Roadmap

## Phase 1 — Foundation (Current)

- [x] Modular-monolith monorepo structure
- [x] FastAPI backend with 14 modules
- [x] Next.js frontend with Tailwind
- [x] Docker Compose for Postgres (pgvector) + Redis
- [x] Model abstraction layer with multi-provider support
- [x] Local CPU embeddings (sentence-transformers, BAAI/bge-m3)
- [x] Health-check endpoints
- [x] Alembic migrations
- [x] Basic test suite

## Phase 2 — Core Features

- [ ] Auth: JWT login, registration, RBAC
- [ ] Tenants: multi-tenant CRUD + isolation
- [ ] Sources: configure data sources (SEC filings, news, etc.)
- [ ] Ingestion: pipeline orchestration with scheduling
- [ ] Documents: upload, parse, chunk, embed, store

## Phase 3 — Intelligence Engine

- [ ] Entities: NER, entity resolution, deduplication
- [ ] Events: extract events from documents/news
- [ ] Evidence: vector search over evidence corpus
- [ ] Graph: entity-relationship graph construction
- [ ] Impact: event-to-portfolio impact scoring
- [ ] Alerts: configurable alert rules & notifications

## Phase 4 — Production Hardening

- [ ] Audit: comprehensive audit logging
- [ ] Rate limiting & DDOS protection
- [ ] Backup & disaster recovery
- [ ] Prometheus/Grafana monitoring
- [ ] Terraform deployment scripts
- [ ] End-to-end encryption options

## Phase 5 — Integrations

- [ ] WorldMonitor integration (GDELT/ACLED)
- [ ] OpenBB Platform integration
- [ ] Custom data source SDK
- [ ] MCP server for AI tool calling
