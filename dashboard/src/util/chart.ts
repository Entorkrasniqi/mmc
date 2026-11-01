import type { Bounds, SeriesPoint, Severity } from "../api/types";

export interface Limits {
  warning: Bounds | null;
  critical: Bounds | null;
}

export interface Band {
  y1: number;
  y2: number;
  severity: Severity;
}

/**
 * The shaded areas of a chart that show the alarm limits. A null end of a limit means "no limit on that side".
 * Between the critical and the warning limit is the WARNING band; beyond the critical limit is the CRITICAL band.
 * With no critical limit on a side, the warning band runs to the edge of the chart.
 */
export function limitBands(limits: Limits, yMin: number, yMax: number): Band[] {
  const [warnLow, warnHigh] = limits.warning ?? [null, null];
  const [critLow, critHigh] = limits.critical ?? [null, null];
  const bands: Band[] = [];
  const add = (a: number, b: number, severity: Severity) => {
    const y1 = Math.max(Math.min(a, b), yMin);
    const y2 = Math.min(Math.max(a, b), yMax);
    if (y2 > y1) bands.push({ y1, y2, severity });
  };
  if (critLow !== null) add(yMin, critLow, "CRITICAL");
  if (warnLow !== null) add(critLow ?? yMin, warnLow, "WARNING");
  if (warnHigh !== null) add(warnHigh, critHigh ?? yMax, "WARNING");
  if (critHigh !== null) add(critHigh, yMax, "CRITICAL");
  return bands;
}

/** A y-axis range that holds every value and every limit, with a little air, so the bands are visible. */
export function yDomain(points: SeriesPoint[], limits: Limits): [number, number] {
  const values: number[] = [];
  for (const p of points) {
    for (const v of [p.v, p.min, p.max]) if (typeof v === "number" && Number.isFinite(v)) values.push(v);
  }
  for (const bounds of [limits.warning, limits.critical]) {
    for (const v of bounds ?? []) if (typeof v === "number") values.push(v);
  }
  if (values.length === 0) return [0, 1];
  const low = Math.min(...values);
  const high = Math.max(...values);
  const pad = (high - low || Math.abs(high) || 1) * 0.08;
  return [low - pad, high + pad];
}

/**
 * When the satellite was in the Earth's shadow, from the points of the in_eclipse series: runs of samples with value 1.
 * A run lasts from its first sample to the first sample after it that says otherwise (or to the last sample overall).
 */
export function eclipseIntervals(points: SeriesPoint[]): [number, number][] {
  const intervals: [number, number][] = [];
  let start: number | null = null;
  for (const p of points) {
    const dark = p.v !== null && p.v >= 0.5;
    if (dark && start === null) start = p.t_ms;
    if (!dark && start !== null) {
      intervals.push([start, p.t_ms]);
      start = null;
    }
  }
  const last = points[points.length - 1];
  if (start !== null && last && last.t_ms > start) intervals.push([start, last.t_ms]);
  return intervals;
}

/** The index of the last element <= value in an ascending list, or -1. */
export function lastAtOrBefore(sorted: number[], value: number): number {
  let low = 0;
  let high = sorted.length - 1;
  let found = -1;
  while (low <= high) {
    const mid = (low + high) >> 1;
    if (sorted[mid]! <= value) {
      found = mid;
      low = mid + 1;
    } else {
      high = mid - 1;
    }
  }
  return found;
}
