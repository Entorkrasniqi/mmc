import { Callout, Card, H4, SegmentedControl, Tag } from "@blueprintjs/core";
import { geoEquirectangular, geoGraticule10, geoPath } from "d3-geo";
import type { Topology } from "topojson-specification";
import { feature } from "topojson-client";
import { useMemo, useState } from "react";
import land110 from "world-atlas/land-110m.json";

import { get } from "../api/client";
import type { GroundStation, Series, Spacecraft } from "../api/types";
import { usePoll } from "../hooks/usePoll";
import { buildTrack, trackSegments } from "../util/track";
import { formatValue } from "../util/format";

const WIDTH = 1000;
const HEIGHT = 500;
const WINDOWS = [
  { value: "1800", label: "30 min" },
  { value: "5760", label: "1 orbit" },
  { value: "10800", label: "3 h" },
];

const topology = land110 as unknown as Topology;
const land = feature(topology, topology.objects.land as never);
const projection = geoEquirectangular().fitSize([WIDTH, HEIGHT], { type: "Sphere" });
const pathOf = geoPath(projection);
const graticule = pathOf(geoGraticule10()) ?? "";
const landPath = pathOf(land) ?? "";

const SUNLIT = "#ec9a3c";
const DARK = "#8f6bd8";

export function GroundTrack({ spacecraft }: { spacecraft: Spacecraft }) {
  const id = spacecraft.spacecraft_id;
  const [windowS, setWindowS] = useState("5760");
  const q = { window_s: windowS, max_points: 2000 };
  const lat = usePoll((s) => get<Series>(`/api/spacecraft/${id}/series/latitude_deg`, q, s), 5000, [id, windowS]).data;
  const lon = usePoll((s) => get<Series>(`/api/spacecraft/${id}/series/longitude_deg`, q, s), 5000, [id, windowS]).data;
  const eclipse = usePoll((s) => get<Series>(`/api/spacecraft/${id}/series/in_eclipse`, q, s), 5000, [id, windowS]).data;
  const stations = usePoll((s) => get<{ items: GroundStation[] }>("/api/ground-stations", undefined, s), null).data?.items ?? [];

  const track = useMemo(() => buildTrack(lat?.points ?? [], lon?.points ?? [], eclipse?.points ?? []), [lat, lon, eclipse]);
  const segments = useMemo(() => trackSegments(track), [track]);
  const here = track[track.length - 1];
  const at = (lonDeg: number, latDeg: number) => projection([lonDeg, latDeg]) ?? [0, 0];
  const d = (points: { lon: number; lat: number }[]) => points.map((p, i) => `${i === 0 ? "M" : "L"}${at(p.lon, p.lat).map((n) => n.toFixed(1)).join(",")}`).join("");
  const marker = here ? at(here.lon, here.lat) : undefined;

  return (
    <div className="page">
      <div className="spread">
        <H4 style={{ margin: 0 }}>Ground track of {spacecraft.name}</H4>
        <SegmentedControl small options={WINDOWS} value={windowS} onValueChange={setWindowS} />
      </div>
      {track.length === 0 && <Callout intent="warning" icon="map">No position received in this window yet. The Position packet comes every 5 s.</Callout>}
      <Card data-testid="ground-track">
        <svg className="map" viewBox={`0 0 ${WIDTH} ${HEIGHT}`} role="img" aria-label="Ground track on a world map">
          <rect className="ocean" width={WIDTH} height={HEIGHT} />
          <path className="graticule" d={graticule} />
          <path className="land" d={landPath} />
          {segments.map((s, i) => (
            <path key={i} d={d(s)} fill="none" strokeWidth={2} strokeLinecap="round" stroke={s[0]!.eclipse ? DARK : SUNLIT} data-testid="track-segment" />
          ))}
          {stations.map((st) => {
            const [x, y] = at(st.longitude_deg, st.latitude_deg);
            return (
              <g key={st.station_id} transform={`translate(${x},${y})`} data-testid={`station-${st.station_id}`}>
                <rect x={-4} y={-4} width={8} height={8} fill="#2d72d2" stroke="#fff" strokeWidth={1} transform="rotate(45)" />
                <text x={8} y={4} fontSize={13} fill="currentColor" style={{ paintOrder: "stroke", stroke: "rgba(0,0,0,0.5)", strokeWidth: 3 }}>{st.station_id}</text>
              </g>
            );
          })}
          {marker && (
            <g transform={`translate(${marker[0]},${marker[1]})`} data-testid="spacecraft-marker">
              <circle r={9} fill="none" stroke="#fff" strokeWidth={1.5} opacity={0.8} />
              <circle r={4.5} fill={here!.eclipse ? DARK : SUNLIT} stroke="#fff" strokeWidth={1.5} />
            </g>
          )}
        </svg>
        <div className="spread small" style={{ marginTop: 8 }}>
          <span className="chart-legend">
            <span><span className="swatch" style={{ background: SUNLIT }} />in sunlight</span>
            <span><span className="swatch" style={{ background: DARK }} />in eclipse</span>
            <span><span className="swatch" style={{ background: "#2d72d2", transform: "rotate(45deg)" }} />ground station</span>
          </span>
          {here && (
            <span className="inline" data-testid="position">
              <Tag minimal>lat {formatValue(here.lat, "°", 2)}</Tag>
              <Tag minimal>lon {formatValue(here.lon, "°", 2)}</Tag>
              <Tag minimal>{formatValue(spacecraft.values.altitude_km, "km", 0)}</Tag>
            </span>
          )}
        </div>
      </Card>
      <div className="small muted">
        Position is a spherical-Earth, circular-orbit approximation: good for a picture, not for navigation. Land: Natural Earth (public domain) via the world-atlas package.
      </div>
    </div>
  );
}
