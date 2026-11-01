import { Card, ProgressBar } from "@blueprintjs/core";

import type { ParameterState, Spacecraft } from "../api/types";
import { formatDuration, formatValue } from "../util/format";

const DECIMALS: Record<string, number> = { battery_voltage: 2, battery_soc_pct: 1, battery_temp_c: 1, solar_current_a: 2, load_current_a: 2 };

function Tile({ p }: { p: ParameterState }) {
  const severity = p.severity === "CRITICAL" ? "critical" : p.severity === "WARNING" ? "warning" : "";
  const shown = p.label ?? (p.name === "uptime_s" ? formatDuration(p.value) : formatValue(p.value, null, DECIMALS[p.name] ?? 2));
  const unit = p.label || p.name === "uptime_s" ? null : p.unit;
  return (
    <Card className={`tile ${severity}`} data-testid={`tile-${p.name}`}>
      <div className="label">{p.name.replace(/_/g, " ")}</div>
      <div className="value">
        {shown}
        {unit && <span className="unit">{unit}</span>}
      </div>
      {p.name === "battery_soc_pct" && (
        <ProgressBar value={Math.max(0, Math.min(1, p.value / 100))} stripes={false} animate={false}
          intent={p.severity === "CRITICAL" ? "danger" : p.severity === "WARNING" ? "warning" : "success"} />
      )}
    </Card>
  );
}

/** The newest value of every telemetry parameter, in wire order, with the ones outside their limits marked. */
export function StateTiles({ spacecraft }: { spacecraft: Spacecraft }) {
  if (spacecraft.parameters.length === 0) return <div className="muted">No telemetry received yet. Is the ground station running?</div>;
  return (
    <div className="tiles">
      {spacecraft.parameters.map((p) => <Tile key={p.name} p={p} />)}
    </div>
  );
}
