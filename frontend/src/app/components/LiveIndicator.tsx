"use client";

import { useEffect, useState } from "react";

interface LiveIndicatorProps {
  label?: string;
}

export default function LiveIndicator({ label = "Live" }: LiveIndicatorProps) {
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [stale, setStale] = useState(false);

  useEffect(() => {
    setLastUpdated(new Date());
    setStale(false);
    const timer = setTimeout(() => setStale(true), 65000);
    return () => clearTimeout(timer);
  }, []);

  return (
    <div className="flex items-center gap-2 text-2xs text-fg-dim">
      <span className={`inline-block w-1.5 h-1.5 rounded-full ${stale ? "bg-accent-amber" : "bg-accent-green animate-pulse"}`} />
      <span>{stale ? "Stale" : label}</span>
      {lastUpdated && (
        <span className="font-mono">
          {lastUpdated.toLocaleTimeString()}
        </span>
      )}
    </div>
  );
}
