"use client";

import { useEffect, useState } from "react";

type ServiceStatus = {
  status: string;
  detail: string | null;
};

type HealthData = {
  status: string;
  mode: string;
  services: {
    postgres: ServiceStatus;
    redis: ServiceStatus;
  };
};

export default function HealthPage() {
  const [data, setData] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/health")
      .then((r) => r.json())
      .then(setData)
      .catch((e) => setError(e.message));
  }, []);

  const badge = (s: string) => {
    const color =
      s === "ok"
        ? "bg-green-100 text-green-800"
        : s === "degraded"
          ? "bg-yellow-100 text-yellow-800"
          : "bg-red-100 text-red-800";
    return (
      <span className={`inline-block px-2 py-0.5 rounded text-sm font-medium ${color}`}>
        {s}
      </span>
    );
  };

  return (
    <main className="max-w-2xl mx-auto p-8">
      <h1 className="text-2xl font-bold mb-6">System Health</h1>
      {error && <p className="text-red-600">Error: {error}</p>}
      {data && (
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <span className="font-semibold">Overall:</span>
            {badge(data.status)}
            <span className="text-sm text-gray-500">Mode: {data.mode}</span>
          </div>
          <div className="border rounded p-4 space-y-2">
            <h2 className="font-semibold">Services</h2>
            <div className="flex justify-between">
              <span>PostgreSQL</span>
              {badge(data.services.postgres.status)}
            </div>
            <div className="flex justify-between">
              <span>Redis</span>
              {badge(data.services.redis.status)}
            </div>
          </div>
        </div>
      )}
      {!data && !error && <p>Loading...</p>}
    </main>
  );
}
