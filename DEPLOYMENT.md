# FIOS Deployment Guide

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│  Oracle Cloud ARM64 VM (Ubuntu 22.04 / 24.04)           │
│                                                          │
│  ┌──────────┐  ┌─────────┐  ┌─────────────────────────┐ │
│  │ Postgres │  │  Redis  │  │  Backend (uvicorn)       │ │
│  │   :5432  │  │  :6379  │  │  :8000                   │ │
│  │  pgvector│  │  redis  │  │  FastAPI + APScheduler   │ │
│  └──────────┘  └─────────┘  └─────────────────────────┘ │
│                                          │               │
│                                  0.0.0.0:8000           │
└──────────────────────────────────────────────────────────┘
         │
         │ API calls over HTTPS
         ▼
┌──────────────────────┐
│  Vercel (Frontend)   │
│  Next.js             │
│  NEXT_PUBLIC_API_URL │
└──────────────────────┘
```

## Prerequisites

- An Oracle Cloud Always Free account
- A Vercel account (hobby tier is fine)

---

## 1. Create the Oracle ARM64 Instance

1. Sign in to [OCI Console](https://cloud.oracle.com)
2. Create a VM instance:
   - **Image**: Canonical Ubuntu 24.04 (or 22.04) Minimal
   - **Shape**: VM.Standard.A1.Flex (ARM64, 4 OCPUs, 24 GB RAM — Always Free)
   - **Boot volume**: 200 GB (Always Free)
   - **SSH key**: Add your public key
3. Under **Networking**, note the public IP and note the subnet.

### Open port 8000 in OCI Security List

1. Go to **Networking → Virtual Cloud Networks** → your VCN → Security Lists
2. Click the default security list → **Add Ingress Rule**:
   - Source CIDR: `0.0.0.0/0`
   - Destination Port Range: `8000`
   - Protocol: TCP
   - Description: FIOS Backend API

### Open port 8000 in VM firewall

```bash
ssh ubuntu@<YOUR_VM_PUBLIC_IP>

# Install ufw if not present
sudo apt update && sudo apt install -y ufw

sudo ufw allow 22/tcp
sudo ufw allow 8000/tcp
sudo ufw --force enable
```

---

## 2. Install Docker

```bash
curl -fsSL https://get.docker.com | sudo bash
sudo usermod -aG docker $USER
newgrp docker
```

---

## 3. Clone and Configure

```bash
git clone https://github.com/openclawbluinkmedia-arch/Financial-world-monitor.git fios
cd fios

cp .env.production.example .env
nano .env   # fill in your API keys, secrets, and Vercel domain
```

Required variables in `.env`:

| Variable | Description |
|---|---|
| `DEPLOYMENT_MODE` | `dev` for NVIDIA+OpenRouter, `customer` for vLLM |
| `NVIDIA_API_KEY` | NVIDIA NIM API key (dev mode) |
| `OPENROUTER_API_KEY` | OpenRouter API key (dev mode fallback) |
| `SECRET_KEY` | 64-char random key for JWT signing |
| `CORS_ORIGINS` | Comma-separated: `http://localhost:3000,https://your-project.vercel.app` |
| `DATABASE_URL` | Auto-configured for Docker (postgres service) |
| `REDIS_URL` | Auto-configured for Docker (redis service) |

Generate a secure SECRET_KEY:

```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

---

## 4. Deploy the Backend

```bash
docker compose -f docker-compose.prod.yml up -d
```

Check logs:

```bash
docker compose -f docker-compose.prod.yml logs -f
```

Verify health:

```bash
curl http://<YOUR_VM_PUBLIC_IP>:8000/api/health
```

You should see:
```json
{"status":"ok","mode":"dev","services":{"postgres":{"status":"ok"},"redis":{"status":"ok"}}}
```

---

## 5. Deploy the Frontend to Vercel

1. Push the repo to GitHub (or connect Vercel directly)
2. In Vercel Dashboard → **Add New Project** → Import your repo
3. Set **Root Directory** to `frontend`
4. Add environment variable:
   - `NEXT_PUBLIC_API_URL` = `http://<YOUR_VM_PUBLIC_IP>:8000`
5. Click **Deploy**

Vercel auto-detects the `vercel.json` and Next.js framework — no additional config needed.

---

## 6. Verify the Full Stack

1. Open the Vercel URL in your browser
2. Confirm the dashboard loads and shows live data
3. Check that ingestion jobs are running:
   ```bash
   curl http://<YOUR_VM_PUBLIC_IP>:8000/api/ingestion/connectors/health
   ```
4. Each connector should report health status, last run time, and consecutive failures

---

## Maintenance

### View scheduler logs

```bash
docker compose -f docker-compose.prod.yml logs -f backend
```

### Trigger a manual ingestion

```bash
curl -X POST http://<YOUR_VM_PUBLIC_IP>:8000/api/ingestion/run/gdelt
```

### Update the deployment

```bash
cd fios
git pull
docker compose -f docker-compose.prod.yml up -d --build
```

### Stop everything

```bash
docker compose -f docker-compose.prod.yml down
```

---

## Resource Limits

The VM has 24 GB RAM and 4 OCPUs. The production compose file sets:

| Service | Memory limit |
|---|---|
| Postgres | 2 GB |
| Redis | 512 MB |
| Backend | 4 GB |

Remaining ~17.5 GB is available for OS caches and the sentence-transformers model cache.

---

## Security Notes

- Postgres and Redis bind to `127.0.0.1` — not exposed externally
- Only port `8000` is open for the backend API
- Use a reverse proxy (Caddy / Nginx) with TLS for production internet-facing use
- Rotate `SECRET_KEY` and API keys regularly
