# Data Sources

## OpenBB Platform

[OpenBB Platform](https://github.com/OpenBB-finance/OpenBB) provides
financial data from hundreds of sources. It runs as a **separate AGPLv3
service** behind a REST API and MCP interface.

### ⚠ License Warning

OpenBB is licensed under AGPLv3. **Do not import any OpenBB code into the
FIOS backend.** OpenBB must run as a completely separate service. FIOS
communicates with it exclusively via its REST API or MCP interface.

### Configuration

```
OPENBB_BASE_URL=http://openbb:8000
OPENBB_API_KEY=...
```

## Other Sources

| Source       | Integration Method      | License Concern? |
|-------------|------------------------|------------------|
| WorldMonitor | REST / MCP             | AGPL (separate)  |
| OpenBB       | REST / MCP             | AGPL (separate)  |
| Custom APIs  | Configurable via code  | None             |

All source integrations follow the same pattern: the data provider runs as an
independent service, and FIOS consumes it through a well-defined API boundary.
