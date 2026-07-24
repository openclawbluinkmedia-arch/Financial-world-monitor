"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchApi, getHealth, getConnectorHealth, type HealthData, type ConnectorHealthItem } from "@/lib/api";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import LiveIndicator from "../components/LiveIndicator";

function relativeTime(ts: string): string {
  try {
    const diff = Date.now() - new Date(ts).getTime();
    const m = Math.floor(diff / 60000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    return `${Math.floor(m / 60)}h ago`;
  } catch { return ts; }
}

export default function HealthPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<HealthData | null>(null);
  const [connectors, setConnectors] = useState<ConnectorHealthItem[]>([]);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, c] = await Promise.all([
        getHealth(),
        getConnectorHealth(),
      ]);
      setHealth(h);
      setConnectors(c || []);
    } catch (e: any) {
      setError(e.message || "Failed to load health data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const allOk = health?.status === "ok";
  const healthyConnectors = connectors.filter((c) => c.status === "healthy").length;

  return (
    <div className="page-container">
      {!apiUrl && (
        <div className="mb-4 px-4 py-3 bg-accent-amber-bg border border-accent-amber-border rounded-lg text-sm text-accent-amber text-center">
          ⚠ NEXT_PUBLIC_API_URL is not configured. Using fallback http://localhost:8000
        </div>
      )}

      <PageHeader title="System Health" subtitle="Service status and connector availability"
        actions={
          <>
            <LiveIndicator />
            <button onClick={() => fetchAll()} className="btn-primary">Refresh</button>
          </>
        }
      />

      {error && (
        <div className="mb-4 card p-4 border-l-2 border-l-accent-red">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-accent-red">Failed to load</p>
              <p className="text-xs text-fg-muted mt-1">{error}</p>
            </div>
            <button onClick={fetchAll} className="btn-primary text-xs shrink-0">Retry</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        {loading && !health ? (
          [1,2,3].map((i) => <div key={i} className="card p-4 animate-pulse"><div className="h-3 bg-surface-hover rounded w-1/3 mb-2" /><div className="h-6 bg-surface-hover rounded w-1/2" /></div>)
        ) : (
          <>
            <StatCard label="Overall Status" value={health?.status || "—"} accent={allOk ? "green" : "red"} secondary={`Mode: ${health?.mode || "—"}`} />
            <StatCard label="Services" value={health?.services ? Object.keys(health.services).length : "—"} accent="blue" mono secondary={`${allOk ? "All healthy" : "Issues detected"}`} />
            <StatCard label="Connectors" value={`${healthyConnectors}/${connectors.length}`} accent={healthyConnectors === connectors.length && connectors.length > 0 ? "green" : healthyConnectors > 0 ? "amber" : "red"} mono />
          </>
        )}
      </div>

      <div className="mb-6">
        <h2 className="section-title">Backend Services</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
          {loading && !health ? (
            [1,2,3,4,5,6].map((i) => <div key={i} className="card p-3 animate-pulse"><div className="h-4 bg-surface-hover rounded w-2/3" /></div>)
          ) : !health ? (
            <div className="card p-6 text-center text-fg-dim text-sm col-span-full">No health data available</div>
          ) : (
            Object.entries(health.services || {}).map(([name, svc]: [string, any]) => (
              <div key={name} className="card p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-fg">{name}</span>
                  <span className={`text-2xs ${svc.status === "ok" ? "badge-green" : svc.status === "degraded" ? "badge-amber" : "badge-red"}`}>{svc.status}</span>
                </div>
                <div className="flex items-center gap-2 mt-1">
                  <div className={`h-1.5 flex-1 rounded-full bg-surface-alt overflow-hidden`}>
                    <div className={`h-full rounded-full transition-all ${svc.status === "ok" ? "bg-accent-green w-full" : svc.status === "degraded" ? "bg-accent-amber w-1/2" : "bg-accent-red w-1/4"}`} />
                  </div>
                </div>
                {svc.detail && <p className="text-2xs text-fg-dim truncate mt-1">{svc.detail}</p>}
              </div>
            ))
          )}
        </div>
      </div>

      <div>
        <h2 className="section-title">Connector Status</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
          {loading && connectors.length === 0 ? (
            [1,2,3,4,5,6].map((i) => <div key={i} className="card p-3 animate-pulse"><div className="h-4 bg-surface-hover rounded w-2/3" /></div>)
          ) : connectors.length === 0 ? (
            <div className="card p-6 text-center text-fg-dim text-sm col-span-full">No connectors found — run ingestion</div>
          ) : (
            connectors.map((c) => (
              <div key={c.connector} className="card p-3">
                <div className="flex items-center justify-between mb-1">
                  <div className="flex items-center gap-2">
                    <span className={`inline-block w-2 h-2 rounded-full ${c.status === "healthy" ? "bg-accent-green" : c.status === "degraded" ? "bg-accent-amber" : "bg-accent-red"}`} />
                    <span className="text-sm font-medium text-fg capitalize">{c.connector.replace("_", " ")}</span>
                  </div>
                  <span className={`text-2xs ${c.status === "healthy" ? "badge-green" : c.status === "degraded" ? "badge-amber" : "badge-red"}`}>{c.status}</span>
                </div>
                <div className="text-2xs text-fg-dim space-y-0.5 mt-1 ml-4">
                  {c.last_run_at && <p>Last run: {relativeTime(c.last_run_at)}</p>}
                  {c.last_success_at && <p>Last success: {relativeTime(c.last_success_at)}</p>}
                  {c.consecutive_failures > 0 && <p className="text-accent-red">{c.consecutive_failures} consecutive failure(s)</p>}
                  {c.last_error && <p className="text-accent-red truncate" title={c.last_error}>Error: {c.last_error}</p>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}
