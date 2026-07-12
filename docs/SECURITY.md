# Security

## Tenets

1. **Privacy-first**: All customer data stays on self-hosted infrastructure.
   No evidence text is ever sent to third-party AI APIs.
2. **Encryption at rest**: Database encryption is managed at the storage layer.
3. **Encryption in transit**: All inter-service communication uses TLS in
   production deployments.

## Authentication & Authorization

- JWT-based authentication using `python-jose`.
- Passwords hashed with bcrypt via `passlib`.
- Token expiry configurable via `ACCESS_TOKEN_EXPIRE_MINUTES`.
- Multi-tenant isolation enforced at the database query level.

## AI Security

- **Embeddings**: Always run locally on CPU via sentence-transformers.
  The `BAAI/bge-m3` model never sends data to any external API.
- **Reasoning LLM**:
  - `DEPLOYMENT_MODE=dev`: Uses NVIDIA NIM (primary) and OpenRouter
    (fallback). For development and demo on **public/synthetic data only**.
  - `DEPLOYMENT_MODE=customer`: Self-hosted vLLM endpoint. No external API
    calls. This is the only mode approved for real customer data.

## API Security

- All API routes (except `/api/health` and `/docs`) require authentication.
- CORS is configurable and locked down in production.
- Rate limiting should be applied at the reverse proxy level (nginx, Caddy).
