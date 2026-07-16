# WorldMonitor Integration

## Overview

[WorldMonitor](https://github.com/koala73/worldmonitor) is a self-hostable
service that aggregates global events from GDELT and ACLED. FIOS consumes
WorldMonitor as a **separate, external service** — its codebase remains
architecturally independent. **No WorldMonitor code is copied into the FIOS
backend or frontend.**

## License

**WorldMonitor is licensed under AGPL-3.0-only.**

| Field | Value |
|---|---|
| License | AGPL-3.0-only (GNU Affero General Public License v3.0) |
| Copyright | © 2024-2026 Elie Habib |
| License file | https://github.com/koala73/worldmonitor/blob/main/LICENSE |

Because FIOS consumes WorldMonitor exclusively via its REST API (over HTTP)
and never incorporates, links, or derives from WorldMonitor's source code,
AGPL copyleft obligations do not apply to FIOS itself.

## Deployment

WorldMonitor runs as a **separate Docker container** alongside the FIOS stack.

### docker-compose (recommended)

A `worldmonitor` service is defined in `infra/docker-compose.yml`:

```yaml
worldmonitor:
  build:
    context: ../worldmonitor        # cloned repo path
    dockerfile: Dockerfile
  ports:
    - "127.0.0.1:3001:8080"         # local-only access
  environment:
    NODE_ENV: production
```

First clone the repository:

```bash
cd FIOS
git clone https://github.com/koala73/worldmonitor.git worldmonitor
```

Then start the stack:

```bash
docker compose up -d worldmonitor
```

WorldMonitor will be available at `http://localhost:3001`.

### Standalone (without Docker)

```bash
git clone https://github.com/koala73/worldmonitor.git
cd worldmonitor
npm install
npm run dev
```

Opens on http://localhost:3000.

## Architecture

```
┌──────────┐   HTTP REST    ┌──────────────┐
│   FIOS   │───────────────▶│ WorldMonitor  │
│ Backend  │◀───────────────│ (separate     │
│          │                │  service)     │
└──────────┘                └──────────────┘
```

- WorldMonitor runs as its own Docker container or process.
- FIOS connects via WorldMonitor's REST API (endpoints under `/api/v1/`).
- No WorldMonitor code is imported into the FIOS backend.
- FIOS's `WorldMonitorConnector` polls WorldMonitor's event endpoints.

## Configuration

Add WorldMonitor's URL to `.env`:

```env
WORLDMONITOR_BASE_URL=http://worldmonitor:8080
WORLDMONITOR_API_KEY=
```

The connector is configured in `backend/app/modules/ingestion/connectors/world_monitor.py`.

## FIOS Connector

The `WorldMonitorConnector` polls the following endpoints:

| Endpoint | Path | Description |
|---|---|---|
| events | `/api/v1/events` | All global events |
| finance | `/api/v1/finance/events` | Finance-specific events |
| geopolitics | `/api/v1/geopolitics/events` | Geopolitical events |

See `backend/app/modules/ingestion/connectors/world_monitor.py` for the full
implementation.
