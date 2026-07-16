import EvidenceCitation from "./EvidenceCitation";

interface CausalStep {
  step: number;
  cause: string;
  effect: string;
  evidence_refs?: string[];
  confidence?: string;
  type?: string;
}

interface CausalChainProps {
  steps: CausalStep[];
}

const EDGE_TYPE_STYLES: Record<string, string> = {
  verified: "border-l-accent-green",
  inferred: "border-l-accent-amber",
  uncertain: "border-l-accent-red",
};

export default function CausalChain({ steps }: CausalChainProps) {
  if (!steps || steps.length === 0) return null;

  return (
    <div className="space-y-2">
      {steps.map((step, i) => (
        <div
          key={i}
          className={`bg-surface-alt border-l-2 rounded-lg p-3 ${
            (step.type ? EDGE_TYPE_STYLES[step.type.toLowerCase()] : undefined) || "border-l-accent-blue"
          }`}
        >
          <div className="flex items-start gap-3">
            <span className="badge-blue text-2xs shrink-0">
              Step {step.step}
            </span>
            <div className="min-w-0">
              <p className="text-sm font-medium text-fg">{step.cause}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-fg-dim">→</span>
                <p className="text-sm text-fg-muted">{step.effect}</p>
              </div>
              <div className="flex items-center gap-3 mt-1.5 text-2xs text-fg-dim">
                {step.type && (
                  <span className="badge-neutral">{step.type}</span>
                )}
                {step.confidence && (
                  <span>Conf: {step.confidence}</span>
                )}
                <EvidenceCitation refs={step.evidence_refs} />
              </div>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
