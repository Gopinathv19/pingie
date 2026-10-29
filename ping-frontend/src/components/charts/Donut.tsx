import c from "./charts.module.css";

export interface DonutSlice {
  label: string;
  pct: number;
  color: string;
}

const R = 52;
const C = 2 * Math.PI * R;

export function Donut({ items, value, label }: { items: DonutSlice[]; value: string; label: string }) {
  let offset = 0;
  const segments = items.map((o) => {
    const len = (o.pct / 100) * C;
    const seg = { color: o.color, dash: Math.max(len - 1, 0), offset: -offset };
    offset += len;
    return seg;
  });

  return (
    <div className={c.donutWrap}>
      <svg
        role="img"
        aria-label={`Donut chart: ${items.map((o) => `${o.pct}% ${o.label.toLowerCase()}`).join(", ")}`}
        width="170"
        height="170"
        viewBox="0 0 140 140"
      >
        <circle cx="70" cy="70" r={R} fill="none" style={{ stroke: "var(--grid)" }} strokeWidth="18" />
        {segments.map((s) => (
          s.dash > 0 && <circle
            key={s.color}
            cx="70"
            cy="70"
            r={R}
            fill="none"
            stroke={s.color}
            strokeWidth="18"
            strokeDasharray={`${s.dash.toFixed(1)} ${C.toFixed(1)}`}
            strokeDashoffset={s.offset.toFixed(1)}
            transform="rotate(-90 70 70)"
          />
        ))}
      </svg>
      <div className={c.donutCenter}>
        <span className={c.donutValue}>{value}</span>
        <span className={c.donutLabel}>{label}</span>
      </div>
    </div>
  );
}
