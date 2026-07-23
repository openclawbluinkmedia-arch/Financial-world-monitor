"use client";

import { useEffect, useState, useCallback } from "react";
import StatCard from "./components/StatCard";
import ImpactBadge from "./components/ImpactBadge";
import ConfidenceBar from "./components/ConfidenceBar";
import LiveIndicator from "./components/LiveIndicator";

interface HealthData {
  status: string;
  mode: string;
  services: Record<string, { status: string; detail: string | null }>;
}

interface EventSummary {
  id: string;
  event_id: string;
  event_type: string;
  factual_summary: string;
  timestamp: string;
  geography: string;
  impact_direction: string;
  impact_horizon: string;
  confidence: number;
  sectors: string[];
}

interface SourceStat {
  source_name: string;
  total_items: number;
  mock_items: number;
  health_status: string;
}

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
  } catch {
    return ts;
  }
}

export default function HomePage() {
  const [health, setHealth] = useState<HealthData | null>(null);
  const [events, setEvents] = useState<EventSummary[]>([]);
  const [sources, setSources] = useState<SourceStat[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchAll = useCallback(async () => {
    try {
      const [h, e, s] = await Promise.all([
        fetch("/api/health").then((r) => r.json()),
        fetch("/api/intelligence/events?page_size=10").then((r) => r.json()),
        fetch("/api/evidence/stats/sources").then((r) => r.json()),
      ]);
      setHealth(h);
      setEvents(e.items || []);
      setSources(s || []);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
  }, [fetchAll]);

  // Live polling every 45s
  useEffect(() => {
    const interval = setInterval(fetchAll, 45000);
    return () => clearInterval(interval);
  }, [fetchAll]);

  const totalItems = sources.reduce((sum, s) => sum + s.total_items, 0);
  const mockItems = sources.reduce((sum, s) => sum + s.mock_items, 0);
  const healthySources = sources.filter(
    (s) => s.health_status === "healthy"
  ).length;

  return (
    <div className="page-container">
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-xl font-bold text-fg">Dashboard</h1>
          <p className="text-sm text-fg-dim mt-0.5">
            System overview and recent intelligence
          </p>
        </div>
        <LiveIndicator />
      </div>

      {/* Stat cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
        <StatCard
          label="System Status"
          value={health?.status || "—"}
          accent={health?.status === "ok" ? "green" : health?.status === "degraded" ? "amber" : "red"}
          secondary={health?.mode ? `Mode: ${health.mode}` : undefined}
        />
        <StatCard
          label="Evidence Items"
          value={totalItems}
          accent="blue"
          secondary={`${mockItems} mock`}
          mono
        />
        <StatCard
          label="Data Sources"
          value={sources.length}
          accent="purple"
          secondary={`${healthySources} healthy`}
          mono
        />
        <StatCard
          label="Intelligence Events"
          value={events.length}
          accent="cyan"
          secondary="Last 24h"
          mono
        />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Map anchor */}
        <div className="card p-4">
          <h2 className="section-title mb-3">Geographic Coverage</h2>
          <div className="flex items-center justify-center h-48 bg-surface-card rounded-lg border border-surface-border">
            <div className="text-center text-fg-dim">
              <svg className="w-16 h-16 mx-auto mb-2 opacity-40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="text-xs">India • Global</p>
              <p className="text-2xs text-fg-dim mt-1">Map view coming soon</p>
            </div>
          </div>
        </div>

        {/* Recent Events Feed */}
        <div>
          <h2 className="section-title">Recent Intelligence Events</h2>
          <div className="space-y-2">
            {loading ? (
              <>
                {[1, 2, 3, 4, 5].map((i) => (
                  <div key={i} className="card p-4 animate-pulse">
                    <div className="h-4 bg-surface-hover rounded w-3/4 mb-2" />
                    <div className="h-3 bg-surface-hover rounded w-1/2" />
                  </div>
                ))}
              </>
            ) : events.length === 0 ? (
              <div className="card p-6 text-center text-fg-dim text-sm">
                No intelligence events yet. Data ingestion may still be running.
              </div>
            ) : (
              events.map((ev) => (
                <div key={ev.id} className="card p-3 hover:bg-surface-hover transition-colors">
                  <div className="flex items-start justify-between gap-2 mb-1">
                    <p className="text-sm font-medium text-fg leading-snug line-clamp-2">
                      {ev.factual_summary}
                    </p>
                    <ImpactBadge direction={ev.impact_direction} />
                  </div>
                  <div className="flex items-center gap-2 text-2xs text-fg-dim">
                    <span className="badge-blue">{ev.event_type.replace("_", " ")}</span>
                    <span>{relativeTime(ev.timestamp)}</span>
                    <span>{ev.geography}</span>
                    <span className="ml-auto font-mono">{Math.round(ev.confidence * 100)}%</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>
      </div>

      {/* Data Sources Status */}
      <div className="mt-6">
        <h2 className="section-title">Data Source Health</h2>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3 mt-3">
          {loading ? (
            <>
              {[1, 2, 3, 4, 5, 6].map((i) => (
                <div key={i} className="card p-4 animate-pulse">
                  <div className="h-4 bg-surface-hover rounded w-1/2" />
                </div>
              ))}
            </>
          ) : sources.length === 0 ? (
            <div className="card p-6 text-center text-fg-dim text-sm col-span-full">
              No source data available.
            </div>
          ) : (
            sources.map((s) => {
              const healthColor =
                s.health_status === "healthy"
                  ? "badge-green"
                  : s.health_status === "degraded"
                    ? "badge-amber"
                    : "badge-red";
              return (
                <div key={s.source_name} className="card p-3">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-sm font-medium text-fg">
                      {s.source_name}
                    </span>
                    <span className={`text-2xs ${healthColor}`}>
                      {s.health_status}
                    </span>
                  </div>
                  <div className="flex items-center gap-3 text-2xs text-fg-dim">
                    <span>{s.total_items} items</span>
                    {s.mock_items > 0 && (
                      <span className="text-accent-amber">
                        {s.mock_items} mock
                      </span>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* System Health Details */}
      {health && (
        <div className="mt-6">
          <h2 className="section-title">System Services</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3 mt-3">
            {Object.entries(health.services || {}).map(([name, svc]) => (
              <div key={name} className="card p-3">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-sm font-medium text-fg">{name}</span>
                  <span
                    className={`text-2xs ${
                      svc.status === "ok"
                        ? "badge-green"
                        : svc.status === "degraded"
                          ? "badge-amber"
                          : "badge-red"
                    }`}
                  >
                    {svc.status}
                  </span>
                </div>
                {svc.detail && (
                  <p className="text-2xs text-fg-dim truncate">{svc.detail}</p>
                )}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
