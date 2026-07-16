interface EvidenceCitationProps {
  refs?: string[];
  max?: number;
}

export default function EvidenceCitation({
  refs,
  max = 3,
}: EvidenceCitationProps) {
  if (!refs || refs.length === 0) return null;

  const shown = refs.slice(0, max);
  const remaining = refs.length - max;

  return (
    <div className="flex items-center gap-1.5 text-2xs text-fg-dim">
      <span className="text-fg-faint">📄</span>
      {shown.map((ref, i) => (
        <span key={i} className="font-mono truncate max-w-[100px]" title={ref}>
          {ref.length > 12 ? ref.slice(0, 10) + "…" : ref}
        </span>
      ))}
      {remaining > 0 && <span>+{remaining}</span>}
    </div>
  );
}
