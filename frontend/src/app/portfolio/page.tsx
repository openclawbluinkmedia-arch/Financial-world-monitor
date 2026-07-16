"use client";

import { useState, useEffect, useCallback } from "react";
import PageHeader from "../components/PageHeader";
import StatCard from "../components/StatCard";
import DataTable from "../components/DataTable";
import ImpactBadge from "../components/ImpactBadge";

interface Portfolio {
  id: string;
  portfolio_id: string;
  name: string;
  description: string | null;
  created_at: string;
  holdings_count: number;
  total_market_value: number | null;
}

interface Holding {
  id: string;
  ticker: string;
  name: string;
  exchange: string;
  quantity: number;
  market_value: number | null;
  allocation_pct: number;
  sector: string | null;
}

function relativeTime(ts: string): string {
  try {
    const diff = Date.now() - new Date(ts).getTime();
    const d = Math.floor(diff / 86400000);
    const h = Math.floor(diff / 3600000);
    if (d > 0) return `${d}d ago`;
    if (h > 0) return `${h}h ago`;
    return "today";
  } catch {
    return ts;
  }
}

export default function PortfolioPage() {
  const [portfolios, setPortfolios] = useState<Portfolio[]>([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState<Portfolio | null>(null);
  const [holdings, setHoldings] = useState<Holding[]>([]);
  const [holdingsLoading, setHoldingsLoading] = useState(false);

  const fetchPortfolios = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/portfolios");
      setPortfolios(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPortfolios();
  }, [fetchPortfolios]);

  const handleSelectPortfolio = async (p: Portfolio) => {
    setSelected(p);
    setHoldingsLoading(true);
    try {
      const res = await fetch(`/api/portfolios/${p.id}/holdings`);
      setHoldings(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setHoldingsLoading(false);
    }
  };

  const portfolioColumns = [
    { key: "name", label: "Name", render: (row: Portfolio) => (
      <div>
        <p className="text-sm font-medium text-fg">{row.name}</p>
        {row.description && (
          <p className="text-2xs text-fg-dim truncate max-w-xs">{row.description}</p>
        )}
      </div>
    )},
    { key: "holdings_count", label: "Holdings", render: (row: Portfolio) => (
      <span className="font-mono text-sm text-fg">{row.holdings_count}</span>
    )},
    {
      key: "total_market_value",
      label: "Market Value",
      render: (row: Portfolio) => (
        <span className="font-mono text-sm text-fg">
          {row.total_market_value
            ? `$${row.total_market_value.toLocaleString()}`
            : "—"}
        </span>
      ),
    },
    {
      key: "created_at",
      label: "Created",
      render: (row: Portfolio) => (
        <span className="text-2xs text-fg-dim">{relativeTime(row.created_at)}</span>
      ),
    },
    {
      key: "actions",
      label: "",
      render: (row: Portfolio) => (
        <button
          onClick={(e) => {
            e.stopPropagation();
            handleSelectPortfolio(row);
          }}
          className="btn-ghost text-2xs"
        >
          Holdings
        </button>
      ),
    },
  ];

  const holdingColumns = [
    { key: "ticker", label: "Ticker", render: (row: Holding) => (
      <span className="font-mono text-sm text-fg font-medium">{row.ticker}</span>
    )},
    { key: "name", label: "Name" },
    { key: "exchange", label: "Exchange", render: (row: Holding) => (
      <span className="badge-neutral text-2xs">{row.exchange}</span>
    )},
    { key: "quantity", label: "Qty", render: (row: Holding) => (
      <span className="font-mono text-sm text-fg">{row.quantity}</span>
    )},
    {
      key: "market_value",
      label: "Market Value",
      render: (row: Holding) => (
        <span className="font-mono text-sm text-fg">
          {row.market_value ? `$${row.market_value.toLocaleString()}` : "—"}
        </span>
      ),
    },
    {
      key: "allocation_pct",
      label: "Allocation",
      render: (row: Holding) => (
        <span className="font-mono text-sm text-fg-muted">{row.allocation_pct}%</span>
      ),
    },
    { key: "sector", label: "Sector", render: (row: Holding) => (
      row.sector ? <span className="badge-neutral text-2xs">{row.sector}</span> : <span className="text-2xs text-fg-dim">—</span>
    )},
  ];

  return (
    <div className="page-container">
      <PageHeader
        title="Portfolio"
        subtitle={`${portfolios.length} portfolio(s)`}
        actions={
          <button onClick={() => fetchPortfolios()} className="btn-primary">
            Refresh
          </button>
        }
      />

      {/* Summary stats */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-6">
        <StatCard label="Portfolios" value={portfolios.length} accent="blue" mono />
        <StatCard
          label="Total Holdings"
          value={portfolios.reduce((s, p) => s + p.holdings_count, 0)}
          accent="purple"
          mono
        />
        <StatCard
          label="Total Value"
          value={
            portfolios.some((p) => p.total_market_value)
              ? `$${portfolios
                  .reduce((s, p) => s + (p.total_market_value || 0), 0)
                  .toLocaleString()}`
              : "—"
          }
          accent="green"
        />
      </div>

      {/* Portfolio list */}
      <div className="card mb-6">
        <div className="card-header">
          <span className="text-sm font-medium text-fg">Portfolios</span>
        </div>
        <DataTable
          columns={portfolioColumns}
          data={portfolios}
          loading={loading}
          emptyMessage="No portfolios found. Upload a CSV to get started."
          onRowClick={(row) => handleSelectPortfolio(row)}
        />
      </div>

      {/* Holdings detail */}
      {selected && (
        <div className="card">
          <div className="card-header">
            <div>
              <span className="text-sm font-medium text-fg">
                {selected.name} — Holdings
              </span>
              {selected.description && (
                <p className="text-2xs text-fg-dim mt-0.5">{selected.description}</p>
              )}
            </div>
            <button
              onClick={() => setSelected(null)}
              className="btn-ghost text-xs"
            >
              Close
            </button>
          </div>
          <DataTable
            columns={holdingColumns}
            data={holdings}
            loading={holdingsLoading}
            emptyMessage="No holdings in this portfolio."
          />
        </div>
      )}
    </div>
  );
}
