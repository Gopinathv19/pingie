"use client";

import { useState } from "react";
import type { SeriesPoint } from "@/lib/types";
import c from "./charts.module.css";

const W = 800;
const H = 220;
const BASE = 218;

function niceMax(max: number) {
  const raw = Math.max(max, 1) * 1.3 / 4;
  const pow = 10 ** Math.floor(Math.log10(raw));
  const step = [1, 2, 2.5, 5, 10].find((m) => m * pow >= raw)! * pow;
  return step * 4;
}

export function LineChart({ points }: { points: SeriesPoint[] }) {
  const n = points.length;
  const defaultIdx = n - 1; // the most recent point
  const [hover, setHover] = useState<number | null>(null);
  const idx = hover ?? defaultIdx;

  const max = niceMax(Math.max(...points.map((p) => p.conversations)));
  const x = (i: number) => (i / (n - 1)) * W;
  const y = (v: number) => BASE - (v / max) * (BASE - 2);
  const line = (key: "conversations" | "unanswered") =>
    points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)},${y(p[key]).toFixed(1)}`).join(" ");
  const conv = line("conversations");
  const ticks = [max, (max * 3) / 4, max / 2, max / 4, 0];
  const xLabels = [0, Math.round((n - 1) / 3), Math.round((2 * (n - 1)) / 3), n - 1];
  const p = points[idx];

  return (
    <>
      <div className={c.plotRow}>
        <div aria-hidden="true" className={c.yAxis}>
          {ticks.map((t) => (
            <span key={t}>{t}</span>
          ))}
        </div>
        <div
          className={c.plot}
          onMouseMove={(e) => {
            const r = e.currentTarget.getBoundingClientRect();
            setHover(Math.round(((e.clientX - r.left) / r.width) * (n - 1)));
          }}
          onMouseLeave={() => setHover(null)}
        >
          <svg
            role="img"
            aria-label={`Line chart of conversations and unanswered questions across ${n} points`}
            width="100%"
            height={H}
            viewBox={`0 0 ${W} ${H}`}
            preserveAspectRatio="none"
          >
            {[2, 56, 110, 164].map((gy) => (
              <line key={gy} x1="0" y1={gy} x2={W} y2={gy} style={{ stroke: "var(--grid)" }} vectorEffect="non-scaling-stroke" />
            ))}
            <line x1="0" y1={BASE} x2={W} y2={BASE} style={{ stroke: "var(--border-strong)" }} vectorEffect="non-scaling-stroke" />
            <line
              x1={x(idx)}
              y1="0"
              x2={x(idx)}
              y2={BASE}
              style={{ stroke: "var(--divider)" }}
              strokeDasharray="3 3"
              vectorEffect="non-scaling-stroke"
            />
            <path d={`${conv} L${W},${BASE} L0,${BASE} Z`} fill="#8B5CF6" fillOpacity="0.12" />
            <path d={conv} fill="none" stroke="#8B5CF6" strokeWidth="2" vectorEffect="non-scaling-stroke" />
            <path
              d={line("unanswered")}
              fill="none"
              stroke="#F59E0B"
              strokeWidth="1.5"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div
            className={c.tooltip}
            style={{ left: `clamp(70px, ${(idx / (n - 1)) * 100}%, calc(100% - 70px))` }}
          >
            <span style={{ fontWeight: 700 }}>{p.label}</span>
            <span className={c.tooltipRow}>
              <span style={{ color: "var(--accent-softer)" }}>Conversations</span>
              <span className={c.tooltipNum}>{p.conversations}</span>
            </span>
            <span className={c.tooltipRow}>
              <span style={{ color: "var(--warn-soft)" }}>Unanswered</span>
              <span className={c.tooltipNum}>{p.unanswered}</span>
            </span>
          </div>
        </div>
      </div>
      <div className={c.xAxis}>
        {xLabels.map((i) => (
          <span key={i}>{points[i].label}</span>
        ))}
      </div>
    </>
  );
}
