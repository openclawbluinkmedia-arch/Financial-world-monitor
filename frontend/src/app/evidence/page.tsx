"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

interface EvidenceItem {
  id: string;
  evidence_id: string;
  source_id: string;
  source_name: string;
  original_url: string | null;
  publisher: string | null;
  title: string;
  raw_content: string;
  normalized_content: string | null;
  content_hash: string;
  near_dup_hash: string | null;
  publication_ts: string | null;
  ingestion_ts: string;
  jurisdiction: string;
  source_type: string;
  version: number;
  is_mock: boolean;
  extra_metadata: string | null;
  duplicate_status: string;
}

interface EvidenceResponse {
  items: EvidenceItem[];
  total: number;
  page: number;
  page_size: number;
  has_more: boolean;
}

interface SourceStats {
  source_id: string;
  source_name: string;
  source_type: string;
  total_items: number;
  mock_items: number;
  latest_ingestion: string | null;
  health_status: string;
}

interface ConnectorHealth {
  connector: string;
  status: string;
  last_run_at: string | null;
  consecutive_failures: number;
  last_error: string | null;
}

const JURISDICTION_COLORS: Record<string, string> = {
  IN: "bg-indigo-100 text-indigo-800",
  US: "bg-blue-100 text-blue-800",
  EU: "bg-purple-100 text-purple-800",
  GLOBAL: "bg-gray-100 text-gray-800",
  OTHER: "bg-slate-100 text-slate-800",
};

const SOURCE_TYPE_COLORS: Record<string, string> = {
  rss: "bg-green-100 text-green-800",
  api: "bg-blue-100 text-blue-800",
  scraper: "bg-orange-100 text-orange-800",
  world_monitor: "bg-purple-100 text-purple-800",
  gdelt: "bg-pink-100 text-pink-800",
  document: "bg-teal-100 text-teal-800",
};

const HEALTH_COLORS: Record<string, string> = {
  healthy: "bg-green-100 text-green-800",
  degraded: "bg-yellow-100 text-yellow-800",
  failed: "bg-red-100 text-red-800",
  unknown: "bg-gray-100 text-gray-800",
};

const DUP_STATUS_COLORS: Record<string, string> = {
  unique: "bg-green-100 text-green-800",
  exact: "bg-red-100 text-red-800",
  near: "bg-yellow-100 text-yellow-800",
};

