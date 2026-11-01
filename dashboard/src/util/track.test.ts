import { describe, expect, it } from "vitest";

import type { SeriesPoint } from "../api/types";
import { buildTrack, trackSegments, type TrackPoint } from "./track";

const pt = (t_ms: number, v: number | null): SeriesPoint => ({ t_ms, t: "", v });
const tp = (t_ms: number, lon: number, eclipse = false, lat = 0): TrackPoint => ({ t_ms, lat, lon, eclipse });

describe("buildTrack", () => {
  it("pairs latitude and longitude by time and notes the eclipse state in force at that moment", () => {
    const track = buildTrack(
      [pt(1000, 10), pt(6000, 20), pt(11000, 30)],
      [pt(1000, 100), pt(6000, 110), pt(11000, 120)],
      [pt(0, 0), pt(5000, 1), pt(10000, 0)],
    );
    expect(track.map((p) => [p.lat, p.lon, p.eclipse])).toEqual([[10, 100, false], [20, 110, true], [30, 120, false]]);
  });

  it("drops a point that is missing either coordinate (NaN comes back as null)", () => {
    const track = buildTrack([pt(1, 10), pt(2, null), pt(3, 30)], [pt(1, 1), pt(2, 2), pt(4, 4)], []);
    expect(track.map((p) => p.t_ms)).toEqual([1]);
  });

  it("treats the time before the first eclipse sample as not in eclipse", () => {
    expect(buildTrack([pt(5, 1)], [pt(5, 1)], [pt(10, 1)])[0]!.eclipse).toBe(false);
  });
});

describe("trackSegments", () => {
  it("cuts the line where the satellite crosses the antimeridian instead of drawing it across the whole map", () => {
    const segments = trackSegments([tp(0, 170), tp(1000, 178), tp(2000, -178), tp(3000, -170)]);
    expect(segments.map((s) => s.map((p) => p.lon))).toEqual([[170, 178], [-178, -170]]);
  });

  it("starts a new piece when the eclipse state changes, and the pieces share their joining point", () => {
    const segments = trackSegments([tp(0, 0), tp(1000, 1), tp(2000, 2, true), tp(3000, 3, true), tp(4000, 4, false), tp(5000, 5, false)]);
    expect(segments.map((s) => s.map((p) => p.t_ms))).toEqual([[0, 1000], [1000, 2000, 3000], [3000, 4000, 5000]]);
    expect(segments.map((s) => s[s.length - 1]!.eclipse)).toEqual([false, true, false]);
  });

  it("cuts across a hole in the data longer than the limit, but not a shorter one", () => {
    expect(trackSegments([tp(0, 0), tp(100_000, 1)], 120_000)).toHaveLength(1);
    expect(trackSegments([tp(0, 0), tp(130_000, 1), tp(131_000, 2)], 120_000).map((s) => s.length)).toEqual([2]);
  });

  it("makes no pieces out of a single point or nothing", () => {
    expect(trackSegments([])).toEqual([]);
    expect(trackSegments([tp(0, 0)])).toEqual([]);
  });

  it("does not treat a move of exactly 180 degrees as a crossing", () => {
    expect(trackSegments([tp(0, -90), tp(1000, 90)])).toHaveLength(1);
  });
});
