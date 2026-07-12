# WorldMonitor Integration

## Overview

[WorldMonitor](https://github.com/koala73/worldmonitor) is a self-hostable
service that aggregates global events from GDELT and ACLED. FIOS consumes
WorldMonitor as a **separate, external service** — its codebase remains
architecturally independent.

## Architecture

```
┌──────────┐    HTTP / MCP    ┌──────────────┐
│   FIOS   │────────────────▶│ WorldMonitor  │
│ Backend  │◀────────────────│ (separate     │
│          │                 │  service)     │
└──────────┘                 └──────────────┘
```

- WorldMonitor runs as its own Docker container or process.
- FIOS connects via WorldMonitor's REST API or MCP interface.
- No WorldMonitor code is imported into the FIOS backend.

## License

**Verify WorldMonitor's license** before reusing any of its code. As of this
writing, the repository uses an AGPL-3.0 license. If FIOS were to incorporate
WorldMonitor code, it would need to comply with AGPL terms. The recommended
approach is to keep WorldMonitor as a completely separate service and consume
it via API only.

## Configuration

Add WorldMonitor's URL to `.env`:

```
WORLDMONITOR_BASE_URL=http://worldmonitor:8080
WORLDMONITOR_API_KEY=...
```
