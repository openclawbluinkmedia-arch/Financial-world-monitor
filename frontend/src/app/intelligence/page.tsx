"use client";

import React, { useState, useEffect, useCallback } from "react";
import { useRouter, useSearchParams } from "next/navigation";

interface IntelligenceEvent {
  id: string;
  event_id: string;
  event_type: string;
  factual_summary: string;
  timestamp: string;
  geography: string;
  entities: any[];
  sectors: string[];
  industries: string[];
  commodities: string[];
  currencies: string[];
  source_ids: string[];
  direct_impacts: Impact[];
  indirect_impacts: Impact[];
  possible_beneficiaries: Impact[];
  possible_negative_exposures: Impact[];
  impact_direction: string;
  impact_horizon: string;
  causal_chain: CausalStep[];
  confidence: number;
  uncertainty: number;
  human_review_required: boolean;
  validation_flags: string[];
}

interface Impact {
  entity: string;
  ticker?: string;
  impact: string;
  direction: string;
  magnitude?: string;
  evidence_refs: string[];
  reasoning?: string;
  probability?: string;
}

interface CausalStep {
  step: number;
  cause: string;
  effect: string;
  evidence_refs: string[];
  confidence: string;
  type: string;
}

interface IntelligenceResponse {
  items: IntelligenceEvent[];
  total: number;
  limit: number;
  offset: number;
}

const EVENT_TYPE_COLORS: Record<string, string> = {
  macro: "bg-blue-100 text-blue-800",
  earnings: "bg-green-100 text-green-800",
  m_a: "bg-purple-100 text-purple-800",
  regulatory: "bg-red-100 text-red-800",
  policy: "bg-orange-100 text-orange-800",
  corporate_action: "bg-indigo-100 text-indigo-800",
  market_move: "bg-yellow-100 text-yellow-800",
  commodity: "bg-amber-100 text-amber-800",
  currency: "bg-teal-100 text-teal-800",
  geopolitical: "bg-rose-100 text-rose-800",
  sector: "bg-cyan-100 text-cyan-800",
  supply_chain: "bg-lime-100 text-lime-800",
  esg: "bg-emerald-100 text-emerald-800",
  other: "bg-gray-100 text-gray-800",
};

const DIRECTION_COLORS: Record<string, string> = {
  positive: "bg-green-100 text-green-800",
  negative: "bg-red-100 text-red-800",
  neutral: "bg-gray-100 text-gray-800",
  mixed: "bg-yellow-100 text-yellow-800",
  unknown: "bg-gray-100 text-gray-800",
};

const HORIZON_COLORS: Record<string, string> = {
  immediate: "bg-red-100 text-red-800",
  short_term: "bg-orange-100 text-orange-800",
  medium_term: "bg-blue-100 text-blue-800",
  long_term: "bg-purple-100 text-purple-800",
  unknown: "bg-gray-100 text-gray-800",
};

