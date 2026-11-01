import { describe, expect, it } from "vitest";

import type { SeriesPoint } from "../api/types";
import { rowsOf, type Trace } from "./TimeSeriesChart";

const pts = (...pairs: [number, number | null][]): SeriesPoint[] => pairs.map(([t_ms, v]) => ({ t_ms, t: "", v }));
const trace = (key: string, points: SeriesPoint[]): Trace => ({ key, label: key, color: "#000", points });

describe("rowsOf", () => {
  it("makes one row per instant, with every trace's value on it", () => {
    const rows = rowsOf([trace("a", pts([1000, 1], [2000, 2])), trace("b", pts([2000, 20], [3000, 30]))]);
    expect(rows.map((r) => [r.x, r.y.a ?? null, r.y.b ?? null])).toEqual([[1000, 1, null], [2000, 2, 20], [3000, null, 30]]);
  });

  it("keeps a trace called 't' from overwriting the time (regression: the temperature chart drew every point at x = 12)", () => {
    const rows = rowsOf([trace("t", pts([1_793_524_608_190, 12.03], [1_793_524_609_190, 12.05]))]);
    expect(rows.map((r) => r.x)).toEqual([1_793_524_608_190, 1_793_524_609_190]);
    expect(rows.map((r) => r.y.t)).toEqual([12.03, 12.05]);
  });

  it.each(["x", "time", "v", "min", "max"])("does the same for a trace called %s", (key) => {
    const rows = rowsOf([trace(key, pts([5000, 1.5]))]);
    expect(rows[0]!.x).toBe(5000);
    expect(rows[0]!.y[key]).toBe(1.5);
  });

  it("sorts by time and carries the bucket minimum and maximum", () => {
    const points: SeriesPoint[] = [{ t_ms: 2000, t: "", v: 5, min: 1, max: 9 }, { t_ms: 1000, t: "", v: 4, min: 3, max: 6 }];
    const rows = rowsOf([trace("a", points)]);
    expect(rows.map((r) => r.x)).toEqual([1000, 2000]);
    expect(rows.map((r) => [r.y["a:min"], r.y["a:max"]])).toEqual([[3, 6], [1, 9]]);
  });

  it("keeps a missing value (NaN comes back as null) as a gap", () => {
    expect(rowsOf([trace("a", pts([1, null]))])[0]!.y.a).toBeNull();
  });
});
