import { Callout, Card, H4, H5, HTMLTable, SegmentedControl, Tag } from "@blueprintjs/core";
import { useMemo, useState } from "react";

import { get } from "../api/client";
import type { Page, Series, Spacecraft, SpacecraftEvent } from "../api/types";
import { EstimatePanel } from "../components/EstimatePanel";
import { StateTiles } from "../components/StateTiles";
import { TimeSeriesChart, type Trace } from "../components/TimeSeriesChart";
import { useData } from "../Data";
import { usePoll } from "../hooks/usePoll";
import { eclipseIntervals } from "../util/chart";
import { formatDuration, formatTime, words } from "../util/format";

const WINDOWS = [
  { value: "300", label: "5 min" },
  { value: "900", label: "15 min" },
  { value: "3600", label: "1 h" },
  { value: "10800", label: "3 h" },
];

const COLORS = { blue: "#4c90f0", green: "#32a467", orange: "#ec9a3c", violet: "#9d7bdc" };

function seriesTrace(series: Series | undefined, key: string, label: string, color: string): Trace {
  return { key, label, color, points: series?.points ?? [] };
}

function useSeries(spacecraftId: string, parameter: string, windowS: string) {
  return usePoll((signal) => get<Series>(`/api/spacecraft/${spacecraftId}/series/${parameter}`, { window_s: windowS, max_points: 600 }, signal),
    5000, [spacecraftId, parameter, windowS]).data;
}

function Header({ sc }: { sc: Spacecraft }) {
  return (
    <div className="spread">
      <div className="inline">
        <H4 style={{ margin: 0 }}>{sc.name}</H4>
        {sc.mode && <Tag large minimal data-testid="mode-tag">mode {sc.mode}</Tag>}
      </div>
      <div className="muted small" data-testid="contact-age">
        last telemetry {sc.telemetry_age_s === null ? "never" : `${formatDuration(sc.telemetry_age_s)} ago`}
      </div>
    </div>
  );
}

function RecentEvents({ spacecraftId }: { spacecraftId: string }) {
  const events = usePoll((signal) => get<Page<SpacecraftEvent>>(`/api/spacecraft/${spacecraftId}/events`, { limit: 8 }, signal), 3000, [spacecraftId]);
  const rows = events.data?.items ?? [];
  return (
    <Card>
      <H5>Recent events</H5>
      {rows.length === 0 ? <div className="muted">Nothing has happened yet.</div> : (
        <HTMLTable compact striped width="100%" data-testid="events-table">
          <tbody>
            {rows.map((e) => (
              <tr key={e.event_id}>
                <td className="nowrap mono">{formatTime(e.occurred_at)}</td>
                <td><Tag minimal intent={e.event_type === "FDIR" ? "danger" : e.event_type === "LINK_LOST" || e.event_type === "PACKET_LOSS" ? "warning" : "none"}>{words(e.event_type)}</Tag></td>
                <td className="small muted">{Object.entries(e.details).map(([k, v]) => `${k}: ${String(v)}`).join(", ")}</td>
              </tr>
            ))}
          </tbody>
        </HTMLTable>
      )}
    </Card>
  );
}

export function Overview({ spacecraft }: { spacecraft: Spacecraft }) {
  const { definitions } = useData();
  const [windowS, setWindowS] = useState("900");
  const id = spacecraft.spacecraft_id;
  const soc = useSeries(id, "battery_soc_pct", windowS);
  const voltage = useSeries(id, "battery_voltage", windowS);
  const temperature = useSeries(id, "battery_temp_c", windowS);
  const solar = useSeries(id, "solar_current_a", windowS);
  const load = useSeries(id, "load_current_a", windowS);
  const eclipseSeries = useSeries(id, "in_eclipse", windowS);
  const eclipse = useMemo(() => eclipseIntervals(eclipseSeries?.points ?? []), [eclipseSeries]);
  const fromMs = soc?.from ? Date.parse(soc.from) : undefined;
  const toMs = soc?.to ? Date.parse(soc.to) : undefined;
  const common = { eclipse, fromMs, toMs };
  const loading = (...series: (Series | undefined)[]) => series.some((x) => x === undefined);

  return (
    <div className="page">
      <Header sc={spacecraft} />
      {spacecraft.telemetry_stale && (
        <Callout intent="warning" icon="offline" title="Telemetry is stale" data-testid="stale-callout">
          Nothing has arrived for {spacecraft.telemetry_age_s === null ? "as long as anyone knows" : formatDuration(spacecraft.telemetry_age_s)}. The values below are the last ones received.
        </Callout>
      )}
      <StateTiles spacecraft={spacecraft} />
      <EstimatePanel spacecraftId={id} definitions={definitions} />
      <div className="spread">
        <H5 style={{ margin: 0 }}>Telemetry</H5>
        <div className="inline">
          <span className="chart-legend"><span><span className="swatch" style={{ background: "#000", opacity: 0.4 }} />eclipse</span>
            <span><span className="swatch" style={{ background: "#d9822b" }} />warning band</span>
            <span><span className="swatch" style={{ background: "#cd4246" }} />critical band</span></span>
          <SegmentedControl small options={WINDOWS} value={windowS} onValueChange={setWindowS} data-testid="window" />
        </div>
      </div>
      <div className="charts">
        <Card data-testid="chart-soc">
          <div className="chart-title"><strong>Battery charge</strong><span className="muted small">%</span></div>
          <TimeSeriesChart {...common} loading={loading(soc)} unit="%" limits={soc?.parameter} traces={[seriesTrace(soc, "soc", "charge", COLORS.green)]} />
        </Card>
        <Card data-testid="chart-voltage">
          <div className="chart-title"><strong>Battery voltage</strong><span className="muted small">V</span></div>
          <TimeSeriesChart {...common} loading={loading(voltage)} unit="V" limits={voltage?.parameter} traces={[seriesTrace(voltage, "v", "voltage", COLORS.blue)]} />
        </Card>
        <Card data-testid="chart-temperature">
          <div className="chart-title"><strong>Battery temperature</strong><span className="muted small">°C</span></div>
          <TimeSeriesChart {...common} loading={loading(temperature)} unit="°C" limits={temperature?.parameter} traces={[seriesTrace(temperature, "t", "temperature", COLORS.orange)]} />
        </Card>
        <Card data-testid="chart-currents">
          <div className="chart-title"><strong>Solar and load current</strong><span className="muted small">A</span></div>
          <TimeSeriesChart {...common} loading={loading(solar, load)} unit="A" traces={[seriesTrace(solar, "solar", "solar", COLORS.orange), seriesTrace(load, "load", "load", COLORS.violet)]} />
        </Card>
      </div>
      <RecentEvents spacecraftId={id} />
    </div>
  );
}
