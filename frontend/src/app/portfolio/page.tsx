"use client";

import { useEffect, useState, useCallback } from "react";
import { fetchApi, getPortfolios, type Portfolio } from "@/lib/api";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import LiveIndicator from "../components/LiveIndicator";

export default function PortfolioPage() {
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [selected, setSelected] = useState<Portfolio | null>(null);

  const apiUrl = process.env.NEXT_PUBLIC_API_URL;

  const fetchAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPortfolios(await getPortfolios());
    } catch (e: any) {
      setError(e.message || "Failed to load portfolios");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchAll(); }, [fetchAll]);

  const totalValue = portfolios.reduce((s, p) => s + (p.total_value || 0), 0);
  const totalHoldings = portfolios.reduce((s, p) => s + (p.holding_count || 0), 0);

  return (
    <div className="page-container">
      {!apiUrl && (
        <div className="mb-4 px-4 py-3 bg-accent-amber-bg border border-accent-amber-border rounded-lg text-sm text-accent-amber text-center">
          ⚠ NEXT_PUBLIC_API_URL is not configured. Using fallback http://localhost:8000
        </div>
      )}

      <PageHeader title="Portfolios" subtitle="Track holdings and exposure"
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

      {loading && portfolios.length === 0 && (
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
          {[1,2,3].map((i) => <div key={i} className="card p-4 animate-pulse"><div className="h-3 bg-surface-hover rounded w-1/3 mb-2" /><div className="h-6 bg-surface-hover rounded w-1/2" /></div>)}
        </div>
      )}

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard label="Portfolios" value={portfolios.length} accent="blue" mono />
        <StatCard label="Total Holdings" value={totalHoldings} accent="purple" mono />
        <StatCard label="Total Value" value={totalValue ? `₹${(totalValue / 1e7).toFixed(1)}Cr` : "—"} accent="green" mono />
      </div>

      <div className="card">
        <div className="card-header">
          <span className="text-sm font-medium text-fg">Portfolio List</span>
        </div>
        <div className="divide-y divide-surface-border">
          {loading && portfolios.length === 0 ? (
            [1,2,3].map((i) => (
              <div key={i} className="card p-4 animate-pulse">
                <div className="h-4 bg-surface-hover rounded w-1/3 mb-2" />
                <div className="h-3 bg-surface-hover rounded w-1/4" />
              </div>
            ))
          ) : portfolios.length === 0 ? (
            <div className="p-6 text-center text-fg-dim text-sm">No portfolios yet</div>
          ) : (
            portfolios.map((p) => (
              <div key={p.id} className="card p-4 hover:bg-surface-hover transition-colors cursor-pointer" onClick={() => setSelected(p)}>
                <div className="flex items-start justify-between">
                  <div>
                    <p className="text-sm font-medium text-fg">{p.name}</p>
                    {p.description && <p className="text-2xs text-fg-dim mt-0.5">{p.description}</p>}
                  </div>
                  <div className="text-right">
                    <p className="text-sm font-mono text-fg">{p.holding_count || 0} holdings</p>
                    {p.total_value != null && <p className="text-2xs text-fg-dim">₹{(p.total_value / 1e7).toFixed(1)}Cr</p>}
                  </div>
                </div>
                <div className="flex gap-3 mt-2 text-2xs text-fg-dim">
                  {p.created_at && <span>Created: {new Date(p.created_at).toLocaleDateString()}</span>}
                  {p.updated_at && <span>Updated: {new Date(p.updated_at).toLocaleDateString()}</span>}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center p-4 z-50" onClick={() => setSelected(null)}>
          <div className="card max-w-lg w-full" onClick={(e) => e.stopPropagation()}>
            <div className="card-header">
              <h3 className="text-sm font-semibold text-fg">{selected.name}</h3>
              <button onClick={() => setSelected(null)} className="text-fg-dim hover:text-fg text-lg leading-none">✕</button>
            </div>
            <div className="card-body space-y-3">
              {selected.description && <div><p className="text-2xs text-fg-dim">Description</p><p className="text-sm text-fg">{selected.description}</p></div>}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div><p className="text-2xs text-fg-dim">Holdings</p><p className="font-mono text-fg">{selected.holding_count || 0}</p></div>
                <div><p className="text-2xs text-fg-dim">Total Value</p><p className="font-mono text-fg">{selected.total_value != null ? `₹${(selected.total_value / 1e7).toFixed(1)}Cr` : "—"}</p></div>
              </div>
              <div className="flex gap-3 text-2xs text-fg-dim">
                {selected.created_at && <span>Created: {new Date(selected.created_at).toLocaleString()}</span>}
                {selected.updated_at && <span>Updated: {new Date(selected.updated_at).toLocaleString()}</span>}
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
