import { describe, expect, it } from "vitest";

import type { SeriesPoint } from "../api/types";
import { eclipseIntervals, lastAtOrBefore, limitBands, yDomain } from "./chart";

const pt = (t_ms: number, v: number | null, extra: Partial<SeriesPoint> = {}): SeriesPoint => ({ t_ms, t: "", v, ...extra });

describe("limitBands", () => {
  it("draws the critical band under 20 % and the warning band from 20 to 35 % (spec: warning [35, none], critical [20, none])", () => {
    expect(limitBands({ warning: [35, null], critical: [20, null] }, 0, 100)).toEqual([
      { y1: 0, y2: 20, severity: "CRITICAL" },
      { y1: 20, y2: 35, severity: "WARNING" },
    ]);
  });

  it("draws both sides of a two-sided limit (battery voltage: warning [6.8, 8.5], critical [6.4, 8.6])", () => {
    const bands = limitBands({ warning: [6.8, 8.5], critical: [6.4, 8.6] }, 6, 9);
    expect(bands).toEqual([
      { y1: 6, y2: 6.4, severity: "CRITICAL" },
      { y1: 6.4, y2: 6.8, severity: "WARNING" },
      { y1: 8.5, y2: 8.6, severity: "WARNING" },
      { y1: 8.6, y2: 9, severity: "CRITICAL" },
    ]);
  });

  it("clips bands to the visible range and drops the ones outside it", () => {
    expect(limitBands({ warning: [35, null], critical: [20, null] }, 25, 100)).toEqual([{ y1: 25, y2: 35, severity: "WARNING" }]);
    expect(limitBands({ warning: [35, null], critical: [20, null] }, 40, 100)).toEqual([]);
  });

  it("runs a warning band to the edge when there is no critical limit on that side", () => {
    expect(limitBands({ warning: [null, 10], critical: null }, 0, 15)).toEqual([{ y1: 10, y2: 15, severity: "WARNING" }]);
  });

  it("has no bands for a parameter without limits", () => {
    expect(limitBands({ warning: null, critical: null }, 0, 10)).toEqual([]);
  });
});

describe("yDomain", () => {
  it("holds every value and every limit, with 8 % of air", () => {
    const [low, high] = yDomain([pt(0, 50), pt(1, 60)], { warning: [35, null], critical: [20, null] });
    expect(low).toBeCloseTo(20 - 0.08 * 40);        // lowest is the 20 % limit, highest the 60 % value: span 40
    expect(high).toBeCloseTo(60 + 0.08 * 40);
  });

  it("looks at the minimum and maximum of a bucketed point too, and ignores nulls", () => {
    const [low, high] = yDomain([pt(0, 5, { min: 1, max: 9 }), pt(1, null)], { warning: null, critical: null });
    expect(low).toBeLessThan(1);
    expect(high).toBeGreaterThan(9);
  });

  it("gives a usable range for an empty or constant series", () => {
    expect(yDomain([], { warning: null, critical: null })).toEqual([0, 1]);
    const [low, high] = yDomain([pt(0, 5), pt(1, 5)], { warning: null, critical: null });
    expect(low).toBeLessThan(5);
    expect(high).toBeGreaterThan(5);
  });
});

describe("eclipseIntervals", () => {
  it("lasts from the first dark sample to the first sample that says otherwise", () => {
    const values = [0, 0, 1, 1, 1, 0, 0, 1, 1];            // t = 0 .. 8
    expect(eclipseIntervals(values.map((v, t) => pt(t, v)))).toEqual([[2, 5], [7, 8]]);
  });

  it("ends a run that is still going at the last sample", () => {
    expect(eclipseIntervals([pt(10, 1), pt(20, 1), pt(30, 1)])).toEqual([[10, 30]]);
  });

  it("finds nothing in daylight, in no data, or in a single dark sample", () => {
    expect(eclipseIntervals([pt(0, 0), pt(1, 0)])).toEqual([]);
    expect(eclipseIntervals([])).toEqual([]);
    expect(eclipseIntervals([pt(5, 1)])).toEqual([]);
  });

  it("reads a bucketed mean of 0.5 or more as dark, and null as light", () => {
    expect(eclipseIntervals([pt(0, 0.49), pt(1, 0.5), pt(2, null)])).toEqual([[1, 2]]);
  });
});

describe("lastAtOrBefore", () => {
  const times = [10, 20, 30, 40];
  it.each([[5, -1], [10, 0], [15, 0], [20, 1], [39, 2], [40, 3], [99, 3]])("%i -> %i", (value, expected) => {
    expect(lastAtOrBefore(times, value)).toBe(expected);
  });
  it("copes with an empty list", () => expect(lastAtOrBefore([], 5)).toBe(-1));
});
