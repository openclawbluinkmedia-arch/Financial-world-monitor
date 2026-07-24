"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchApi, getEvidence, getSourceStats, type EvidenceItem, type SourceStat } from "@/lib/api";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import FilterBar from "../components/FilterBar";
import DataTable from "../components/DataTable";
import ImpactBadge from "../components/ImpactBadge";
import LiveIndicator from "../components/LiveIndicator";

function relativeTime(ts: string | null): string {
  if (!ts) return "—";
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

export default function EvidencePage() {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [filters, setFilters] = useState({
    search: "", source_id: "", source_type: "", jurisdiction: "",
    is_mock: "", duplicate_status: "", date_from: "", date_to: "",
  });
  const [selected, setSelected] = useState<EvidenceItem | null>(null);
  const [sources, setSources] = useState<SourceStat[]>([]);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchEvidence = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Record<string, string> = { page: page.toString(), page_size: pageSize.toString() };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const data = await getEvidence(params);
      setEvidence(data.items || []);
      setTotal(data.total || 0);
    } catch (e: any) {
      setError(e.message || "Failed to load evidence");
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  const fetchSources = useCallback(async () => {
    try { setSources(await getSourceStats()); }
    catch { /* non-critical */ }
  }, []);

  useEffect(() => { fetchEvidence(); fetchSources(); }, [fetchEvidence, fetchSources]);

  useEffect(() => {
    const interval = setInterval(() => { fetchEvidence(); fetchSources(); setLastUpdated(new Date()); }, 45000);
    return () => clearInterval(interval);
  }, [fetchEvidence, fetchSources]);

  const handleFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleExport = async () => {
    try {
      const params: Record<string, string> = { page_size: "1000" };
      Object.entries(filters).forEach(([k, v]) => { if (v) params[k] = v; });
      const data = await getEvidence(params);
      const csv = [
        ["Evidence ID","Source","Title","Pub Time","Jurisdiction","Type","Mock","Dup"].join(","),
        ...(data.items || []).map(
          (i: EvidenceItem) => [i.evidence_id, i.source_name, `"${i.title.replace(/"/g, '""')}"`, i.publication_ts || "", i.jurisdiction, i.source_type, i.is_mock ? "YES" : "NO", i.duplicate_status].join(",")
        ),
      ].join("\n");
      const blob = new Blob([csv], { type: "text/csv" });
      const a = document.createElement("a");
      a.href = URL.createObjectURL(blob);
      a.download = `evidence-${new Date().toISOString().slice(0,10)}.csv`;
      a.click();
    } catch (e: any) { console.error("Export failed:", e); }
  };

  const totalMock = sources.reduce((s, src) => s + src.mock_items, 0);
  const sourceOptions = [
    { value: "", label: "All Sources" },
    ...sources.map((s) => ({ value: s.source_name, label: s.source_name })),
  ];

  const filterDefs = [
    { key: "search", label: "Search", type: "text" as const, placeholder: "Title, content..." },
    { key: "source_id", label: "Source", type: "select" as const, options: sourceOptions },
    { key: "source_type", label: "Type", type: "select" as const,
      options: [{ value: "", label: "All Types" }, { value: "rss", label: "RSS" }, { value: "api", label: "API" }, { value: "scraper", label: "Scraper" }, { value: "world_monitor", label: "World Monitor" }, { value: "gdelt", label: "GDELT" }] },
    { key: "jurisdiction", label: "Jurisdiction", type: "select" as const,
      options: [{ value: "", label: "All" }, { value: "IN", label: "India" }, { value: "US", label: "US" }, { value: "EU", label: "EU" }, { value: "GLOBAL", label: "Global" }] },
    { key: "is_mock", label: "Mock Data", type: "select" as const,
      options: [{ value: "", label: "All" }, { value: "true", label: "Mock Only" }, { value: "false", label: "Real Only" }] },
    { key: "duplicate_status", label: "Duplicate", type: "select" as const,
      options: [{ value: "", label: "All" }, { value: "unique", label: "Unique" }, { value: "exact", label: "Exact Duplicate" }, { value: "near", label: "Near Duplicate" }] },
    { key: "date_from", label: "From", type: "date" as const },
    { key: "date_to", label: "To", type: "date" as const },
  ];

  const columns = [
    { key: "title", label: "Title",
      render: (row: EvidenceItem) => (
        <div className="max-w-md">
          <div className="flex items-center gap-1.5">
            {row.is_mock && <span className="badge-amber text-2xs">MOCK</span>}
            <span className="text-sm font-medium text-fg truncate" title={row.title}>{row.title}</span>
          </div>
          <p className="text-2xs text-fg-dim truncate mt-0.5">{row.raw_content?.slice(0,80)}...</p>
        </div>
      ) },
    { key: "source_name", label: "Source" },
    { key: "publication_ts", label: "Pub Time", render: (row: EvidenceItem) => <span className="text-2xs font-mono text-fg-dim">{relativeTime(row.publication_ts)}</span> },
    { key: "jurisdiction", label: "Jurisdiction", render: (row: EvidenceItem) => <span className="badge-neutral">{row.jurisdiction}</span> },
    { key: "source_type", label: "Type", render: (row: EvidenceItem) => <span className="badge-neutral">{row.source_type}</span> },
    { key: "duplicate_status", label: "Dup", render: (row: EvidenceItem) => {
      const c = row.duplicate_status === "unique" ? "badge-green" : row.duplicate_status === "exact" ? "badge-red" : row.duplicate_status === "near" ? "badge-amber" : "badge-neutral";
      return <span className={`${c} text-2xs`}>{row.duplicate_status}</span>;
    }},
    { key: "actions", label: "", render: (row: EvidenceItem) => (
      <button onClick={(e) => { e.stopPropagation(); setSelected(row); }} className="btn-ghost text-2xs">View</button>
    )},
  ];

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-container">
      {!apiUrl && (
        <div className="mb-4 px-4 py-3 bg-accent-amber-bg border border-accent-amber-border rounded-lg text-sm text-accent-amber text-center">
          ⚠ NEXT_PUBLIC_API_URL is not configured. Using fallback http://localhost:8000
        </div>
      )}

      <PageHeader title="Evidence Explorer" subtitle={`${total} items from ${sources.length} sources`}
        actions={
          <>
            <LiveIndicator />
            <button onClick={handleExport} className="btn-secondary">Export CSV</button>
            <button onClick={() => { fetchEvidence(); setLastUpdated(new Date()); }} className="btn-primary">Refresh</button>
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
            <button onClick={fetchEvidence} className="btn-primary text-xs shrink-0">Retry</button>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Items" value={total} accent="blue" mono />
        <StatCard label="Mock Items" value={totalMock} accent={totalMock > 0 ? "amber" : "green"} mono />
        <StatCard label="Data Sources" value={sources.length} accent="purple" mono />
      </div>

      <div className="mb-6">
        <FilterBar filters={filters} definitions={filterDefs} onChange={handleFilter} />
      </div>

      <div className="card">
        <div className="card-header">
          <span className="text-sm font-medium text-fg">Evidence Items</span>
          <select value={pageSize} onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }} className="text-sm w-auto">
            <option value="25">25 / page</option><option value="50">50 / page</option><option value="100">100 / page</option>
          </select>
        </div>
        <DataTable columns={columns} data={evidence} loading={loading} emptyMessage="No evidence items yet — run ingestion" onRowClick={(row) => setSelected(row)} />
        <div className="card-header border-t border-surface-border">
          <span className="text-2xs text-fg-dim">Page {page} of {pageCount} ({total} total)</span>
          <div className="flex gap-2">
            <button onClick={() => setPage(page - 1)} disabled={page <= 1} className="btn-ghost text-xs disabled:opacity-40">Previous</button>
            <button onClick={() => setPage(page + 1)} disabled={page >= pageCount} className="btn-ghost text-xs disabled:opacity-40">Next</button>
          </div>
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={() => setSelected(null)}>
          <div className="card max-w-3xl w-full max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h3 className="text-sm font-semibold text-fg truncate">{selected.title}</h3>
              <button onClick={() => setSelected(null)} className="text-fg-dim hover:text-fg text-lg leading-none">✕</button>
            </div>
            <div className="card-body space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div><p className="text-2xs text-fg-dim">Evidence ID</p><p className="font-mono text-xs text-fg-muted">{selected.evidence_id}</p></div>
                <div><p className="text-2xs text-fg-dim">Source</p><p className="text-sm text-fg">{selected.source_name}</p></div>
                <div><p className="text-2xs text-fg-dim">Jurisdiction</p><p>{selected.jurisdiction}</p></div>
                <div><p className="text-2xs text-fg-dim">Type</p><span className="badge-neutral">{selected.source_type}</span></div>
                <div><p className="text-2xs text-fg-dim">Duplicate</p><span className={`text-2xs ${selected.duplicate_status === "unique" ? "badge-green" : selected.duplicate_status === "exact" ? "badge-red" : "badge-amber"}`}>{selected.duplicate_status}</span></div>
                <div><p className="text-2xs text-fg-dim">Mock</p><p>{selected.is_mock ? "Yes" : "No"}</p></div>
              </div>
              <div><p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">Raw Content</p>
                <pre className="fact-box text-xs font-mono text-fg-muted max-h-60 overflow-auto whitespace-pre-wrap">{selected.raw_content}</pre>
              </div>
              {selected.original_url && (
                <div><p className="text-2xs text-fg-dim uppercase tracking-wider mb-1">Source URL</p>
                  <a href={selected.original_url} target="_blank" rel="noopener noreferrer" className="text-xs text-accent-blue hover:underline">{selected.original_url}</a>
                </div>
              )}
              <div className="flex items-center gap-4 text-2xs text-fg-dim">
                <span>Published: {selected.publication_ts ? new Date(selected.publication_ts).toLocaleString() : "—"}</span>
                <span>Ingested: {selected.ingestion_ts ? new Date(selected.ingestion_ts).toLocaleString() : "—"}</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
