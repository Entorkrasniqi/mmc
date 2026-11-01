import { Spinner } from "@blueprintjs/core";
import { CartesianGrid, ComposedChart, Line, ReferenceArea, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import type { SeriesPoint } from "../api/types";
import { limitBands, yDomain, type Limits } from "../util/chart";
import { formatTime } from "../util/format";

export interface Trace {
  key: string;
  label: string;
  color: string;
  points: SeriesPoint[];
}

interface Props {
  traces: Trace[];
  /** Alarm limits to draw as bands (only for charts of one parameter). */
  limits?: Limits;
  unit?: string | null;
  /** Spans of time in the Earth's shadow, in ms. */
  eclipse?: [number, number][];
  fromMs?: number;
  toMs?: number;
  height?: number;
  /** the series has not been fetched yet (as opposed to fetched and empty) */
  loading?: boolean;
}

const WARNING_FILL = "#d9822b";
const CRITICAL_FILL = "#cd4246";

/** One instant: the time, and every trace's value then. Values live in their own map so no trace name can clash with the time. */
export interface Row {
  x: number;
  y: Record<string, number | null>;
}

export function rowsOf(traces: Trace[]): Row[] {
  const rows = new Map<number, Row>();
  for (const trace of traces) {
    for (const p of trace.points) {
      const row = rows.get(p.t_ms) ?? { x: p.t_ms, y: {} };
      row.y[trace.key] = p.v;
      // a thinned series also says how low and how high each bucket went, so a spike is not averaged away
      if (p.min !== undefined && p.min !== null) row.y[`${trace.key}:min`] = p.min;
      if (p.max !== undefined && p.max !== null) row.y[`${trace.key}:max`] = p.max;
      rows.set(p.t_ms, row);
    }
  }
  return [...rows.values()].sort((a, b) => a.x - b.x);
}

const value = (key: string) => (row: Row) => row.y[key] ?? null;

/** One or more parameters over time, with the alarm limits as coloured bands and the eclipse as a darker background. */
export function TimeSeriesChart({ traces, limits, unit, eclipse = [], fromMs, toMs, height = 220, loading = false }: Props) {
  const rows = rowsOf(traces);
  const all = traces.flatMap((t) => t.points);
  const noLimits: Limits = { warning: null, critical: null };
  const [yMin, yMax] = yDomain(all, limits ?? noLimits);
  const bands = limits ? limitBands(limits, yMin, yMax) : [];
  const first = rows[0]?.x;
  const last = rows[rows.length - 1]?.x;
  const domain: [number, number] = [fromMs ?? first ?? 0, toMs ?? last ?? 1];

  if (rows.length === 0) {
    return (
      <div className="muted small" style={{ height, display: "grid", placeItems: "center" }}>
        {loading ? <Spinner size={24} /> : "No samples in this window yet."}
      </div>
    );
  }

  return (
    <ResponsiveContainer width="100%" height={height}>
      <ComposedChart data={rows} margin={{ top: 6, right: 12, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="currentColor" opacity={0.15} />
        <XAxis dataKey="x" type="number" scale="time" domain={domain} allowDataOverflow tick={{ fontSize: 11, fill: "currentColor" }}
          tickFormatter={(t: number) => formatTime(new Date(t).toISOString())} minTickGap={40} stroke="currentColor" />
        <YAxis domain={[yMin, yMax]} allowDataOverflow width={52} tick={{ fontSize: 11, fill: "currentColor" }} stroke="currentColor"
          tickFormatter={(v: number) => (Math.abs(v) >= 100 ? v.toFixed(0) : v.toFixed(2).replace(/\.?0+$/, ""))} />
        {eclipse.map(([a, b]) => (
          <ReferenceArea key={`e${a}`} x1={a} x2={b} fill="#000" fillOpacity={0.22} ifOverflow="hidden" />
        ))}
        {bands.map((b, i) => (
          <ReferenceArea key={`b${i}`} y1={b.y1} y2={b.y2} fill={b.severity === "CRITICAL" ? CRITICAL_FILL : WARNING_FILL}
            fillOpacity={b.severity === "CRITICAL" ? 0.2 : 0.14} ifOverflow="hidden" />
        ))}
        {traces.flatMap((t) => [`${t.key}:min`, `${t.key}:max`]).map((key, i) => (
          <Line key={key} dataKey={value(key)} legendType="none" stroke={traces[i >> 1]!.color} strokeOpacity={0.35} strokeWidth={1} dot={false}
            isAnimationActive={false} connectNulls tooltipType="none" />
        ))}
        {traces.map((t) => (
          <Line key={t.key} className="trace-main" dataKey={value(t.key)} name={t.label} stroke={t.color} strokeWidth={1.8} dot={false} isAnimationActive={false} connectNulls={false} />
        ))}
        <Tooltip
          isAnimationActive={false}
          contentStyle={{ background: "rgba(28,33,39,0.95)", border: "1px solid #5f6b7c", borderRadius: 3, fontSize: 12 }}
          labelStyle={{ color: "#abb3bf" }}
          labelFormatter={(t) => `${formatTime(new Date(Number(t)).toISOString())} UTC`}
          formatter={(value, name) => [typeof value === "number" ? `${value.toFixed(3)}${unit ? ` ${unit}` : ""}` : String(value ?? "—"), String(name)]}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
