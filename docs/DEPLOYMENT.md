# Deployment Guide

## Option 1: Local Dev

See [QUICKSTART.md](QUICKSTART.md).

## Option 2: Docker Compose Self-Host

```bash
# 1. Clone & configure
git clone <repo> && cd fios
cp .env.example .env
# Edit .env: set SECRET_KEY, DB passwords

# 2. Start all services
docker compose -f infra/docker-compose.yml up -d

# 3. Run migrations
docker compose exec backend alembic upgrade head

# 4. Verify
curl http://localhost:8000/api/health
```

**Services started:**
- `postgres` (pgvector) — port 5432
- `redis` — port 6379
- `backend` (FastAPI) — port 8000
- `frontend` (Next.js) — port 3000

## Option 3: Private Cloud / On-Prem (Production)

### Architecture

```
                     ┌─────────────┐
                     │   LB/Proxy  │  TLS termination
                     └──────┬──────┘
                    ┌───────┴────────┐
                    │  FastAPI x N   │  Horizontal scale
                    └───────┬────────┘
           ┌────────────────┼────────────────┐
     ┌─────┴─────┐   ┌─────┴─────┐   ┌──────┴──────┐
     │ Postgres  │   │   Redis   │   │    vLLM     │
     │ (pgvector)│   │  (cache)  │   │  (GPU node) │
     └───────────┘   └───────────┘   └─────────────┘
```

### vLLM Setup

```bash
# On GPU node:
docker run --gpus all -p 8001:8000 \
  -e HF_TOKEN=hf_your_token \
  vllm/vllm-openai:latest \
  --model Qwen/Qwen3.5-397B-A17B \
  --tensor-parallel-size 1 \
  --gpu-memory-utilization 0.90 \
  --max-model-len 32768 \
  --dtype bfloat16
```

### Environment for Production

```env
DEPLOYMENT_MODE=customer
DATABASE_URL=postgresql+asyncpg://user:password@db-host:5432/fios
VLLM_BASE_URL=http://gpu-node:8001/v1
VLLM_MODEL_SLUG=Qwen/Qwen3.5-397B-A17B
SECRET_KEY=<random-64-char>
CORS_ORIGINS=https://app.yourdomain.com
LOG_LEVEL=INFO
REDIS_URL=redis://redis-host:6379/0
```

### Resource Requirements

| Component | Spec |
|-----------|------|
| Backend nodes | 4 vCPU, 16GB RAM (x2 for HA) |
| PostgreSQL | 4 vCPU, 16GB RAM, 100GB SSD |
| GPU node | 1x A10G/A100-40/L40S, 64GB RAM |
| Redis | 2 vCPU, 4GB RAM |

## Migrations

```bash
# Generate new migration after model changes
alembic revision --autogenerate -m "description"
# Apply
alembic upgrade head
# Rollback
alembic downgrade -1
```

## Monitoring

- Health: `GET /api/health` — returns postgres + redis status
- Prometheus metrics: Available at `/metrics` (future)
- Structured logs to stdout — collect via your log aggregator
