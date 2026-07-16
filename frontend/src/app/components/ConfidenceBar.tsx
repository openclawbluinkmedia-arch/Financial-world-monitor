interface ConfidenceBarProps {
  label: string;
  value: number;
  size?: "sm" | "md";
}

function colorForValue(v: number): string {
  if (v >= 0.8) return "bg-accent-green";
  if (v >= 0.5) return "bg-accent-amber";
  return "bg-accent-red";
}

export default function ConfidenceBar({
  label,
  value,
  size = "sm",
}: ConfidenceBarProps) {
  const pct = Math.round(value * 100);
  const barH = size === "sm" ? "h-1.5" : "h-2.5";

  return (
    <div>
      <div className="flex items-center justify-between mb-1">
        <span className="text-2xs text-fg-dim">{label}</span>
        <span className="text-2xs font-mono text-fg-muted">{pct}%</span>
      </div>
      <div className={`${barH} bg-surface-alt rounded-full overflow-hidden`}>
        <div
          className={`${barH} ${colorForValue(value)} rounded-full transition-all duration-500`}
          style={{ width: `${pct}%` }}
        />
      </div>
    </div>
  );
}
