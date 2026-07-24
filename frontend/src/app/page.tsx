"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchApi, getHealth, getEvents, getSourceStats, getConnectorHealth, type SourceStat, type ConnectorHealthItem, type IntelligenceEvent } from "@/lib/api";
import StatCard from "./components/StatCard";
import ImpactBadge from "./components/ImpactBadge";
import LiveIndicator from "./components/LiveIndicator";
import MapView, { type MapEvent } from "./components/MapView";

function relativeTime(ts: string): string {
  try {
    const diff = Date.now() - new Date(ts).getTime();
    const m = Math.floor(diff / 60000);
    const h = Math.floor(diff / 3600000);
    const d = Math.floor(diff / 86400000);
    if (m < 1) return "just now";
    if (m < 60) return `${m}m ago`;
    if (h < 24) return `${h}h ago`;
    return `${d}d ago`;
  } catch { return ts; }
}

const COUNTRY_CENTROIDS: Record<string, [number, number]> = {
  IN: [20.5937, 78.9629], US: [37.0902, -95.7129], EU: [50.8503, 4.3517],
  GLOBAL: [20, 0], UK: [55.3781, -3.4360], JP: [36.2048, 138.2529],
  CN: [35.8617, 104.1954], BR: [-14.2350, -51.9253], AU: [-25.2744, 133.7751],
  RU: [61.5240, 105.3188], CA: [56.1304, -106.3468], DE: [51.1657, 10.4515],
  FR: [46.6034, 1.8883], SG: [1.3521, 103.8198], AE: [23.4241, 53.8478],
  SA: [23.8859, 45.0792], CH: [46.8182, 8.2275], HK: [22.3193, 114.1694],
  KR: [35.9078, 127.7669], ZA: [-30.5595, 22.9375], NG: [9.0820, 8.6753],
  OTHER: [20, 0],
};

function geoToLatLng(geo: string): [number, number] {
  const g = geo.toUpperCase().trim();
  return COUNTRY_CENTROIDS[g] || COUNTRY_CENTROIDS.OTHER;
}

