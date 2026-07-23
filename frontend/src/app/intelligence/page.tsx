"use client";

import { useState, useEffect, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import FilterBar from "../components/FilterBar";
import DataTable from "../components/DataTable";
import EventCard from "../components/EventCard";
import ImpactBadge from "../components/ImpactBadge";
import ConfidenceBar from "../components/ConfidenceBar";
import CausalChain from "../components/CausalChain";
import EvidenceCitation from "../components/EvidenceCitation";
import LiveIndicator from "../components/LiveIndicator";

interface IntelligenceEvent {
  id: string;
  event_id: string;
  event_type: string;
  factual_summary: string;
  timestamp: string;
  geography: string;
  impact_direction: string;
  impact_horizon: string;
  confidence: number;
  uncertainty: number;
  sectors: string[];
  industries: string[];
  commodities: string[];
  currencies: string[];
  entities: any[];
  direct_impacts: any[];
  indirect_impacts: any[];
  possible_beneficiaries: any[];
  possible_negative_exposures: any[];
  causal_chain: any[];
  source_ids: string[];
  human_review_required: boolean;
  validation_flags: string[];
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

export default function IntelligencePage() {
  const [events, setEvents] = useState<IntelligenceEvent[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [filters, setFilters] = useState({
    search: "",
    event_type: "",
    impact_direction: "",
    impact_horizon: "",
    geography: "",
    min_confidence: "",
    date_from: "",
    date_to: "",
  });
  const [selected, setSelected] = useState<IntelligenceEvent | null>(null);
  const [stats, setStats] = useState<any>(null);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      const res = await fetch(`/api/intelligence/events?${params}`);
      const data = await res.json();
      setEvents(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  const fetchStats = useCallback(async () => {
    try {
      const res = await fetch("/api/intelligence/stats");
      setStats(await res.json());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
    fetchStats();
  }, [fetchEvents, fetchStats]);

  // Live polling every 45s
  useEffect(() => {
    const interval = setInterval(() => {
      fetchEvents();
      fetchStats();
      setLastUpdated(new Date());
    }, 45000);
    return () => clearInterval(interval);
  }, [fetchEvents, fetchStats]);

  const handleFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleExport = async () => {
    const params = new URLSearchParams({ page_size: "500" });
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    const res = await fetch(`/api/intelligence/events?${params}`);
    const data = await res.json();
    const csv = [
      ["Event ID", "Type", "Summary", "Timestamp", "Geography", "Direction", "Confidence"].join(","),
      ...(data.items || []).map(
        (e: IntelligenceEvent) =>
          [
            e.event_id,
            e.event_type,
            `"${e.factual_summary.replace(/"/g, '""')}"`,
            e.timestamp,
            e.geography,
            e.impact_direction,
            e.confidence.toFixed(2),
          ].join(",")
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `intel-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const EVENT_TYPES = [
    "macro", "earnings", "m_a", "regulatory", "policy",
    "corporate_action", "market_move", "commodity", "currency",
    "geopolitical", "sector", "supply_chain", "esg", "other",
  ];
  const eventTypeOptions = [
    { value: "", label: "All Types" },
    ...EVENT_TYPES.map((t) => ({
      value: t,
      label: t.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase()),
    })),
  ];

  const filterDefs = [
    { key: "search", label: "Search", type: "text" as const, placeholder: "Search summary, entities..." },
    { key: "event_type", label: "Event Type", type: "select" as const, options: eventTypeOptions },
    {
      key: "impact_direction", label: "Direction", type: "select" as const,
      options: [
        { value: "", label: "All" },
        { value: "positive", label: "Positive" },
        { value: "negative", label: "Negative" },
        { value: "neutral", label: "Neutral" },
        { value: "mixed", label: "Mixed" },
      ],
    },
    {
      key: "impact_horizon", label: "Horizon", type: "select" as const,
      options: [
        { value: "", label: "All" },
        { value: "immediate", label: "Immediate (0-1d)" },
        { value: "short_term", label: "Short-term (1-30d)" },
        { value: "medium_term", label: "Medium-term (1-6m)" },
        { value: "long_term", label: "Long-term (6m+)" },
      ],
    },
    { key: "geography", label: "Geography", type: "select" as const,
      options: [
        { value: "", label: "All" },
        { value: "IN", label: "India" },
        { value: "US", label: "US" },
        { value: "EU", label: "EU" },
        { value: "GLOBAL", label: "Global" },
      ],
    },
    {
      key: "min_confidence", label: "Min Confidence", type: "select" as const,
      options: [
        { value: "", label: "All" },
        { value: "0.3", label: "30%" },
        { value: "0.5", label: "50%" },
        { value: "0.7", label: "70%" },
        { value: "0.8", label: "80%" },
        { value: "0.9", label: "90%" },
      ],
    },
    { key: "date_from", label: "From", type: "date" as const },
    { key: "date_to", label: "To", type: "date" as const },
  ];

  const columns = [
    {
      key: "summary",
      label: "Summary",
      render: (row: IntelligenceEvent) => (
        <div className="max-w-sm">
          <p className="text-sm text-fg truncate" title={row.factual_summary}>
            {row.factual_summary}
          </p>
          <p className="text-2xs text-fg-dim truncate mt-0.5">
            {row.entities?.slice(0, 3).map((e: any) => e.text).join(", ")}
            {row.entities?.length > 3 && ` +${row.entities.length - 3}`}
          </p>
        </div>
      ),
    },
    {
      key: "event_type",
      label: "Type",
      render: (row: IntelligenceEvent) => (
        <span className="badge-blue text-2xs">
          {row.event_type.replace("_", " ")}
        </span>
      ),
    },
    {
      key: "timestamp",
      label: "Time",
      render: (row: IntelligenceEvent) => (
        <span className="text-2xs font-mono text-fg-dim">
          {relativeTime(row.timestamp)}
        </span>
      ),
    },
    { key: "geography", label: "Geo", render: (row: IntelligenceEvent) => (
      <span className="text-2xs text-fg-dim">{row.geography}</span>
    )},
    {
      key: "impact_direction",
      label: "Direction",
      render: (row: IntelligenceEvent) => (
        <ImpactBadge direction={row.impact_direction} />
      ),
    },
    {
      key: "confidence",
      label: "Confidence",
      render: (row: IntelligenceEvent) => (
        <span className="font-mono text-sm text-fg">
          {Math.round(row.confidence * 100)}%
        </span>
      ),
    },
    {
      key: "sectors",
      label: "Sectors",
      render: (row: IntelligenceEvent) => (
        <span className="text-2xs text-fg-dim">
          {row.sectors?.slice(0, 2).join(", ")}
          {row.sectors?.length > 2 && ` +${row.sectors.length - 2}`}
        </span>
      ),
    },
    {
      key: "actions",
      label: "",
      render: (row: IntelligenceEvent) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            fetch(`/api/intelligence/events/${row.id}`)
              .then((r) => r.json())
              .then((d) => setSelected({ ...row, ...d }))
              .catch(console.error);
          }}
          className="btn-ghost text-2xs"
        >
          Detail
        </button>
      ),
    },
  ];

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-container">
      <PageHeader
        title="Intelligence Dashboard"
        subtitle={`${total} events — Real-time impact intelligence`}
        actions={
          <>
            <LiveIndicator />
            <button onClick={handleExport} className="btn-secondary">
              Export CSV
            </button>
            <button onClick={() => { fetchEvents(); setLastUpdated(new Date()); }} className="btn-primary">
              Refresh
            </button>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4 mb-6">
        <StatCard label="Total Events" value={total} accent="blue" mono />
        <StatCard
          label="Avg Confidence"
          value={stats?.avg_confidence ? `${Math.round(stats.avg_confidence * 100)}%` : "—"}
          accent="green"
        />
        <StatCard
          label="Validation Rate"
          value={stats?.validation_pass_rate ? `${Math.round(stats.validation_pass_rate * 100)}%` : "—"}
          accent={stats?.validation_pass_rate > 0.7 ? "green" : "amber"}
        />
        <StatCard
          label="Human Review"
          value={stats?.human_review_required ?? "—"}
          accent={stats?.human_review_required > 0 ? "amber" : "green"}
          mono
        />
        <StatCard
          label="Event Types"
          value={stats?.by_type ? Object.keys(stats.by_type).length : "—"}
          accent="purple"
          mono
        />
      </div>

      {/* Filters */}
      <div className="mb-6">
        <FilterBar
          filters={filters}
          definitions={filterDefs}
          onChange={handleFilter}
        />
      </div>

      {/* Table view */}
      <div className="card">
        <div className="card-header">
          <span className="text-sm font-medium text-fg">Intelligence Events</span>
          <select
            value={pageSize}
            onChange={(e) => {
              setPageSize(Number(e.target.value));
              setPage(1);
            }}
            className="text-sm w-auto"
          >
            <option value="25">25 / page</option>
            <option value="50">50 / page</option>
            <option value="100">100 / page</option>
          </select>
        </div>
        <DataTable
          columns={columns}
          data={events}
          loading={loading}
          emptyMessage="No intelligence events found."
        />
        <div className="card-header border-t border-surface-border">
          <span className="text-2xs text-fg-dim">
            Page {page} of {pageCount} ({total} total)
          </span>
          <div className="flex gap-2">
            <button
              onClick={() => setPage(page - 1)}
              disabled={page <= 1}
              className="btn-ghost text-xs disabled:opacity-40"
            >
              Previous
            </button>
            <button
              onClick={() => setPage(page + 1)}
              disabled={page >= pageCount}
              className="btn-ghost text-xs disabled:opacity-40"
            >
              Next
            </button>
          </div>
        </div>
      </div>

      {/* Detail modal */}
      {selected && (
        <div
          className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50"
          onClick={() => setSelected(null)}
        >
          <div
            className="card max-w-4xl w-full max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-header">
              <h3 className="text-sm font-semibold text-fg truncate">
                {selected.factual_summary}
              </h3>
              <button
                onClick={() => setSelected(null)}
                className="text-fg-dim hover:text-fg text-lg leading-none"
              >
                ✕
              </button>
            </div>
            <div className="card-body space-y-5">
              {/* Meta */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div>
                  <p className="text-2xs text-fg-dim">Event ID</p>
                  <p className="font-mono text-xs text-fg-muted">{selected.event_id}</p>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Type</p>
                  <span className="badge-blue text-2xs">{selected.event_type.replace("_", " ")}</span>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Geography</p>
                  <p>{selected.geography}</p>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Timestamp</p>
                  <p className="text-xs">
                    {selected.timestamp ? new Date(selected.timestamp).toLocaleString() : "—"}
                  </p>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Direction</p>
                  <ImpactBadge direction={selected.impact_direction} size="md" />
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Horizon</p>
                  <span className="badge-neutral text-2xs">
                    {selected.impact_horizon.replace("_", " ")}
                  </span>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Confidence</p>
                  <span className="font-mono text-sm text-fg">
                    {Math.round(selected.confidence * 100)}%
                  </span>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Uncertainty</p>
                  <span className="font-mono text-sm text-fg-dim">
                    {Math.round(selected.uncertainty * 100)}%
                  </span>
                </div>
              </div>

              {/* Confidence bar */}
              <div className="fact-box">
                <ConfidenceBar label="Overall Confidence" value={selected.confidence} size="md" />
              </div>

              {/* Factual Summary */}
              <div className="fact-box">
                <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">Factual Summary</p>
                <p className="text-sm text-fg">{selected.factual_summary}</p>
              </div>

              {/* Entities */}
              {selected.entities && selected.entities.length > 0 && (
                <div>
                  <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">
                    Entities ({selected.entities.length})
                  </p>
                  <div className="flex flex-wrap gap-1.5">
                    {selected.entities.map((e: any, i: number) => (
                      <span key={i} className="badge-purple text-2xs">
                        {e.text} ({e.label})
                        {e.resolved?.company_name && ` → ${e.resolved.company_name}`}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Sectors grid */}
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                  <p className="text-2xs text-fg-dim mb-1">Sectors</p>
                  <div className="flex flex-wrap gap-1">
                    {selected.sectors?.map((s, i) => (
                      <span key={i} className="badge-neutral text-2xs">{s}</span>
                    )) || <span className="text-2xs text-fg-dim">—</span>}
                  </div>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim mb-1">Industries</p>
                  <div className="flex flex-wrap gap-1">
                    {selected.industries?.map((s, i) => (
                      <span key={i} className="badge-neutral text-2xs">{s}</span>
                    )) || <span className="text-2xs text-fg-dim">—</span>}
                  </div>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim mb-1">Commodities</p>
                  <div className="flex flex-wrap gap-1">
                    {selected.commodities?.map((s, i) => (
                      <span key={i} className="badge-neutral text-2xs">{s}</span>
                    )) || <span className="text-2xs text-fg-dim">—</span>}
                  </div>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim mb-1">Currencies</p>
                  <div className="flex flex-wrap gap-1">
                    {selected.currencies?.map((s, i) => (
                      <span key={i} className="badge-neutral text-2xs">{s}</span>
                    )) || <span className="text-2xs text-fg-dim">—</span>}
                  </div>
                </div>
              </div>

              {/* Analysis sections */}
              {/* Direct Impacts */}
              {selected.direct_impacts && selected.direct_impacts.length > 0 && (
                <div className="analysis-box">
                  <p className="text-xs font-semibold text-accent-blue mb-3">
                    Direct Impacts ({selected.direct_impacts.length})
                  </p>
                  <div className="space-y-2">
                    {selected.direct_impacts.map((imp: any, i: number) => (
                      <div key={i} className="bg-surface-card border border-accent-blue-border rounded-lg p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-fg">{imp.entity}</p>
                            {imp.ticker && <p className="text-2xs text-fg-dim">{imp.ticker}</p>}
                            <p className="text-xs text-fg-muted mt-1">{imp.reasoning || imp.impact}</p>
                            <EvidenceCitation refs={imp.evidence_refs} />
                          </div>
                          <ImpactBadge direction={imp.direction || imp.impact} />
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Beneficiaries */}
              {selected.possible_beneficiaries && selected.possible_beneficiaries.length > 0 && (
                <div className="bg-accent-green-bg border border-accent-green-border rounded-lg p-4">
                  <p className="text-xs font-semibold text-accent-green mb-3">
                    Possible Beneficiaries ({selected.possible_beneficiaries.length})
                  </p>
                  <div className="space-y-2">
                    {selected.possible_beneficiaries.map((imp: any, i: number) => (
                      <div key={i} className="bg-surface-card border border-accent-green-border rounded-lg p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-fg">{imp.entity}</p>
                            {imp.ticker && <p className="text-2xs text-fg-dim">{imp.ticker}</p>}
                            <p className="text-xs text-fg-muted mt-1">{imp.reasoning || imp.impact}</p>
                          </div>
                          <span className="badge-green">Beneficiary</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Negative Exposures */}
              {selected.possible_negative_exposures && selected.possible_negative_exposures.length > 0 && (
                <div className="bg-accent-red-bg border border-accent-red-border rounded-lg p-4">
                  <p className="text-xs font-semibold text-accent-red mb-3">
                    Possible Negative Exposures ({selected.possible_negative_exposures.length})
                  </p>
                  <div className="space-y-2">
                    {selected.possible_negative_exposures.map((imp: any, i: number) => (
                      <div key={i} className="bg-surface-card border border-accent-red-border rounded-lg p-3">
                        <div className="flex items-start justify-between gap-2">
                          <div className="min-w-0">
                            <p className="text-sm font-medium text-fg">{imp.entity}</p>
                            {imp.ticker && <p className="text-2xs text-fg-dim">{imp.ticker}</p>}
                            <p className="text-xs text-fg-muted mt-1">{imp.reasoning || imp.impact}</p>
                          </div>
                          <span className="badge-red">Negative</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Causal Chain */}
              {selected.causal_chain && selected.causal_chain.length > 0 && (
                <div>
                  <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">
                    Causal Chain
                  </p>
                  <CausalChain steps={selected.causal_chain} />
                </div>
              )}

              {/* Source evidence */}
              {selected.source_ids && selected.source_ids.length > 0 && (
                <div className="fact-box">
                  <p className="text-2xs text-fg-dim uppercase tracking-wider mb-1">
                    Source Evidence ({selected.source_ids.length})
                  </p>
                  <div className="flex flex-wrap gap-1">
                    {selected.source_ids.map((id, i) => (
                      <span key={i} className="font-mono text-2xs text-fg-dim bg-surface-card px-1.5 py-0.5 rounded">
                        {id.slice(0, 12)}…
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Why section */}
              <div className="analysis-box">
                <p className="text-xs font-semibold text-accent-blue mb-2">
                  Why am I seeing this?
                </p>
                <ul className="text-2xs text-fg-muted space-y-1">
                  <li>• Classified as <strong className="text-fg">{selected.event_type.replace("_", " ")}</strong> with <strong className="text-fg">{Math.round(selected.confidence * 100)}% confidence</strong></li>
                  <li>• Affects <strong className="text-fg">{selected.sectors?.join(", ") || "—"}</strong> sector(s)</li>
                  <li>• Impact direction: <strong className="text-fg">{selected.impact_direction}</strong> over <strong className="text-fg">{selected.impact_horizon.replace("_", " ")}</strong></li>
                  <li>• Based on <strong className="text-fg">{selected.source_ids?.length || 0}</strong> evidence source(s)</li>
                  {selected.human_review_required && (
                    <li className="text-accent-amber">⚠ Human review recommended</li>
                  )}
                </ul>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