const EDGE_TYPE_COLORS: Record<string, string> = {
  verified: "bg-green-100 text-green-800",
  inferred: "bg-yellow-100 text-yellow-800",
  uncertain: "bg-red-100 text-red-800",
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

export default function IntelligenceDashboard() {
  const router = useRouter();
  const searchParams = useSearchParams();

  const [events, setEvents] = useState<IntelligenceEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(50);
  const [filters, setFilters] = useState({
    event_type: searchParams.get("event_type") || "",
    impact_direction: searchParams.get("impact_direction") || "",
    impact_horizon: searchParams.get("impact_horizon") || "",
    geography: searchParams.get("geography") || "",
    min_confidence: searchParams.get("min_confidence") || "",
    date_from: searchParams.get("date_from") || "",
    date_to: searchParams.get("date_to") || "",
    search: searchParams.get("search") || "",
  });
  const [selectedEvent, setSelectedEvent] = useState<IntelligenceEvent | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [stats, setStats] = useState<any>(null);
  const [statsLoading, setStatsLoading] = useState(true);

  const fetchEvents = useCallback(async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({
        page: page.toString(),
        page_size: pageSize.toString(),
      });
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.set(key, value);
      });
      const res = await fetch(`/api/intelligence/events?${params}`);
      const data: IntelligenceResponse = await res.json();
      setEvents(data.items);
      setTotal(data.total);
    } catch (e) {
      console.error("Failed to fetch events:", e);
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, filters]);

  const fetchStats = useCallback(async () => {
    setStatsLoading(true);
    try {
      const res = await fetch("/api/intelligence/stats");
      const data = await res.json();
      setStats(data);
    } catch (e) {
      console.error("Failed to fetch stats:", e);
    } finally {
      setStatsLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEvents();
    fetchStats();
  }, [fetchEvents, fetchStats]);

  const handleFilterChange = (key: string, value: string) => {
    setFilters((prev) => ({ ...prev, [key]: value }));
    setPage(1);
  };

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const handleViewDetail = async (event: IntelligenceEvent) => {
    setDetailLoading(true);
    try {
      const res = await fetch(`/api/intelligence/events/${event.id}`);
      const data = await res.json();
      setSelectedItem({ ...event, ...data });
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
    params.set("page_size", "500");
    const res = await fetch(`/api/intelligence/events?${params}`);
    const data = await res.json();
    const csv = [
      ["Event ID", "Type", "Summary", "Timestamp", "Geography", "Direction", "Horizon", "Confidence", "Direction"].join(","),
      ...data.items.map((e: IntelligenceEvent) =>
        [
          e.event_id,
          e.event_type,
          `"${e.factual_summary.replace(/"/g, '""')}"`,
          formatDate(e.timestamp),
          e.geography,
          e.impact_direction,
          e.impact_horizon,
          e.confidence.toFixed(2),
          e.impact_direction,
        ].join(",")
      ),
    ].join("\n");
    const blob = new Blob([csv], { type: "text/csv" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `intelligence-events-${new Date().toISOString().slice(0, 10)}.csv`;
    a.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">Intelligence Dashboard</h1>
            <p className="text-gray-600 mt-1">
              Real-time impact intelligence for Indian equities
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

        {/* Stats Cards */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-5 gap-4">
          <StatCard
            title="Total Events"
            value={total}
            icon="📊"
            color="indigo"
          />
          <StatCard
            title="Avg Confidence"
            value={stats?.avg_confidence ? `${Math.round(stats.avg_confidence * 100)}%` : "—"}
            icon="🎯"
            color="green"
          />
          <StatCard
            title="Validation Pass Rate"
            value={stats?.validation_pass_rate ? `${Math.round(stats.validation_pass_rate * 100)}%` : "—"}
            icon="✅"
            color="blue"
          />
          <StatCard
            title="Human Review Required"
            value={stats?.human_review_required || "—"}
            icon="⚠️"
            color="amber"
          />
          <StatCard
            title="Event Types"
            value={stats?.by_type ? Object.keys(stats.by_type).length : "—"}
            icon="🏷️"
            color="purple"
          />
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
                placeholder="Search summary, entities..."
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Event Type</label>
              <select
                value={filters.event_type}
                onChange={(e) => handleFilterChange("event_type", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All Types</option>
                {Object.keys(EVENT_TYPE_COLORS).map((type) => (
                  <option key={type} value={type}>
                    {type.charAt(0).toUpperCase() + type.slice(1).replace("_", " ")}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Impact Direction</label>
              <select
                value={filters.impact_direction}
                onChange={(e) => handleFilterChange("impact_direction", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All</option>
                <option value="positive">Positive</option>
                <option value="negative">Negative</option>
                <option value="neutral">Neutral</option>
                <option value="mixed">Mixed</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Impact Horizon</label>
              <select
                value={filters.impact_horizon}
                onChange={(e) => handleFilterChange("impact_horizon", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All</option>
                <option value="immediate">Immediate (0-1 day)</option>
                <option value="short_term">Short-term (1-30 days)</option>
                <option value="medium_term">Medium-term (1-6 months)</option>
                <option value="long_term">Long-term (6+ months)</option>
                <option value="unknown">Unknown</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Geography</label>
              <select
                value={filters.geography}
                onChange={(e) => handleFilterChange("geography", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All</option>
                <option value="IN">India</option>
                <option value="US">US</option>
                <option value="EU">EU</option>
                <option value="GLOBAL">Global</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Min Confidence</label>
              <select
                value={filters.min_confidence}
                onChange={(e) => handleFilterChange("min_confidence", e.target.value)}
                className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
              >
                <option value="">All</option>
                <option value="0.3">30%</option>
                <option value="0.5">50%</option>
                <option value="0.7">70%</option>
                <option value="0.8">80%</option>
                <option value="0.9">90%</option>
              </select>
            </div>
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-1">Date Range</label>
              <div className="flex gap-2">
                <input
                  type="date"
                  value={filters.date_from}
                  onChange={(e) => handleFilterChange("date_from", e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
                <input
                  type="date"
                  value={filters.date_to}
                  onChange={(e) => handleFilterChange("date_to", e.target.value)}
                  className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500"
                />
              </div>
            </div>
          </div>
        </div>

        {/* Events Table */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200">
          <div className="p-4 border-b border-gray-200 flex items-center justify-between">
            <h2 className="text-lg font-semibold text-gray-900">
              Intelligence Events ({total})
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
          ) : events.length === 0 ? (
            <div className="p-12 text-center text-gray-500">
              <svg className="mx-auto h-12 w-12 text-gray-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
              </svg>
              <p className="mt-2 text-lg">No intelligence events found</p>
              <p className="text-sm">Try adjusting your filters</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead>
                  <tr className="text-left text-gray-500 border-b bg-gray-50">
                    <th className="p-3 font-medium">Summary</th>
                    <th className="p-3 font-medium">Type</th>
                    <th className="p-3 font-medium">Time</th>
                    <th className="p-3 font-medium">Geo</th>
                    <th className="p-3 font-medium">Direction</th>
                    <th className="p-3 font-medium">Horizon</th>
                    <th className="p-3 font-medium">Confidence</th>
                    <th className="p-3 font-medium">Sectors</th>
                    <th className="p-3 font-medium">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {events.map((event) => (
                    <tr key={event.id} className="hover:bg-gray-50 cursor-pointer" onClick={() => handleViewDetail(event)}>
                      <td className="p-3 max-w-md">
                        <div className="font-medium text-gray-900 truncate" title={event.factual_summary}>
                          {event.factual_summary}
                        </div>
                        <div className="text-sm text-gray-500 truncate mt-1">
                          Entities: {event.entities.slice(0, 3).map(e => e.text).join(", ")}
                          {event.entities.length > 3 && ` +${event.entities.length - 3} more`}
                        </div>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${EVENT_TYPE_COLORS[event.event_type] || "bg-gray-100 text-gray-800"}`}>
                          {event.event_type.replace("_", " ")}
                        </span>
                      </td>
                      <td className="p-3 text-sm text-gray-600">
                        {formatRelativeTime(event.timestamp)}
                      </td>
                      <td className="p-3 text-sm text-gray-600">{event.geography}</td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${DIRECTION_COLORS[event.impact_direction] || "bg-gray-100 text-gray-800"}`}>
                          {event.impact_direction}
                        </span>
                      </td>
                      <td className="p-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${HORIZON_COLORS[event.impact_horizon] || "bg-gray-100 text-gray-800"}`}>
                          {event.impact_horizon.replace("_", " ")}
                        </span>
                      </td>
                      <td className="p-3 text-sm text-gray-900 font-medium">
                        {(event.confidence * 100).toFixed(0)}%
                      </td>
                      <td className="p-3 text-sm text-gray-500">
                        {event.sectors.slice(0, 2).join(", ")}
                        {event.sectors.length > 2 && ` +${event.sectors.length - 2}`}
                      </td>
                      <td className="p-3">
                        <button
                          onClick={(e) => { e.stopPropagation(); handleViewDetail(event); }}
                          className="text-indigo-600 hover:text-indigo-800 text-sm font-medium"
                        >
                          View Detail
                        </button>
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

      {/* Event Detail Modal */}
      {selectedEvent && (
        <EventDetailModal
          event={selectedEvent}
          loading={detailLoading}
          onClose={() => setSelectedEvent(null)}
        />
      )}
    </div>
  );
}

interface StatCardProps {
  title: string;
  value: string | number;
  icon: string;
  color: string;
}

function StatCard({ title, value, icon, color }: StatCardProps) {
  const colorMap: Record<string, string> = {
    indigo: "bg-indigo-100 text-indigo-800",
    green: "bg-green-100 text-green-800",
    blue: "bg-blue-100 text-blue-800",
    amber: "bg-amber-100 text-amber-800",
    purple: "bg-purple-100 text-purple-800",
  };

  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-4">
      <div className="flex items-center gap-3">
        <div className={`p-2 rounded-lg ${colorMap[color] || "bg-gray-100 text-gray-800"}`}>
          <span className="text-2xl">{icon}</span>
        </div>
        <div>
          <p className="text-sm text-gray-500">{title}</p>
          <p className="text-2xl font-bold text-gray-900">{value}</p>
        </div>
      </div>
    </div>
  );
}

interface EventDetailModalProps {
  event: any;
  loading: boolean;
  onClose: () => void;
}

function EventDetailModal({ event, loading, onClose }: EventDetailModalProps) {
  if (!event) return null;

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50" onClick={onClose}>
      <div className="bg-white rounded-xl max-w-5xl w-full max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="p-4 border-b flex items-center justify-between sticky top-0 bg-white z-10">
          <h3 className="text-lg font-semibold">{event.factual_summary}</h3>
          <button onClick={onClose} className="text-gray-500 hover:text-gray-700 text-2xl">×</button>
        </div>
        <div className="p-4 space-y-4">
          {/* Header Meta */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <MetaItem label="Event ID" value={event.event_id} />
            <MetaItem label="Type" value={event.event_type.replace("_", " ")} />
            <MetaItem label="Geography" value={event.geography} />
            <MetaItem label="Timestamp" value={formatDate(event.timestamp)} />
            <MetaItem label="Direction" value={
              <span className={`px-2 py-0.5 text-xs rounded-full ${DIRECTION_COLORS[event.impact_direction] || ""}`}>
                {event.impact_direction}
              </span>
            } />
            <MetaItem label="Horizon" value={
              <span className={`px-2 py-0.5 text-xs rounded-full ${HORIZON_COLORS[event.impact_horizon] || ""}`}>
                {event.impact_horizon.replace("_", " ")}
              </span>
            } />
            <MetaItem label="Confidence" value={`${(event.confidence * 100).toFixed(1)}%`} />
            <MetaItem label="Uncertainty" value={`${(event.uncertainty * 100).toFixed(1)}%`} />
          </div>

          {/* Factual Summary */}
          <div>
            <h4 className="font-medium mb-2">Factual Summary</h4>
            <p className="text-gray-700">{event.factual_summary}</p>
          </div>

          {/* Entities */}
          {event.entities && event.entities.length > 0 && (
            <div>
              <h4 className="font-medium mb-2">Identified Entities ({event.entities.length})</h4>
              <div className="flex flex-wrap gap-2">
                {event.entities.map((e: any, i: number) => (
                  <EntityBadge key={i} entity={e} />
                ))}
              </div>
            </div>
          )}

          {/* Sectors/Industries */}
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <MetaGroup label="Sectors" items={event.sectors} />
            <MetaGroup label="Industries" items={event.industries} />
            <MetaGroup label="Commodities" items={event.commodities} />
            <MetaGroup label="Currencies" items={event.currencies} />
          </div>

          {/* Direct Impacts */}
          {event.direct_impacts && event.direct_impacts.length > 0 && (
            <ImpactSection
              title="Direct Impacts"
              impacts={event.direct_impacts}
              color="blue"
            />
          )}

          {/* Indirect Impacts */}
          {event.indirect_impacts && event.indirect_impacts.length > 0 && (
            <ImpactSection
              title="Indirect Impacts"
              impacts={event.indirect_impacts}
              color="purple"
            />
          )}

          {/* Beneficiaries */}
          {event.possible_beneficiaries && event.possible_beneficiaries.length > 0 && (
            <ImpactSection
              title="Possible Beneficiaries"
              impacts={event.possible_beneficiaries}
              color="green"
            />
          )}

          {/* Negative Exposures */}
          {event.possible_negative_exposures && event.possible_negative_exposures.length > 0 && (
            <ImpactSection
              title="Possible Negative Exposures"
              impacts={event.possible_negative_exposures}
              color="red"
            />
          )}

          {/* Causal Chain */}
          {event.causal_chain && event.causal_chain.length > 0 && (
            <div>
              <h4 className="font-medium mb-2">Causal Chain</h4>
              <div className="space-y-2">
                {event.causal_chain.map((step: CausalStep, i: number) => (
                  <div key={i} className="bg-gray-50 p-3 rounded-lg border-l-4 border-indigo-500">
                    <div className="flex items-start gap-3">
                      <span className="px-2 py-0.5 text-xs rounded-full bg-indigo-100 text-indigo-800 font-medium">
                        Step {step.step}
                      </span>
                      <div className="flex-1">
                        <p className="font-medium text-gray-900">{step.cause}</p>
                        <p className="text-gray-600">→ {step.effect}</p>
                        <div className="flex items-center gap-2 mt-1 text-xs text-gray-500">
                          <span className={`px-1.5 py-0.5 rounded ${EDGE_TYPE_COLORS[step.type?.toLowerCase()] || ""}`}>
                            {step.type}
                          </span>
                          <span>Confidence: {step.confidence}</span>
                          {step.evidence_refs && step.evidence_refs.length > 0 && (
                            <span>Evidence: {step.evidence_refs.slice(0, 3).join(", ")}</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Validation & Confidence */}
          {event.validation && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium mb-2">Validation Status</h4>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <MetaItem
                  label="Passed"
                  value={event.validation.passed ? "✅ Yes" : "❌ No"}
                />
                <MetaItem
                  label="Score"
                  value={`${Math.round((event.validation.score || 0) * 100)}%`}
                />
                <MetaItem
                  label="Citation Valid"
                  value={event.validation.citation_valid ? "✅" : "❌"}
                />
                <MetaItem
                  label="Abstained"
                  value={event.validation.abstained ? "⚠️ Yes" : "✅ No"}
                />
              </div>
            </div>
          )}

          {event.confidence_details && (
            <div className="bg-gray-50 p-4 rounded-lg">
              <h4 className="font-medium mb-2">Confidence Breakdown</h4>
              <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
                <ConfidenceBar
                  label="Source Reliability"
                  value={event.confidence_details.components?.source_reliability || 0}
                />
                <ConfidenceBar
                  label="Corroboration"
                  value={Math.min((event.confidence_details.components?.corroboration_count || 0) / 5, 1)}
                />
                <ConfidenceBar
                  label="Evidence Coverage"
                  value={event.confidence_details.components?.evidence_coverage || 0}
                />
                <ConfidenceBar
                  label="Entity Resolution"
                  value={event.confidence_details.components?.entity_resolution_certainty || 0}
                />
                <ConfidenceBar
                  label="Retrieval Score"
                  value={event.confidence_details.components?.retrieval_score || 0}
                />
              </div>
            </div>
          )}

          {/* Why am I seeing this? */}
          <div className="bg-indigo-50 p-4 rounded-lg border border-indigo-200">
            <h4 className="font-medium text-indigo-800 mb-2">Why am I seeing this?</h4>
            <ul className="text-sm text-indigo-700 space-y-1">
              <li>• This event was classified as <strong>{event.event_type.replace("_", " ")}</strong> with <strong>{(event.confidence * 100).toFixed(0)}% confidence</strong></li>
              <li>• It affects <strong>{event.sectors.join(", ")}</strong> sector(s)</li>
              <li>• Impact direction: <strong>{event.impact_direction}</strong> over <strong>{event.impact_horizon.replace("_", " ")}</strong></li>
              <li>• Based on <strong>{event.source_ids.length}</strong> evidence source(s)</li>
              {event.validation?.abstained && (
                <li className="text-amber-700">• ⚠️ <strong>Abstention:</strong> {event.validation.abstention_reason}</li>
              )}
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}

function MetaItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-sm font-medium text-gray-900">{value}</p>
    </div>
  );
}

function MetaGroup({ label, items }: { label: string; items: string[] }) {
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="flex flex-wrap gap-1">
        {items.map((item, i) => (
          <span key={i} className="px-2 py-0.5 text-xs bg-gray-100 text-gray-700 rounded">
            {item}
          </span>
        ))}
      </div>
    </div>
  );
}

function ImpactSection({ title, impacts, color }: { title: string; impacts: Impact[]; color: string }) {
  const colorMap: Record<string, string> = {
    blue: "bg-blue-50 border-blue-200 text-blue-800",
    green: "bg-green-50 border-green-200 text-green-800",
    purple: "bg-purple-50 border-purple-200 text-purple-800",
    red: "bg-red-50 border-red-200 text-red-800",
  };

  return (
    <div className={`border ${colorMap[color] || "border-gray-200"} rounded-lg p-4`}>
      <h4 className={`font-medium mb-2 ${colorMap[color] || ""}`}>{title} ({impacts.length})</h4>
      <div className="space-y-2">
        {impacts.map((impact: Impact, i: number) => (
          <div key={i} className="bg-white p-3 rounded border">
            <div className="flex items-start gap-2">
              <div className="flex-1">
                <p className="font-medium">{impact.entity}</p>
                {impact.ticker && <p className="text-sm text-gray-500">{impact.ticker}</p>}
                <p className="text-sm text-gray-600 mt-1">{impact.reasoning || impact.impact}</p>
                {impact.evidence_refs && impact.evidence_refs.length > 0 && (
                  <p className="text-xs text-gray-400 mt-1">Evidence: {impact.evidence_refs.slice(0, 3).join(", ")}</p>
                )}
              </div>
              <span className={`px-2 py-0.5 text-xs rounded-full ${colorMap[color] || ""}`}>
                {impact.direction || impact.impact}
              </span>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function EntityBadge({ entity }: { entity: any }) {
  const resolved = entity.resolved;
  return (
    <span className="px-2 py-0.5 text-xs rounded-full bg-indigo-100 text-indigo-800">
      {entity.text} ({entity.label})
      {resolved && <span className="ml-1">→ {resolved.company_name}</span>}
    </span>
  );
}

function ConfidenceBar({ label, value }: { label: string; value: number }) {
  const pct = Math.round(value * 100);
  return (
    <div>
      <p className="text-xs text-gray-500 mb-1">{label}</p>
      <div className="h-2 bg-gray-200 rounded-full overflow-hidden">
        <div
          className="h-full bg-indigo-600 rounded-full transition-all"
          style={{ width: `${pct}%` }}
        />
      </div>
      <p className="text-xs font-medium text-gray-600 mt-0.5">{pct}%</p>
    </div>
  );
}