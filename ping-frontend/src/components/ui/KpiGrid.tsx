import type { Kpi } from "@/lib/types";

export function KpiGrid({ items }: { items: Kpi[] }) {
  return (
    <div className="kpi-grid">
      {items.map((k) => (
        <div key={k.label} className="kpi">
          <span className="kpi-label">{k.label}</span>
          <span className="kpi-value-row">
            <span className="kpi-value">{k.value}</span>
            <span className={`delta delta-${k.tone}`}>{k.delta}</span>
          </span>
          <span className="kpi-sub">{k.sub}</span>
        </div>
      ))}
    </div>
  );
}
