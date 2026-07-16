# Security

## Tenets

1. **Privacy-first**: All customer data stays on self-hosted infrastructure in
   customer mode. No evidence text sent to third-party AI APIs.
2. **Encryption at rest**: Database encryption managed at storage layer.
3. **Encryption in transit**: TLS required in production.
4. **Tenant isolation**: Every query includes tenant_id filter at DB level.

## Authentication & Authorization

- **JWT-based** authentication via `python-jose` with HS256 signing.
- **Passwords**: bcrypt-hashed via `passlib`.
- **Endpoints**: All routes except `/api/health`, `/api/auth/login`,
  `/api/auth/register`, `/`, and `/docs` require Bearer token.
- **Roles**: `admin` (full access), `analyst` (portfolio + intelligence access).
- **Token expiry**: Configurable via `ACCESS_TOKEN_EXPIRE_MINUTES` (default 60).
- **Dev mode bypass**: When `SECRET_KEY` is the default value and
  `DEPLOYMENT_MODE=dev`, auth is auto-provisioned for local development.

## Multi-Tenant Isolation

- Every portfolio endpoint filters by `tenant_id` in WHERE clause.
- Cross-tenant data retrieval returns HTTP 404 (not 403) to avoid leaking
  existence information.
- Tenant ID is extracted from the JWT token, not from user-supplied params.

## API Security

- **CORS**: Configurable via `CORS_ORIGINS` env var (default:
  `http://localhost:3000`). Never use wildcard with credentials in production.
- **Rate limiting**: Apply at reverse proxy level (nginx, Caddy, Cloudflare).
- **File uploads**: CSV only; validated for content-type, file size (5MB max),
  encoding (UTF-8), and structural rules (weight sum = 100%).
- **Input validation**: All inputs validated via Pydantic schemas with length
  and pattern constraints.

## AI Security

- **Embeddings**: Always local CPU via sentence-transformers. Never external.
- **Reasoning LLM**:
  - DEV mode: NVIDIA NIM (primary) + OpenRouter (fallback) — synthetic data only.
  - CUSTOMER mode: Self-hosted vLLM — no external calls. Only mode for real data.

## Audit Trail

All portfolio operations are logged to `audit_logs` table:
- User ID, action, resource type, resource ID, timestamp
- Includes: portfolio create/update/delete, holding operations, CSV uploads

## Secrets

- `SECRET_KEY` must be a strong random key (64+ chars) in production.
- All secrets come from environment variables, never hardcoded.
- Default DB password `fios_secret` must be changed in production.
- API keys for NVIDIA/OpenRouter set via `.env` only.
