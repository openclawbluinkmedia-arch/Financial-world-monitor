# QUICKSTART

## Prerequisites

- Python 3.11+
- Docker Desktop
- 16GB RAM (dev) or 24GB+ VRAM GPU (prod self-host)

## 1. Environment

```bash
cp .env.example .env
```

Edit `.env`:
```env
DEPLOYMENT_MODE=dev
DATABASE_URL=postgresql+asyncpg://fios:fios_secret@localhost:5432/fios
SECRET_KEY=generate-a-random-64-char-key-here
NVIDIA_API_KEY=nvapi-your-key    # For dev AI
OPENROUTER_API_KEY=sk-or-v1-your-key  # Fallback
CORS_ORIGINS=http://localhost:3000
```

## 2. Start Infrastructure

```bash
docker compose up -d postgres redis
```

## 3. Install Backend

```bash
cd backend
pip install -e ".[dev]"
alembic upgrade head
```

## 4. Run Backend

```bash
uvicorn app.main:app --reload --port 8000
```

Verify: `curl http://localhost:8000/api/health`

## 5. Create User & Login

```bash
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@fios.dev","password":"demodemo123","display_name":"Demo User"}'

curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"demo@fios.dev","password":"demodemo123"}'
# Returns: {"access_token": "...", "tenant_id": "...", "role": "analyst"}
```

## 6. Upload Portfolio

```bash
# See DEMO.md for a sample portfolio CSV
curl -X POST "http://localhost:8000/api/portfolios/upload?portfolio_name=My%20Portfolio&tenant_id=YOUR_TENANT_ID" \
  -F "file=@portfolio.csv"
```

## 7. Run Frontend (optional)

```bash
cd frontend
npm install
npm run dev
# Opens at http://localhost:3000
```

## Troubleshooting

- `alembic upgrade head` fails: Ensure Postgres is running and `vector` extension is available. Run `CREATE EXTENSION vector;` manually.
- AI calls fail: Check `NVIDIA_API_KEY` or `OPENROUTER_API_KEY` in `.env`
- CORS errors: Ensure `CORS_ORIGINS` includes your frontend URL
