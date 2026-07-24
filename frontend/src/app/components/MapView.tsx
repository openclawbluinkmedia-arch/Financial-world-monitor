"use client";

import { useState } from "react";
import {
  ComposableMap,
  Geographies,
  Geography,
  Marker,
} from "react-simple-maps";

const GEO_URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json";

export interface MapEvent {
  id: string;
  title?: string;
  summary?: string;
  lat: number;
  lng: number;
  impact_direction?: string;
  confidence?: number;
  source_name?: string;
  timestamp?: string;
  geography?: string;
}

interface MapViewProps {
  events: MapEvent[];
  onEventClick?: (id: string) => void;
  height?: number;
}

function dotColor(direction?: string): string {
  switch (direction) {
    case "positive":
    case "beneficiary":
      return "#22c55e";
    case "negative":
    case "negative exposure":
      return "#ef4444";
    case "mixed":
    case "uncertain":
      return "#f59e0b";
    default:
      return "#6b7080";
  }
}

function dotSize(confidence?: number): number {
  if (!confidence) return 4;
  if (confidence >= 0.8) return 8;
  if (confidence >= 0.5) return 6;
  return 4;
}

export default function MapView({ events, onEventClick, height = 400 }: MapViewProps) {
  const [tooltip, setTooltip] = useState<{ ev: MapEvent; x: number; y: number } | null>(null);

  const validEvents = events.filter((e) => e.lat != null && e.lng != null);

  return (
    <div className="relative" style={{ height }}>
      <ComposableMap
        projection="geoMercator"
        projectionConfig={{ scale: 120, center: [20, 20] }}
        style={{ width: "100%", height: "100%" }}
      >
        <Geographies geography={GEO_URL}>
          {({ geographies }) =>
            geographies.map((geo) => (
              <Geography
                key={geo.rsmKey}
                geography={geo}
                style={{
                  default: { fill: "#1e2130", stroke: "#2e3140", strokeWidth: 0.5, outline: "none" },
                  hover: { fill: "#252836", outline: "none" },
                  pressed: { outline: "none" },
                }}
              />
            ))
          }
        </Geographies>
        {validEvents.map((ev) => (
          <Marker
            key={ev.id}
            coordinates={[ev.lng, ev.lat]}
            onMouseEnter={(e: any) => {
              const rect = (e.target as SVGElement).closest("svg")?.getBoundingClientRect();
              setTooltip({
                ev,
                x: (rect?.left || 0) + 60,
                y: (rect?.top || 0) + 20,
              });
            }}
            onMouseLeave={() => setTooltip(null)}
            onClick={() => onEventClick?.(ev.id)}
          >
            <g style={{ cursor: "pointer" }}>
              <circle
                r={dotSize(ev.confidence)}
                fill={dotColor(ev.impact_direction)}
                opacity={0.3}
                className="animate-ping"
                style={{ animationDuration: "2s" }}
              />
              <circle
                r={dotSize(ev.confidence)}
                fill={dotColor(ev.impact_direction)}
                opacity={0.9}
              />
            </g>
          </Marker>
        ))}
      </ComposableMap>

      {validEvents.length === 0 && (
        <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
          <div className="text-center text-fg-dim">
            <svg className="w-12 h-12 mx-auto mb-2 opacity-30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1} d="M3.055 11H5a2 2 0 012 2v1a2 2 0 002 2 2 2 0 012 2v2.945M8 3.935V5.5A2.5 2.5 0 0010.5 8h.5a2 2 0 012 2 2 2 0 104 0 2 2 0 012-2h1.064M15 20.488V18a2 2 0 012-2h3.064M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <p className="text-xs">No geospatial events yet</p>
          </div>
        </div>
      )}

      {tooltip && (
        <div
          className="absolute z-50 card p-2 pointer-events-none text-xs"
          style={{ left: tooltip.x + 12, top: tooltip.y - 10 }}
        >
          <p className="text-fg font-medium max-w-[200px] truncate">
            {tooltip.ev.title || tooltip.ev.summary || "Event"}
          </p>
          <div className="flex items-center gap-2 text-2xs text-fg-dim mt-0.5">
            {tooltip.ev.source_name && <span>{tooltip.ev.source_name}</span>}
            {tooltip.ev.timestamp && (
              <span>{new Date(tooltip.ev.timestamp).toLocaleDateString()}</span>
            )}
            {tooltip.ev.geography && <span>{tooltip.ev.geography}</span>}
          </div>
        </div>
      )}
    </div>
  );
}
