"use client";

import { useState, useEffect, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import FilterBar from "../components/FilterBar";
import DataTable from "../components/DataTable";
import ImpactBadge from "../components/ImpactBadge";
import LiveIndicator from "../components/LiveIndicator";

interface EvidenceItem {
  id: string;
  evidence_id: string;
  source_name: string;
  original_url: string | null;
  publisher: string | null;
  title: string;
  raw_content: string;
  publication_ts: string | null;
  ingestion_ts: string;
  jurisdiction: string;
  source_type: string;
  is_mock: boolean;
  duplicate_status: string;
}

interface SourceStats {
  source_name: string;
  source_type: string;
  total_items: number;
  mock_items: number;
  health_status: string;
}

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
  } catch {
    return ts;
  }
}

export default function EvidencePage() {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [filters, setFilters] = useState({
    search: "",
    source_id: "",
    source_type: "",
    jurisdiction: "",
    is_mock: "",
    duplicate_status: "",
    date_from: "",
    date_to: "",
  });
  const [selected, setSelected] = useState<EvidenceItem | null>(null);
  const [sources, setSources] = useState<SourceStats[]>([]);

  const fetchEvidence = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });
      Object.entries(filters).forEach(([k, v]) => {
        if (v) params.set(k, v);
      });
      const res = await fetch(`/api/evidence?${params}`);
      const data = await res.json();
      setEvidence(data.items || []);
      setTotal(data.total || 0);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  const fetchSources = useCallback(async () => {
    try {
      const res = await fetch("/api/evidence/stats/sources");
      setSources(await res.json());
    } catch (e) {
      console.error(e);
    }
  }, []);

  useEffect(() => {
    fetchEvidence();
    fetchSources();
  }, [fetchEvidence, fetchSources]);

  // Live polling every 45s
  useEffect(() => {
    const interval = setInterval(() => {
      fetchEvidence();
      fetchSources();
      setLastUpdated(new Date());
    }, 45000);
    return () => clearInterval(interval);
  }, [fetchEvidence, fetchSources]);

  const handleFilter = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handleExport = async () => {
    const params = new URLSearchParams({ page_size: "1000" });
    Object.entries(filters).forEach(([k, v]) => {
      if (v) params.set(k, v);
    });
    const res = await fetch(`/api/evidence?${params}`);
    const data = await res.json();
    const csv = [
      ["Evidence ID", "Source", "Title", "Pub Time", "Jurisdiction", "Type", "Mock", "Dup"].join(","),
      ...(data.items || []).map(
        (i: EvidenceItem) =>
          [
            i.evidence_id,
            i.source_name,
            `"${i.title.replace(/"/g, '""')}"`,
            i.publication_ts || "",
            i.jurisdiction,
            i.source_type,
            i.is_mock ? "YES" : "NO",
            i.duplicate_status,
          ].join(",")
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = `evidence-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
  };

  const totalMock = sources.reduce((s, src) => s + src.mock_items, 0);

  const sourceOptions = [
    { value: "", label: "All Sources" },
    ...sources.map((s) => ({ value: s.source_name, label: s.source_name })),
  ];

  const filterDefs = [
    { key: "search", label: "Search", type: "text" as const, placeholder: "Title, content..." },
    {
      key: "source_id",
      label: "Source",
      type: "select" as const,
      options: sourceOptions,
    },
    {
      key: "source_type",
      label: "Type",
      type: "select" as const,
      options: [
        { value: "", label: "All Types" },
        { value: "rss", label: "RSS" },
        { value: "api", label: "API" },
        { value: "scraper", label: "Scraper" },
        { value: "world_monitor", label: "World Monitor" },
        { value: "gdelt", label: "GDELT" },
      ],
    },
    {
      key: "jurisdiction",
      label: "Jurisdiction",
      type: "select" as const,
      options: [
        { value: "", label: "All" },
        { value: "IN", label: "India" },
        { value: "US", label: "US" },
        { value: "EU", label: "EU" },
        { value: "GLOBAL", label: "Global" },
      ],
    },
    {
      key: "is_mock",
      label: "Mock Data",
      type: "select" as const,
      options: [
        { value: "", label: "All" },
        { value: "true", label: "Mock Only" },
        { value: "false", label: "Real Only" },
      ],
    },
    {
      key: "duplicate_status",
      label: "Duplicate",
      type: "select" as const,
      options: [
        { value: "", label: "All" },
        { value: "unique", label: "Unique" },
        { value: "exact", label: "Exact Duplicate" },
        { value: "near", label: "Near Duplicate" },
      ],
    },
    { key: "date_from", label: "From", type: "date" as const },
    { key: "date_to", label: "To", type: "date" as const },
  ];

  const columns = [
    {
      key: "title",
      label: "Title",
      render: (row: EvidenceItem) => (
        <div className="max-w-md">
          <div className="flex items-center gap-1.5">
            {row.is_mock && <span className="badge-amber text-2xs">MOCK</span>}
            <span className="text-sm font-medium text-fg truncate" title={row.title}>
              {row.title}
            </span>
          </div>
          <p className="text-2xs text-fg-dim truncate mt-0.5">
            {row.raw_content?.slice(0, 80)}...
          </p>
        </div>
      ),
    },
    { key: "source_name", label: "Source" },
    {
      key: "publication_ts",
      label: "Pub Time",
      render: (row: EvidenceItem) => (
        <span className="text-2xs font-mono text-fg-dim">
          {relativeTime(row.publication_ts)}
        </span>
      ),
    },
    {
      key: "jurisdiction",
      label: "Jurisdiction",
      render: (row: EvidenceItem) => (
        <span className="badge-neutral">{row.jurisdiction}</span>
      ),
    },
    {
      key: "source_type",
      label: "Type",
      render: (row: EvidenceItem) => (
        <span className="badge-neutral">{row.source_type}</span>
      ),
    },
    {
      key: "duplicate_status",
      label: "Dup",
      render: (row: EvidenceItem) => {
        const color =
          row.duplicate_status === "unique"
            ? "badge-green"
            : row.duplicate_status === "exact"
              ? "badge-red"
              : row.duplicate_status === "near"
                ? "badge-amber"
                : "badge-neutral";
        return <span className={`${color} text-2xs`}>{row.duplicate_status}</span>;
      },
    },
    {
      key: "actions",
      label: "",
      render: (row: EvidenceItem) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            setSelected(row);
          }}
          className="btn-ghost text-2xs"
        >
          View
        </button>
      ),
    },
  ];

  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="page-container">
      <PageHeader
        title="Evidence Explorer"
        subtitle={`${total} items from ${sources.length} sources`}
        actions={
          <>
            <LiveIndicator />
            <button onClick={handleExport} className="btn-secondary">
              Export CSV
            </button>
            <button onClick={() => { fetchEvidence(); setLastUpdated(new Date()); }} className="btn-primary">
              Refresh
            </button>
          </>
        }
      />

      {/* Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard label="Total Items" value={total} accent="blue" mono />
        <StatCard
          label="Mock Items"
          value={totalMock}
          accent={totalMock > 0 ? "amber" : "green"}
          mono
        />
        <StatCard
          label="Data Sources"
          value={sources.length}
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

      {/* Table */}
      <div className="card">
        <div className="card-header">
          <span className="text-sm font-medium text-fg">Evidence Items</span>
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
          data={evidence}
          loading={loading}
          emptyMessage="No evidence items found. Try adjusting filters."
          onRowClick={(row) => setSelected(row)}
        />
        {/* Pagination */}
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
            className="card max-w-3xl w-full max-h-[85vh] overflow-y-auto"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="card-header">
              <h3 className="text-sm font-semibold text-fg truncate">
                {selected.title}
              </h3>
              <button
                onClick={() => setSelected(null)}
                className="text-fg-dim hover:text-fg text-lg leading-none"
              >
                ✕
              </button>
            </div>
            <div className="card-body space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-3 gap-4 text-sm">
                <div>
                  <p className="text-2xs text-fg-dim">Evidence ID</p>
                  <p className="font-mono text-xs text-fg-muted">
                    {selected.evidence_id}
                  </p>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Source</p>
                  <p className="text-sm text-fg">{selected.source_name}</p>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Jurisdiction</p>
                  <p>{selected.jurisdiction}</p>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Type</p>
                  <span className="badge-neutral">{selected.source_type}</span>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Duplicate</p>
                  <span
                    className={`text-2xs ${
                      selected.duplicate_status === "unique"
                        ? "badge-green"
                        : selected.duplicate_status === "exact"
                          ? "badge-red"
                          : "badge-amber"
                    }`}
                  >
                    {selected.duplicate_status}
                  </span>
                </div>
                <div>
                  <p className="text-2xs text-fg-dim">Mock</p>
                  <p>{selected.is_mock ? "Yes" : "No"}</p>
                </div>
              </div>

              <div>
                <p className="text-2xs text-fg-dim uppercase tracking-wider mb-2">
                  Raw Content
                </p>
                <pre className="fact-box text-xs font-mono text-fg-muted max-h-60 overflow-auto whitespace-pre-wrap">
                  {selected.raw_content}
                </pre>
              </div>

              {selected.original_url && (
                <div>
                  <p className="text-2xs text-fg-dim uppercase tracking-wider mb-1">
                    Source URL
                  </p>
                  <a
                    href={selected.original_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-xs text-accent-blue hover:underline"
                  >
                    {selected.original_url}
                  </a>
                </div>
              )}

              <div className="flex items-center gap-4 text-2xs text-fg-dim">
                <span>
                  Published:{" "}
                  {selected.publication_ts
                    ? new Date(selected.publication_ts).toLocaleString()
                    : "—"}
                </span>
                <span>
                  Ingested:{" "}
                  {selected.ingestion_ts
                    ? new Date(selected.ingestion_ts).toLocaleString()
                    : "—"}
                </span>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
