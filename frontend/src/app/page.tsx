"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchApi, getEvents, getHealth, getSourceStats, getConnectorHealth, type IntelligenceEvent, type SourceStat, type ConnectorHealthItem } from "@/lib/api";
import { ComposableMap, Geographies, Geography, Marker } from "react-simple-maps";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";
const POLL_MS = 30000;
const STALE_MS = 40000;

const COUNTRY_CENTROIDS: Record<string, [number, number]> = {
  IN: [20.5937, 78.9629], US: [37.0902, -95.7129], EU: [50.8503, 4.3517],
  GLOBAL: [20, 0], UK: [55.3781, -3.4360], JP: [36.2048, 138.2529],
  CN: [35.8617, 104.1954], BR: [-14.2350, -51.9253], AU: [-25.2744, 133.7751],
  RU: [61.5240, 105.3188], DE: [51.1657, 10.4515], FR: [46.6034, 1.8883],
  SG: [1.3521, 103.8198], AE: [23.4241, 53.8478], KR: [35.9078, 127.7669],
  ZA: [-30.5595, 22.9375], NG: [9.0820, 8.6753],
};

function geoCenter(geo: string): [number, number] {
  return COUNTRY_CENTROIDS[geo.toUpperCase().trim()] || [20, 0];
}

function fmtTime(ts: string): string {
  try {
    const d = Date.now() - new Date(ts).getTime();
    const m = Math.floor(d / 60000);
    if (m < 1) return "now";
    if (m < 60) return `${m}m`;
    return `${Math.floor(m / 60)}h`;
  } catch { return ts; }
}