export default function HomePage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [health, setHealth] = useState<any>(null);
  const [events, setEvents] = useState<IntelligenceEvent[]>([]);
  const [sources, setSources] = useState<SourceStat[]>([]);
  const [connectors, setConnectors] = useState<ConnectorHealthItem[]>([]);
  const [gdeltFeed, setGdeltFeed] = useState<IntelligenceEvent[]>([]);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [h, e, s, c] = await Promise.all([
        getHealth(),
        getEvents({ page_size: "20" }),
        getSourceStats(),
        getConnectorHealth(),
      ]);
      setHealth(h);
      setEvents(e.items || []);
      setSources(s || []);
      setConnectors(c || []);
      setGdeltFeed((e.items || []).filter((ev: IntelligenceEvent) =>
        ev.source_name?.toLowerCase() === "gdelt" ||
        ev.geography?.toUpperCase() === "GLOBAL"
      ).slice(0, 10));
      setLastUpdated(new Date());
    } catch (e: any) {
      setError(e.message || "Failed to load dashboard data");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  useEffect(() => {
    const interval = setInterval(fetchAll, 60000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const totalItems = sources.reduce((sum, s) => sum + s.total_items, 0);
  const mockItems = sources.reduce((sum, s) => sum + s.mock_items, 0);
  const healthySources = sources.filter((s) => s.health_status === "healthy").length;

  const mapEvents: MapEvent[] = events.map((ev) => {
    const [lat, lng] = geoToLatLng(ev.geography);
    return {
      id: ev.id,
      title: ev.factual_summary,
      lat,
      lng,
      impact_direction: ev.impact_direction,
      confidence: ev.confidence,
      source_name: ev.source_name,
      timestamp: ev.timestamp,
      geography: ev.geography,
    };
  });

  return (
    <div className="page-container">
      {!apiUrl && (
        <div className="mb-4 px-4 py-3 bg-accent-amber-bg border border-accent-amber-border rounded-lg text-sm text-accent-amber text-center">
          ⚠ NEXT_PUBLIC_API_URL is not configured. Using fallback http://localhost:8000
        </div>
      )}

      {error && (
        <div className="mb-4 card p-4 border-l-2 border-l-accent-red">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-medium text-accent-red">Failed to load dashboard</p>
              <p className="text-xs text-fg-muted mt-1">{error}</p>
            </div>
            <button onClick={fetchAll} className="btn-primary text-xs shrink-0">Retry</button>
          </div>
        </div>
      )}

      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-fg">Dashboard</h1>
          <p className="text-sm text-fg-dim mt-0.5">System overview and global intelligence</p>
        </div>
        <LiveIndicator label={lastUpdated ? `Updated ${relativeTime(lastUpdated.toISOString())}` : "Loading"} />
      </div>

      {loading && !health && (
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          {[1, 2, 3, 4].map((i) => (
            <div key={i} className="card p-4 animate-pulse">
              <div className="h-3 bg-surface-hover rounded w-1/3 mb-2" />
              <div className="h-6 bg-surface-hover rounded w-1/2" />
            </div>
          ))}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="System Status"
          value={health?.status || "—"}
          accent={health?.status === "ok" ? "green" : health?.status === "degraded" ? "amber" : "red"}
          secondary={health?.mode != null ? `Mode: ${health.mode}` : undefined}
        />
        <StatCard
          label="Intelligence Events"
          value={events.length}
          accent="cyan"
          secondary="Last 24h"
          mono
        />
        <StatCard
          label="Active Sources"
          value={`${healthySources}/${sources.length}`}
          accent={healthySources === sources.length && sources.length > 0 ? "green" : "amber"}
          secondary={`${totalItems} items`}
        />
        <StatCard
          label="Evidence Items"
          value={totalItems}
          accent="blue"
          secondary={`${mockItems} mock`}
          mono
        />
      </div>

      {error && (
        <div className="card p-6 text-center text-fg-dim text-sm">
          No data yet — run ingestion
        </div>
      )}

      <div className="mb-6 card p-4">
        <div className="flex items-center justify-between mb-3">
          <h2 className="section-title mb-0">Global Event Map</h2>
          <span className="text-2xs text-fg-dim">{mapEvents.length} events mapped</span>
        </div>
        <MapView events={mapEvents} onEventClick={(id) => window.open(`/intelligence`, "_self")} height={380} />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mb-6">
        <div>
          <h2 className="section-title">Global Intelligence Feed</h2>
          <div className="space-y-2 mt-3">
            {loading && gdeltFeed.length === 0 ? (
              [1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="card p-3 animate-pulse">
                  <div className="h-4 bg-surface-hover rounded w-3/4 mb-2" />
                  <div className="h-3 bg-surface-hover rounded w-1/2" />
                </div>
              ))
            ) : gdeltFeed.length === 0 ? (
              <div className="card p-6 text-center text-fg-dim text-sm">
                No global intelligence events yet — run ingestion
              </div>
            ) : (
              gdeltFeed.map((ev) => (
                <div key={ev.id} className="card p-3 hover:bg-surface-hover transition-colors">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <p className="text-sm font-medium text-fg leading-snug line-clamp-2 flex-1">
                      {ev.factual_summary}
                    </p>
                    <ImpactBadge direction={ev.impact_direction} />
                  </div>
                  <div className="flex items-center gap-3 text-2xs text-fg-dim">
                    <span className="badge-blue">{ev.source_name || ev.event_type?.replace("_", " ")}</span>
                    <span>{relativeTime(ev.timestamp)}</span>
                    <span>{ev.geography}</span>
                    {ev.confidence != null && (
                      <span className="font-mono">{Math.round(ev.confidence * 100)}%</span>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        <div>
          <h2 className="section-title">Sector Impact</h2>
          <div className="space-y-2 mt-3">
            {loading && events.length === 0 ? (
              [1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="card p-3 animate-pulse">
                  <div className="h-4 bg-surface-hover rounded w-1/2 mb-2" />
                  <div className="h-3 bg-surface-hover rounded w-1/3" />
                </div>
              ))
            ) : events.length === 0 ? (
              <div className="card p-6 text-center text-fg-dim text-sm">
                No sector impact data yet — run ingestion
              </div>
            ) : (
              events.slice(0, 8).map((ev) => (
                <div key={ev.id} className="card p-3 hover:bg-surface-hover transition-colors">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <p className="text-sm font-medium text-fg leading-snug line-clamp-1 flex-1">
                      {ev.factual_summary}
                    </p>
                    <ImpactBadge direction={ev.impact_direction} />
                  </div>
                  <div className="flex flex-wrap items-center gap-1.5 text-2xs text-fg-dim">
                    {ev.sectors?.slice(0, 3).map((s) => (
                      <span key={s} className="badge-neutral">{s}</span>
                    ))}
                    <span className="ml-auto font-mono">{relativeTime(ev.timestamp)}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      <div className="mb-6">
        <h2 className="section-title">Connector Status</h2>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3 mt-3">
          {loading && connectors.length === 0 ? (
            [1, 2, 3, 4, 5, 6].map((i) => (
              <div key={i} className="card p-3 animate-pulse">
                <div className="h-4 bg-surface-hover rounded w-2/3" />
              </div>
            ))
          ) : connectors.length === 0 ? (
            <div className="card p-6 text-center text-fg-dim text-sm col-span-full">
              No connector data available — run ingestion
            </div>
          ) : (
            connectors.map((c) => {
              const dotColor = c.status === "healthy" ? "bg-accent-green" : c.status === "degraded" ? "bg-accent-amber" : "bg-accent-red";
              return (
                <div key={c.connector} className="card p-3">
                  <div className="flex items-center gap-2 mb-1">
                    <span className={`inline-block w-2 h-2 rounded-full ${dotColor} ${c.status === "healthy" ? "animate-pulse" : ""}`} />
                    <span className="text-sm font-medium text-fg capitalize">{c.connector.replace("_", " ")}</span>
                  </div>
                  <div className="text-2xs text-fg-dim space-y-0.5 ml-4">
                    <span className={c.status === "healthy" ? "badge-green" : c.status === "degraded" ? "badge-amber" : "badge-red"}>
                      {c.status}
                    </span>
                    {c.last_run_at && <p>Last: {relativeTime(c.last_run_at)}</p>}
                    {c.consecutive_failures > 0 && (
                      <p className="text-accent-red">{c.consecutive_failures} failure(s)</p>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {health && (
        <div className="mb-6">
          <h2 className="section-title">System Services</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
            {Object.entries(health.services || {}).map(([name, svc]: [string, any]) => (
              <div key={name} className="card p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-fg">{name}</span>
                  <span className={`text-2xs ${svc.status === "ok" ? "badge-green" : svc.status === "degraded" ? "badge-amber" : "badge-red"}`}>
                    {svc.status}
                  </span>
                </div>
                {svc.detail && <p className="text-2xs text-fg-dim truncate">{svc.detail}</p>}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
