interface StatCardProps {
  label: string;
  value: string | number;
  accent?: "green" | "red" | "amber" | "blue" | "purple" | "cyan";
  trend?: "up" | "down" | "neutral";
  secondary?: string;
  mono?: boolean;
}

const ACCENT_BORDERS: Record<string, string> = {
  green: "border-l-accent-green",
  red: "border-l-accent-red",
  amber: "border-l-accent-amber",
  blue: "border-l-accent-blue",
  purple: "border-l-accent-purple",
  cyan: "border-l-accent-cyan",
};

const TREND_ICONS: Record<string, string> = {
  up: "↑",
  down: "↓",
  neutral: "→",
};

const TREND_COLORS: Record<string, string> = {
  up: "text-accent-green",
  down: "text-accent-red",
  neutral: "text-fg-dim",
};

export default function StatCard({
  label,
  value,
  accent = "blue",
  trend,
  secondary,
  mono = false,
}: StatCardProps) {
  return (
    <div
      className={`card border-l-2 ${ACCENT_BORDERS[accent] || "border-l-accent-blue"} p-4`}
    >
      <p className="text-2xs text-fg-dim uppercase tracking-wider mb-1">
        {label}
      </p>
      <div className="flex items-baseline gap-2">
        <span
          className={`text-2xl font-bold ${mono ? "font-mono" : ""} ${
            trend ? TREND_COLORS[trend] : "text-fg"
          }`}
        >
          {value}
        </span>
        {trend && (
          <span className={`text-sm ${TREND_COLORS[trend]}`}>
            {TREND_ICONS[trend]}
          </span>
        )}
      </div>
      {secondary && (
        <p className="text-2xs text-fg-dim mt-1">{secondary}</p>
      )}
    </div>
  );
}