function formatDate(ts: string | null): string {
  if (!ts) return "—";
  try {
    return new Date(ts).toLocaleString("en-US", {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return ts;
  }
}

function formatRelativeTime(ts: string | null): string {
  if (!ts) return "—";
  try {
    const diff = Date.now() - new Date(ts).getTime();
    const mins = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);
    if (mins < 1) return "just now";
    if (mins < 60) return `${mins}m ago`;
    if (hours < 24) return `${hours}h ago`;
    return `${days}d ago`;
  } catch {
    return ts;
  }
}

export default function EvidenceExplorerPage() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [evidence, setEvidence] = useState<EvidenceItem[]>([]);
  const [sourceStats, setSourceStats] = useState<SourceStats[]>([]);
  const [connectorHealth, setConnectorHealth] = useState<ConnectorHealth[]>([]);
  const [loading, setLoading] = useState(true);
  const [statsLoading, setStatsLoading] = useState(true);
  const [healthLoading, setHealthLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [filters, setFilters] = useState({
    source_id: searchParams.get("source_id") || "",
    source_type: searchParams.get("source_type") || "",
    jurisdiction: searchParams.get("jurisdiction") || "",
    is_mock: searchParams.get("is_mock") || "",
    duplicate_status: searchParams.get("duplicate_status") || "",
    search: searchParams.get("search") || "",
    date_from: searchParams.get("date_from") || "",
    date_to: searchParams.get("date_to") || "",
  });
  const [selectedItem, setSelectedItem] = useState<EvidenceItem | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const fetchEvidence = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const res = await fetch(`/api/evidence?${params}`);
      const data: EvidenceResponse = await res.json();
      setEvidence(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error("Failed to fetch evidence:", e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  const fetchSourceStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await fetch("/api/evidence/stats/sources");
      const data: SourceStats[] = await res.json();
      setSourceStats(data);
    } catch (e) {
      console.error("Failed to fetch source stats:", e);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  const fetchConnectorHealth = useCallback(async () => {
    setHealthLoading(true);
    try {
      const res = await fetch("/api/evidence/health/connectors");
      const data: ConnectorHealth[] = await res.json();
      setConnectorHealth(data);
    } catch (e) {
      console.error("Failed to fetch connector health:", e);
    } finally {
      setHealthLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvidence();
    fetchSourceStats();
    fetchConnectorHealth();
  }, [fetchEvidence, fetchSourceStats, fetchConnectorHealth]);

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleViewDetail = async (item: EvidenceItem) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/evidence/${item.id}`);
      const detail = await res.json();
      setSelectedItem({ ...item, ...detail });
    } catch (e) {
      console.error("Failed to fetch detail:", e);
    } finally {
      setDetailLoading(false);
    }
  };

  const handleExport = async () => {
    const params = new URLSearchParams();
    Object.entries(filters).forEach(([key, value]) => {
      if (value) params.set(key, value);
    });
    params.set("page_size", "1000");
    const res = await fetch(`/api/evidence?${params}`);
    const data = await res.json();
    const csv = [
      ["Evidence ID", "Source", "Title", "Publication Time", "Ingestion Time", "Jurisdiction", "Type", "Mock", "Duplicate Status", "URL"].join(","),
      ...data.items.map((i: EvidenceItem) =>
        [
          i.evidence_id,
          i.source_name,
          `"${i.title.replace(/"/g, '""')}"`,
          formatDate(i.publication_ts),
          formatDate(i.ingestion_ts),
          i.jurisdiction,
          i.source_type,
          i.is_mock ? "YES" : "NO",
          i.duplicate_status,
          i.original_url || "",
        ].join(",")
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `evidence-export-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Evidence Explorer</h1>
            <p className="text-gray-600 mt-1">
              Browse and analyze ingested financial intelligence evidence
            </p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleExport}
              className="px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors font-medium"
            >
              Export CSV
            </button>
            <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors font-medium"
            >
              Refresh
            </button>
          </div>
        </div>

        {/* Connector Health Bar */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Connector Health</h2>
          {healthLoading ? (
            <div className="flex gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex-1 animate-pulse bg-gray-100 rounded h-20" />
              ))}
            </div>
          ) : (
            <div className="flex flex-wrap gap-4">
              {connectorHealth.map((conn) => (
                <div
                  key={conn.connector}
                  className="flex-1 min-w-[200px] p-4 bg-gray-50 rounded-lg border"
                >
                  <div className="flex items-center justify-between mb-2">
                    <span className="font-medium text-gray-900">{conn.connector}</span>
                    <span
                      className={`px-2 py-1 text-xs rounded-full ${HEALTH_COLORS[conn.status] || HEALTH_COLORS.unknown}`}
                    >
                      {conn.status.toUpperCase()}
                    </span>
                  </div>
                  <div className="text-sm text-gray-600 space-y-1">
                    <p>Last run: {conn.last_run_at ? formatRelativeTime(conn.last_run_at) : "Never"}</p>
                    <p>Failures: {conn.consecutive_failures}</p>
                    {conn.last_error && (
                      <p className="text-red-600 truncate" title={conn.last_error}>
                        Error: {conn.last_error}
                      </p>
                    )}
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Source Stats */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Source Statistics</h2>
          {statsLoading ? (
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="animate-pulse bg-gray-100 rounded h-24" />
              ))}
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="text-left text-gray-500 border-b">
                    <th className="pb-2 pr-4">Source</th>
                    <th className="pb-2 pr-4">Type</th>
                    <th className="pb-2 pr-4">Total Items</th>
                    <th className="pb-2 pr-4">Mock Items</th>
                    <th className="pb-2 pr-4">Latest Ingestion</th>
                    <th className="pb-2 pr-4">Health</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {sourceStats.map((stat) => (
                    <tr key={stat.source_id} className="hover:bg-gray-50">
                      <td className="py-3 pr-4 font-medium">{stat.source_name}</td>
                      <td className="py-3 pr-4">
                        <span
                          className={`px-2 py-0.5 text-xs rounded-full ${SOURCE_TYPE_COLORS[stat.source_type] || "bg-gray-100 text-gray-800"}`}
                        >
                          {stat.source_type}
                        </span>
                      </td>
                      <td className="py-3 pr-4">{stat.total_items}</td>
                      <td className="py-3 pr-4">{stat.mock_items}</td>
                      <td className="py-3 pr-4 text-gray-600">
                        {stat.latest_ingestion ? formatRelativeTime(stat.latest_ingestion) : "—"}
                      </td>
                      <td className="py-3 pr-4">
                        <span
                          className={`px-2 py-0.5 text-xs rounded-full ${HEALTH_COLORS[stat.health_status] || HEALTH_COLORS.unknown}`}
                        >
                          {stat.health_status}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Filters */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
          <h2 className="text-lg font-semibold text-gray-900 mb-3">Filters</h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-7 gap-4">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Search</label>
              <input
                type="text"
                value={filters.search}
                onChange={(e) => handleFilterChange("search", e.target.value)}
                placeholder="Search title, content..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Source</label>
              <select
                value={filters.source_id}
                onChange={(e) => handleFilterChange("source_id", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All Sources</option>
                {sourceStats.map((s) => (
                  <option key={s.source_id} value={s.source_id}>
                    {s.source_name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Type</label>
              <select
                value={filters.source_type}
                onChange={(e) => handleFilterChange("source_type", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All Types</option>
                <option value="rss">RSS</option>
                <option value="api">API</option>
                <option value="scraper">Scraper</option>
                <option value="world_monitor">World Monitor</option>
                <option value="gdelt">GDELT</option>
                <option value="document">Document</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Jurisdiction</label>
              <select
                value={filters.jurisdiction}
                onChange={(e) => handleFilterChange("jurisdiction", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All</option>
                <option value="IN">India</option>
                <option value="US">US</option>
                <option value="EU">EU</option>
                <option value="GLOBAL">Global</option>
                <option value="OTHER">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Mock Data</label>
              <select
                value={filters.is_mock}
                onChange={(e) => handleFilterChange("is_mock", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All</option>
                <option value="true">Mock Only</option>
                <option value="false">Real Only</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Duplicate Status</label>
              <select
                value={filters.duplicate_status}
                onChange={(e) => handleFilterChange("duplicate_status", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All</option>
                <option value="unique">Unique</option>
                <option value="exact">Exact Duplicate</option>
                <option value="near">Near Duplicate</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date Range</label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={filters.date_from}
                  onChange={(e) => handleFilterChange("date_from", e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
                <input
                  type="date"
                  value={filters.date_to}
                  onChange={(e) => handleFilterChange("date_to", e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Evidence Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Evidence Items ({total})
            </h2>
            <select
              value={pageSize}
              onChange={(e) => { setPageSize(Number(e.target.value)); setPage(1); }}
              className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
            >
              <option value="25">25 per page</option>
              <option value="50">50 per page</option>
              <option value="100">100 per page</option>
            </select>
          </div>

          {loading ? (
            <div className="p-8">
              {[1, 2, 3, 4, 5].map((i) => (
                <div key={i} className="animate-pulse flex items-center gap-4 px-4 py-4 border-b border-gray-100">
                  <div className="w-8 h-8 bg-gray-200 rounded" />
                  <div className="flex-1 space-y-2">
                    <div className="h-4 bg-gray-200 rounded w-3/4" />
                    <div className="h-3 bg-gray-200 rounded w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          ) : evidence.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="mt-2 text-lg">No evidence items found</p>
              <p className="text-sm">Try adjusting your filters</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-gray-500 border-b bg-gray-50">
                    <th className="p-3 font-medium">Title</th>
                    <th className="p-3 font-medium">Source</th>
                    <th className="p-3 font-medium">Pub Time</th>
                    <th className="p-3 font-medium">Ingest Time</th>
                    <th className="p-3 font-medium">Jurisdiction</th>
                    <th className="p-3 font-medium">Type</th>
                    <th className="p-3 font-medium">Status</th>
                    <th className="p-3 font-medium">Dup</th>
                    <th className="p-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {evidence.map((item) => (
                    <tr key={item.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => handleViewDetail(item)}>
                      <td className="p-3 max-w-md">
                        <div className="font-medium text-gray-900 truncate" title={item.title}>
                          {item.is_mock && <span className="inline-block px-1.5 py-0.5 text-xs bg-amber-100 text-amber-800 rounded mr-2">MOCK</span>}
                          {item.title}
                        </div>
                        <div className="text-sm text-gray-500 truncate mt-1">{item.raw_content.slice(0, 100)}...</div>
                      </td>
                      <td className="p-3 text-sm text-gray-700">{item.source_name}</td>
                      <td className="p-3 text-sm text-gray-600">{item.publication_ts ? formatRelativeTime(item.publication_ts) : "—"}</td>
                      <td className="p-3 text-sm text-gray-600">{formatRelativeTime(item.ingestion_ts)}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${JURISDICTION_COLORS[item.jurisdiction] || JURISDICTION_COLORS.OTHER}`}>
                          {item.jurisdiction}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${SOURCE_TYPE_COLORS[item.source_type] || "bg-gray-100 text-gray-800"}`}>
                          {item.source_type}
                        </span>
                      </td>
                      <td className="p-3">
                        {item.is_mock ? (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-amber-100 text-amber-800">Mock</span>
                        ) : (
                          <span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800">Real</span>
                        )}
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${DUP_STATUS_COLORS[item.duplicate_status] || DUP_STATUS_COLORS.unique}`}>
                          {item.duplicate_status === "exact" ? "Exact" : item.duplicate_status === "near" ? "Near" : "Unique"}
                        </span>
                      </td>
                      <td className="p-3">
                        {item.original_url && (
                          <a
                            href={item.original_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                            onClick={(e) => e.stopPropagation()}
                          >
                            View Source
                          </a>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          <div className="p-4 border-t border-gray-200 flex items-center justify-between">
            <p className="text-sm text-gray-600">
              Showing {((page - 1) * pageSize) + 1} to {Math.min(page * pageSize, total)} of {total}
            </p>
            <div className="flex gap-2">
              <button
                onClick={() => handlePageChange(page - 1)}
                disabled={page === 1}
                className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Previous
              </button>
              <button
                onClick={() => handlePageChange(page + 1)}
                disabled={page * pageSize >= total}
                className="px-3 py-1.5 border border-gray-300 rounded-lg disabled:opacity-50 disabled:cursor-not-allowed hover:bg-gray-50"
              >
                Next
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Detail Modal */}
      {selectedItem && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={() => setSelectedItem(null)}>
          <div className="bg-white rounded-xl max-w-4xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-white z-10">
              <h3 className="text-lg font-semibold">{selectedItem.title}</h3>
              <button onClick={() => setSelectedItem(null)} className="text-gray-500 hover:text-gray-700 text-2xl">×</button>
            </div>
            <div className="p-4 space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
                <div><span className="text-gray-500">Evidence ID</span><p className="font-mono">{selectedItem.evidence_id}</p></div>
                <div><span className="text-gray-500">Source</span><p>{selectedItem.source_name}</p></div>
                <div><span className="text-gray-500">Jurisdiction</span><p>{selectedItem.jurisdiction}</p></div>
                <div><span className="text-gray-500">Type</span><p>{selectedItem.source_type}</p></div>
                <div className="md:col-span-2"><span className="text-gray-500">Publisher</span><p>{selectedItem.publisher || "—"}</p></div>
                <div className="md:col-span-2"><span className="text-gray-500">Original URL</span><p>{selectedItem.original_url ? <a href={selectedItem.original_url} target="_blank" rel="noopener" className="text-indigo-600">{selectedItem.original_url}</a> : "—"}</p></div>
                <div><span className="text-gray-500">Publication</span><p>{formatDate(selectedItem.publication_ts)}</p></div>
                <div><span className="text-gray-500">Ingestion</span><p>{formatDate(selectedItem.ingestion_ts)}</p></div>
                <div><span className="text-gray-500">Version</span><p>{selectedItem.version}</p></div>
                <div><span className="text-gray-500">Mock</span><p>{selectedItem.is_mock ? "Yes" : "No"}</p></div>
                <div><span className="text-gray-500">Duplicate</span><p>{selectedItem.duplicate_status}</p></div>
                <div className="md:col-span-4">
                  <span className="text-gray-500">Content Hash</span>
                  <p className="font-mono text-xs break-all">{selectedItem.content_hash}</p>
                </div>
              </div>

              <div>
                <h4 className="font-medium mb-2">Raw Content</h4>
                <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto max-h-96">{selectedItem.raw_content}</pre>
              </div>

              {selectedItem.normalized_content && (
                <div>
                  <h4 className="font-medium mb-2">Normalized Content</h4>
                  <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto max-h-96">{selectedItem.normalized_content}</pre>
                </div>
              )}

              {selectedItem.extra_metadata && (
                <div>
                  <h4 className="font-medium mb-2">Metadata</h4>
                  <pre className="bg-gray-100 p-4 rounded-lg text-sm overflow-x-auto">{selectedItem.extra_metadata}</pre>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}