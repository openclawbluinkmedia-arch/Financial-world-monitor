interface FilterDef {
  key: string;
  label: string;
  type: "text" | "select" | "date";
  options?: { value: string; label: string }[];
  placeholder?: string;
}

interface FilterBarProps {
  filters: Record<string, string>;
  definitions: FilterDef[];
  onChange: (key: string, value: string) => void;
}

export default function FilterBar({
  filters,
  definitions,
  onChange,
}: FilterBarProps) {
  return (
    <div className="card p-4">
      <p className="section-title">Filters</p>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-6 gap-3">
        {definitions.map((def) => (
          <div key={def.key}>
            <label className="block text-2xs text-fg-dim uppercase tracking-wider mb-1">
              {def.label}
            </label>
            {def.type === "select" ? (
              <select
                value={filters[def.key] || ""}
                onChange={(e) => onChange(def.key, e.target.value)}
                className="w-full"
              >
                {def.options?.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : def.type === "date" ? (
              <input
                type="date"
                value={filters[def.key] || ""}
                onChange={(e) => onChange(def.key, e.target.value)}
                className="w-full"
              />
            ) : (
              <input
                type="text"
                value={filters[def.key] || ""}
                onChange={(e) => onChange(def.key, e.target.value)}
                placeholder={def.placeholder}
                className="w-full"
              />
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
