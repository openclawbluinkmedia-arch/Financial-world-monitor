interface ImpactBadgeProps {
  direction?: string;
  label?: string;
  size?: "sm" | "md";
}

const DIRECTION_STYLES: Record<string, string> = {
  positive: "badge-green",
  negative: "badge-red",
  neutral: "badge-neutral",
  mixed: "badge-amber",
  uncertain: "badge-amber",
  unknown: "badge-neutral",
  beneficiary: "badge-green",
  "negative exposure": "badge-red",
};

const DIRECTION_LABELS: Record<string, string> = {
  positive: "Beneficiary",
  negative: "Negative",
  beneficiary: "Beneficiary",
  "negative exposure": "Negative",
  neutral: "Neutral",
  mixed: "Mixed",
  uncertain: "Uncertain",
};

export default function ImpactBadge({
  direction = "unknown",
  label,
  size = "sm",
}: ImpactBadgeProps) {
  const style =
    DIRECTION_STYLES[direction.toLowerCase()] || "badge-neutral";
  const displayLabel =
    label || DIRECTION_LABELS[direction.toLowerCase()] || direction;

  return (
    <span className={`${style} ${size === "md" ? "text-xs px-2.5 py-1" : "text-2xs"}`}>
      {displayLabel}
    </span>
  );
}