function clockStr(): string {
  return new Date().toLocaleTimeString("en-IN", { hour12: false, hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function dotColor(direction?: string): string {
  if (!direction) return "#6b7080";
  const d = direction.toLowerCase();
  if (d === "positive" || d === "beneficiary") return "#22c55e";
  if (d === "negative" || d === "negative exposure") return "#ef4444";
  if (d === "mixed" || d === "uncertain") return "#f59e0b";
  return "#6b7080";
}

interface AffectedStock {
  ticker: string;
  company_name: string;
  sector: string;
  industry: string;
  direct_or_indirect: string;
  positive_or_negative: string;
  confidence: number;
  reasoning: string;
  evidence_ids: string[];
}

export default function TerminalPage() {
  const [clock, setClock] = useState(clockStr());
  const [stale, setStale] = useState(false);
  const [events, setEvents] = useState<IntelligenceEvent[]>([]);
  const [connectors, setConnectors] = useState<ConnectorHealthItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [newIds, setNewIds] = useState<Set<string>>(new Set());

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchAll = useCallback(async () => {
    setError(null);
    const oldIds = new Set(events.map((e) => e.id));
    try {
      const [eData, cData] = await Promise.all([
        getEvents({ page_size: "30" }),
        getConnectorHealth(),
      ]);
      setEvents(eData.items || []);
      setConnectors(cData || []);
      const freshIds = new Set((eData.items || []).map((e) => e.id));
      const added = [...freshIds].filter((id) => !oldIds.has(id));
      if (added.length > 0) {
        setNewIds(new Set(added));
        setTimeout(() => setNewIds(new Set()), 3000);
      }
      setStale(false);
    } catch (e: any) {
      setError(e.message || "Failed to fetch");
    } finally {
      setLoading(false);
    }
  }, [events]);

  useEffect(() => { fetchAll(); const iv = setInterval(fetchAll, POLL_MS); return () => clearInterval(iv); }, []);

  useEffect(() => { const iv = setInterval(() => setClock(clockStr()), 1000); return () => clearInterval(iv); }, []);

  useEffect(() => {
    if (!stale) {
      const t = setTimeout(() => setStale(true), STALE_MS);
      return () => clearTimeout(t);
    }
  }, [stale, events]);

  const selected = events.find((e) => e.id === selectedId) || events[0] || null;
  const stocks: AffectedStock[] = (selected as any)?.affected_stocks || [];

  const todayCount = events.filter((e) => {
    try { return Date.now() - new Date(e.timestamp).getTime() < 86400000; } catch { return false; }
  }).length;

  return (
    <div className="h-screen w-screen bg-[#0a0b10] text-fg flex flex-col overflow-hidden font-sans">
      {!apiUrl && (
        <div className="px-3 py-1.5 bg-accent-amber-bg border-b border-accent-amber-border text-2xs text-accent-amber text-center shrink-0">
          ⚠ NEXT_PUBLIC_API_URL not set — using http://localhost:8000
        </div>
      )}

      {/* ─── TOP BAR ───────────────────────────────────────────── */}
      <div className="shrink-0 h-9 flex items-center justify-between px-4 border-b border-surface-border bg-[#0d0f16] text-2xs text-fg-dim">
        <div className="flex items-center gap-4">
          <span className="text-xs font-bold text-fg tracking-wider uppercase">FIOS</span>
          <span className="font-mono text-fg-muted">{clock}</span>
          <span className="text-fg-faint">|</span>
          <span className="font-mono text-fg-dim">{todayCount}</span>
          <span className="text-fg-faint">today</span>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-1.5">
            {connectors.length === 0 ? (
              <span className="text-fg-faint">—</span>
            ) : (
              connectors.slice(0, 8).map((c) => (
                <span key={c.connector} className={`inline-block w-1.5 h-1.5 rounded-full ${c.status === "healthy" ? "bg-accent-green" : c.status === "degraded" ? "bg-accent-amber" : "bg-accent-red"}`}
                  title={`${c.connector}: ${c.status}`} />
              ))
            )}
          </div>
          <span className={`inline-block w-1.5 h-1.5 rounded-full ${stale ? "bg-accent-amber" : "bg-accent-green animate-pulse"}`} />
          <span className="font-mono text-fg-muted">{stale ? "stale" : "live"}</span>
          <span className="text-fg-faint">|</span>
          <span className="text-fg-faint">
            {loading ? "…" : events.length > 0 ? fmtTime(events[0].timestamp) : "—"}
          </span>
        </div>
      </div>

      {/* ─── MAIN CONTENT ──────────────────────────────────────── */}
      <div className="flex-1 flex min-h-0 relative">

        {/* World Map background layer */}
        <div className="absolute inset-0 pointer-events-none opacity-[0.15]">
          <ComposableMap projection="geoMercator" projectionConfig={{ scale: 130, center: [20, 20] }} style={{ width: "100%", height: "100%" }}>
            <Geographies geography={GEO_URL}>
              {({ geographies }) => geographies.map((geo) => (
                <Geography key={geo.rsmKey} geography={geo}
                  style={{ default: { fill: "#1a1d27", stroke: "#2e3140", strokeWidth: 0.3, outline: "none" }, hover: {}, pressed: {} }} />
              ))}
            </Geographies>
            {(events || []).filter((e) => e.lat != null && e.lng != null).map((ev) => (
              <Marker key={ev.id} coordinates={[ev.lng!, ev.lat!]}>
                <circle r={ev.confidence ? Math.max(3, ev.confidence * 8) : 4} fill={dotColor(ev.impact_direction)} opacity={0.35} className="animate-ping" style={{ animationDuration: "2.5s" }} />
                <circle r={ev.confidence ? Math.max(2, ev.confidence * 5) : 3} fill={dotColor(ev.impact_direction)} opacity={0.85} />
              </Marker>
            ))}
          </ComposableMap>
        </div>

        {/* ─── LEFT RAIL — EVENT FEED ─────────────────────────── */}
        <div className="w-[340px] shrink-0 border-r border-surface-border bg-[#0a0b10]/80 overflow-y-auto z-10">
          <div className="px-3 py-2 text-2xs text-fg-dim uppercase tracking-wider border-b border-surface-border sticky top-0 bg-[#0a0b10]/90 z-10">
            Live Feed
            {error && <span className="ml-2 text-accent-red normal-case">error</span>}
          </div>

          {loading && events.length === 0 && (
            <div className="space-y-1 p-3">
              {[1,2,3,4,5,6,7,8].map((i) => (
                <div key={i} className="h-14 bg-surface-hover rounded animate-pulse" />
              ))}
            </div>
          )}

          {events.length === 0 && !loading && (
            <div className="p-6 text-center text-fg-dim text-xs">
              No events yet — ingestion has not run
            </div>
          )}

          {events.map((ev) => {
            const isNew = newIds.has(ev.id);
            const isSelected = ev.id === selectedId;
            return (
              <div key={ev.id}
                className={`px-3 py-2 border-b border-surface-border cursor-pointer transition-colors
                  ${isSelected ? "bg-surface-hover border-l-2 border-l-accent-blue" : "hover:bg-surface-hover border-l-2 border-l-transparent"}
                  ${isNew ? "bg-accent-blue-bg/40" : ""}`}
                onClick={() => setSelectedId(ev.id)}>
                <div className="flex items-start justify-between gap-2">
                  <p className={`text-xs leading-snug line-clamp-2 flex-1 ${isSelected ? "text-fg" : "text-fg-muted"}`}>
                    {ev.factual_summary}
                  </p>
                  <span className="text-2xs text-fg-dim font-mono shrink-0 mt-0.5">{fmtTime(ev.timestamp)}</span>
                </div>
                <div className="flex items-center gap-2 mt-1 text-2xs text-fg-dim">
                  <span className="text-accent-cyan">{ev.geography}</span>
                  <span className="text-fg-faint">•</span>
                  <span>{ev.event_type?.replace("_", " ")}</span>
                  <span className="ml-auto font-mono">{ev.confidence != null ? Math.round(ev.confidence * 100) : "?"}%</span>
                </div>
              </div>
            );
          })}
        </div>

        {/* ─── RIGHT RAIL — INDIAN MARKET IMPACT ──────────────── */}
        <div className="flex-1 overflow-y-auto z-10 p-4">
          {!selected ? (
            <div className="flex items-center justify-center h-full text-fg-dim text-sm">
              {loading ? "Loading..." : "Click an event to see Indian market impact"}
            </div>
          ) : (
            <div className="max-w-2xl">
              {/* Event headline */}
              <div className="mb-4">
                <div className="flex items-start gap-3">
                  <span className={`mt-1 w-2.5 h-2.5 rounded-full shrink-0 ${dotColor(selected.impact_direction)}`} />
                  <div>
                    <h1 className="text-sm font-semibold text-fg leading-snug">{selected.factual_summary}</h1>
                    <div className="flex items-center gap-3 mt-1.5 text-2xs text-fg-dim">
                      <span className="badge-blue">{selected.event_type?.replace("_", " ")}</span>
                      <span>{new Date(selected.timestamp).toLocaleString()}</span>
                      <span>{selected.geography}</span>
                      <span className="font-mono">{Math.round(selected.confidence * 100)}% confidence</span>
                    </div>
                  </div>
                </div>
              </div>

              {error && (
                <div className="mb-3 px-3 py-2 bg-accent-red-bg border border-accent-red-border rounded text-2xs text-accent-red">
                  {error}
                </div>
              )}

              {/* Affected Sectors */}
              <div className="mb-4">
                <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">Affected Sectors</p>
                {selected.sectors && selected.sectors.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {selected.sectors.map((s: string) => (
                      <span key={s} className="px-2 py-0.5 rounded text-2xs font-medium bg-surface-alt text-fg-muted border border-surface-border-light">
                        {s}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="text-2xs text-fg-dim">No sector data</p>
                )}
              </div>

              {/* Affected Stocks */}
              <div className="mb-4">
                <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">
                  Affected Stocks <span className="text-fg-faint normal-case">({stocks.length})</span>
                </p>
                {stocks.length > 0 ? (
                  <div className="space-y-1">
                    {stocks.map((s) => (
                      <div key={s.ticker} className="px-3 py-2 rounded bg-surface-card border border-surface-border">
                        <div className="flex items-center justify-between">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-fg font-mono">{s.ticker}</span>
                            <span className="text-2xs text-fg-dim">{s.company_name}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className={`text-2xs px-1.5 py-0.5 rounded ${s.direct_or_indirect === "direct" ? "bg-accent-blue-bg text-accent-blue border border-accent-blue-border" : "bg-surface-alt text-fg-dim border border-surface-border"}`}>
                              {s.direct_or_indirect === "direct" ? "DIRECT" : "INDIRECT"}
                            </span>
                            <span className={`text-2xs px-1.5 py-0.5 rounded ${s.positive_or_negative === "positive" ? "bg-accent-green-bg text-accent-green border border-accent-green-border" : "bg-accent-red-bg text-accent-red border border-accent-red-border"}`}>
                              {s.positive_or_negative === "positive" ? "POSITIVE" : s.positive_or_negative === "negative" ? "NEGATIVE" : "UNCERTAIN"}
                            </span>
                            <span className="text-2xs font-mono text-fg-dim">{Math.round(s.confidence * 100)}%</span>
                          </div>
                        </div>
                        <div className="flex items-center gap-3 mt-1 text-2xs text-fg-dim">
                          {s.sector && <span className="badge-neutral">{s.sector}</span>}
                          {s.reasoning && <span className="truncate flex-1">{s.reasoning}</span>}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="text-2xs text-fg-dim">No stock impact data for this event</p>
                )}
              </div>

              {/* Causal Chain */}
              {(selected as any).causal_chain && (selected as any).causal_chain.length > 0 && (
                <div className="mb-4">
                  <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">Causal Chain</p>
                  <div className="space-y-0.5">
                    {(selected as any).causal_chain.map((step: any, i: number) => (
                      <div key={i} className="flex items-start gap-2 px-3 py-2 bg-surface-card rounded border border-surface-border">
                        <span className="text-2xs text-fg-dim font-mono shrink-0 mt-0.5">{step.step || i + 1}.</span>
                        <div className="flex-1 min-w-0">
                          <p className="text-xs text-fg">{step.cause}</p>
                          <div className="flex items-center gap-1.5 mt-0.5">
                            <span className="text-fg-dim text-2xs">→</span>
                            <p className="text-xs text-fg-muted">{step.effect}</p>
                          </div>
                          <div className="flex items-center gap-2 mt-1">
                            <span className={`text-2xs px-1 py-0.5 rounded ${step.type === "verified" ? "bg-accent-green-bg text-accent-green" : step.type === "inferred" ? "bg-accent-amber-bg text-accent-amber" : "bg-surface-alt text-fg-dim"}`}>
                              {(step.type || "uncertain").toUpperCase()}
                            </span>
                            {step.confidence && <span className="text-2xs text-fg-dim">{step.confidence}</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Citations */}
              {stocks.length > 0 && stocks.some((s) => s.evidence_ids && s.evidence_ids.length > 0) && (
                <div className="mb-4">
                  <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">Source Evidence</p>
                  <div className="flex flex-wrap gap-1">
                    {Array.from(new Set(stocks.flatMap((s) => s.evidence_ids || []))).map((eid) => (
                      <span key={eid} className="font-mono text-2xs text-fg-dim bg-surface-card px-1.5 py-0.5 rounded border border-surface-border">
                        {eid.length > 16 ? eid.slice(0, 16) + "…" : eid}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
