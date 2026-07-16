"use client";

import { useEffect, useState } from "react";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import ConfidenceBar from "../components/ConfidenceBar";

interface ServiceStatus {
  status: string;
  detail: string | null;
}

interface HealthData {
  status: string;
  mode: string;
  uptime_seconds?: number;
  services: Record<string, ServiceStatus>;
}

function formatDuration(seconds?: number): string {
  if (!seconds) return "—";
  const d = Math.floor(seconds / 86400);
  const h = Math.floor((seconds % 86400) / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  const parts: string[] = [];
  if (d > 0) parts.push(`${d}d`);
  if (h > 0) parts.push(`${h}h`);
  parts.push(`${m}m`);
  return parts.join(" ");
}

export default function HealthPage() {
  const [data, setData] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="page-container">
      <PageHeader
        title="System Health"
        subtitle="Backend service status and diagnostics"
        actions={
          <button
            onClick={() => window.location.reload()}
            className="btn-secondary"
          >
            Refresh
          </button>
        }
      />

      {error && (
        <div className="card p-4 mb-6 border-l-accent-red border-l-2">
          <p className="text-sm text-accent-red">Error: {error}</p>
        </div>
      )}

      {!data && !error && (
        <div className="card p-8 text-center text-fg-dim text-sm">
          Loading...
        </div>
      )}

      {data && (
        <>
          {/* Overall status */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
            <StatCard
              label="Overall Status"
              value={data.status.toUpperCase()}
              accent={
                data.status === "ok"
                  ? "green"
                  : data.status === "degraded"
                    ? "amber"
                    : "red"
              }
            />
            <StatCard
              label="Mode"
              value={data.mode}
              accent="blue"
            />
            <StatCard
              label="Uptime"
              value={formatDuration(data.uptime_seconds)}
              accent="purple"
            />
            <StatCard
              label="Services"
              value={Object.keys(data.services || {}).length}
              accent="cyan"
              mono
              secondary={`${
                Object.values(data.services || {}).filter(
                  (s) => s.status === "ok"
                ).length
              } healthy`}
            />
          </div>

          {/* Service cards */}
          <h2 className="section-title">Services</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {Object.entries(data.services || {}).map(([name, svc]) => {
              const statusColor =
                svc.status === "ok"
                  ? "bg-accent-green"
                  : svc.status === "degraded"
                    ? "bg-accent-amber"
                    : "bg-accent-red";
              const pct =
                svc.status === "ok"
                  ? 100
                  : svc.status === "degraded"
                    ? 50
                    : 0;

              return (
                <div key={name} className="card p-4">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-sm font-medium text-fg capitalize">
                      {name}
                    </span>
                    <span
                      className={`text-2xs badge ${
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
                  <ConfidenceBar
                    label="Availability"
                    value={pct / 100}
                  />
                  {svc.detail && (
                    <p className="text-2xs text-fg-dim mt-2 truncate" title={svc.detail}>
                      {svc.detail}
                    </p>
                  )}
                </div>
              );
            })}
          </div>
        </>
      )}
    </div>
  );
}
