import ImpactBadge from "./ImpactBadge";
import ConfidenceBar from "./ConfidenceBar";
import EvidenceCitation from "./EvidenceCitation";

interface EventCardImpact {
  entity: string;
  ticker?: string;
  impact: string;
  direction: string;
  reasoning?: string;
  evidence_refs?: string[];
}

interface EventCardProps {
  id: string;
  summary: string;
  event_type: string;
  timestamp: string;
  geography: string;
  impact_direction: string;
  impact_horizon: string;
  confidence: number;
  sectors: string[];
  direct_impacts?: EventCardImpact[];
  possible_beneficiaries?: EventCardImpact[];
  possible_negative_exposures?: EventCardImpact[];
  causal_chain?: any[];
  onClick?: () => void;
}

function formatRelative(ts: string): string {
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

export default function EventCard({
  summary,
  event_type,
  timestamp,
  geography,
  impact_direction,
  impact_horizon,
  confidence,
  sectors,
  direct_impacts,
  possible_beneficiaries,
  possible_negative_exposures,
  onClick,
}: EventCardProps) {
  return (
    <div
      className="card p-4 cursor-pointer hover:bg-surface-hover transition-colors"
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-3 mb-2">
        <p className="text-sm font-medium text-fg leading-snug line-clamp-2">
          {summary}
        </p>
        <ImpactBadge direction={impact_direction} />
      </div>

      <div className="flex flex-wrap items-center gap-2 text-2xs text-fg-dim mb-3">
        <span className="badge-blue">{event_type.replace("_", " ")}</span>
        <span>{formatRelative(timestamp)}</span>
        <span>{geography}</span>
        <span className="font-mono">
          {impact_horizon.replace("_", " ")}
        </span>
        <span>•</span>
        {sectors.slice(0, 2).map((s) => (
          <span key={s} className="badge-neutral">{s}</span>
        ))}
      </div>

      <div className="mb-3">
        <ConfidenceBar label="Confidence" value={confidence} />
      </div>

      {(possible_beneficiaries && possible_beneficiaries.length > 0) ||
      (possible_negative_exposures && possible_negative_exposures.length > 0) ? (
        <div className="flex flex-wrap gap-1.5 mb-2">
          {possible_beneficiaries?.slice(0, 3).map((imp, i) => (
            <span key={i} className="badge-green text-2xs">
              {imp.entity}
            </span>
          ))}
          {possible_negative_exposures?.slice(0, 3).map((imp, i) => (
            <span key={i} className="badge-red text-2xs">
              {imp.entity}
            </span>
          ))}
        </div>
      ) : null}

      {direct_impacts && direct_impacts.length > 0 && (
        <EvidenceCitation refs={direct_impacts[0]?.evidence_refs} />
      )}
    </div>
  );
}
