import type { SeriesPoint } from "../api/types";
import { lastAtOrBefore } from "./chart";

export interface TrackPoint {
  t_ms: number;
  lat: number;
  lon: number;
  eclipse: boolean;
}

/**
 * Pair the latitude and longitude series by time (they come from the same Position packets) and note for each point whether the
 * satellite was in eclipse then, from the in_eclipse series. A point missing either coordinate (NaN is sent as null) is dropped.
 */
export function buildTrack(lat: SeriesPoint[], lon: SeriesPoint[], eclipse: SeriesPoint[]): TrackPoint[] {
  const longitudes = new Map<number, number>();
  for (const p of lon) if (p.v !== null) longitudes.set(p.t_ms, p.v);
  const eclipseTimes = eclipse.map((p) => p.t_ms);
  const track: TrackPoint[] = [];
  for (const p of lat) {
    const longitude = longitudes.get(p.t_ms);
    if (p.v === null || longitude === undefined) continue;
    const i = lastAtOrBefore(eclipseTimes, p.t_ms);
    track.push({ t_ms: p.t_ms, lat: p.v, lon: longitude, eclipse: i >= 0 && (eclipse[i]!.v ?? 0) >= 0.5 });
  }
  return track;
}

/**
 * Cut a track wherever a line must not be drawn: when the satellite crosses the antimeridian (longitude jumps by more than
 * 180 degrees; a line across the whole map would be wrong), when the eclipse state changes (so each piece has one colour; the
 * pieces share their end point so the line stays joined), or when the data has a hole longer than `maxGapMs`.
 */
export function trackSegments(track: TrackPoint[], maxGapMs = 120_000): TrackPoint[][] {
  const segments: TrackPoint[][] = [];
  let current: TrackPoint[] = [];
  for (const point of track) {
    const previous = current[current.length - 1];
    if (previous) {
      const jump = Math.abs(point.lon - previous.lon) > 180;
      const hole = point.t_ms - previous.t_ms > maxGapMs;
      if (jump || hole) {
        segments.push(current);
        current = [];
      } else if (point.eclipse !== previous.eclipse) {
        segments.push(current);
        current = [previous];
      }
    }
    current.push(point);
  }
  if (current.length > 0) segments.push(current);
  return segments.filter((s) => s.length > 1);
}
