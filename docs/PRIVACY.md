# Privacy & Data Handling

## Core Principle

FIOS is designed **privacy-first**. No customer portfolio data ever leaves your
infrastructure unless explicitly configured.

## Data Residency

| Data | Storage | External Transmission |
|------|---------|----------------------|
| Portfolio holdings | Local PostgreSQL | Never |
| Evidence content | Local PostgreSQL | Never |
| Embeddings | Local memory (CPU) | Never |
| AI inference text | Local PostgreSQL | DEV mode only to NVIDIA/OpenRouter |
| User credentials | Local PostgreSQL (bcrypt-hashed) | Never |
| Audit logs | Local PostgreSQL | Never |

## DEV Mode (Default)

- Event text and entity data are sent to **NVIDIA NIM API** (primary) or
  **OpenRouter API** (fallback) for LLM inference.
- **This includes portfolio-relevant text** (sectors, company names, event
  descriptions).
- Use **only synthetic or public data** in DEV mode.
- Embeddings are computed **locally on CPU** — never sent externally.

## CUSTOMER Mode (Production)

- **No external API calls**. All inference goes to a self-hosted vLLM endpoint.
- Requires an NVIDIA GPU with >=24GB VRAM running vLLM serving Qwen3.6-27B.
- See [DEPLOYMENT.md](DEPLOYMENT.md) for on-prem setup.

## Data Protection

- **No PII collection**: No SSN, Aadhaar, PAN, phone, or email fields in
  business models (email only in auth/User model).
- **Encryption at rest**: Rely on PostgreSQL TDE or filesystem encryption.
- **Encryption in transit**: TLS required in production.
- **Audit trail**: Every portfolio operation is logged with actor, action, and
  timestamp.
- **Secure deletion**: Portfolio holdings can be overwritten before deletion
  (secure=true flag).
- **Configurable retention**: Set via `RETENTION_DAYS` env var (future).

## Tenant Isolation

- All data queries include `tenant_id` filter.
- No cross-tenant retrieval possible at the SQL query level.
- RBAC enforced via JWT token claims.

## Logging

- Structured logging (JSON) — no portfolio data in log messages.
- Logs contain: request path, duration, status code, user_id, tenant_id.
- Logs do NOT contain: holding data, event content, AI output text.
- Configure log level via `LOG_LEVEL` env var.
