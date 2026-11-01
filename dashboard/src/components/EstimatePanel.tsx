import { Callout, Card, Collapse, H5, HTMLSelect, Spinner } from "@blueprintjs/core";
import { useMemo, useState } from "react";

import { post } from "../api/client";
import type { Definitions, TimeToSafeAnswer } from "../api/types";
import { usePoll } from "../hooks/usePoll";
import { formatDuration, formatValue } from "../util/format";

interface Scenario {
  id: string;
  label: string;
  command?: string;
  arguments?: Record<string, string>;
}

/** "What if I sent this?" choices, from the command definitions: every command with no argument or one enum argument. */
export function scenariosOf(definitions: Definitions | undefined): Scenario[] {
  const list: Scenario[] = [{ id: "none", label: "nothing: the state as it is now" }];
  for (const c of definitions?.commands ?? []) {
    if (c.name === "Noop") continue;
    const [only] = c.arguments;
    if (c.arguments.length === 0) list.push({ id: c.name, label: c.name, command: c.name, arguments: {} });
    else if (c.arguments.length === 1 && only?.enum_labels) {
      for (const e of only.enum_labels) list.push({ id: `${c.name}:${e.label}`, label: `${c.name} ${e.label}`, command: c.name, arguments: { [only.name]: e.label } });
    }
  }
  return list;
}

/** What the estimate says, in words: whether the satellite would take the command, and when the battery would reach FDIR. */
export function EstimateView({ data, label }: { data: TimeToSafeAnswer; label: string }) {
  const [showWhy, setShowWhy] = useState(false);
  const estimate = data.time_to_safe;
  const hours = estimate.horizon_s / 3600;
  let verdict: { intent: "none" | "success" | "warning" | "danger" | "primary"; text: string };
  if (!estimate.known) verdict = { intent: "none", text: "No telemetry yet, so nothing can be estimated." };
  else if (estimate.reaches_safe && estimate.seconds === 0) verdict = { intent: "danger", text: "The spacecraft is already in SAFE mode, or below the 15 % limit." };
  else if (estimate.reaches_safe && estimate.seconds !== null) {
    verdict = { intent: estimate.seconds < 1800 ? "danger" : estimate.seconds < 7200 ? "warning" : "primary",
      text: `The battery reaches the FDIR limit (15 %) in about ${formatDuration(estimate.seconds)}, and the satellite protects itself by going to SAFE mode.` };
  } else verdict = { intent: "success", text: `The battery does not reach the FDIR limit within ${hours} h (lowest charge ${formatValue(estimate.min_soc_pct, "%", 1)}).` };
  const pre = data.preflight;
  return (
    <>
      {pre && (
        <Callout intent={pre.accepted === false ? "danger" : pre.known ? "success" : "none"} style={{ marginBottom: 8 }}
          icon={pre.accepted === false ? "ban-circle" : "tick"} data-testid="estimate-preflight">
          {!pre.known ? "The satellite's state is unknown, so the command cannot be checked."
            : pre.accepted ? `The satellite would accept ${label}.`
            : `The satellite would REJECT ${label}: ${pre.reason}`}
        </Callout>
      )}
      <Callout intent={verdict.intent} icon="time" data-testid="estimate-verdict">{verdict.text}</Callout>
      {estimate.assumptions.length > 0 && (
        <>
          <a className="small" role="button" onClick={() => setShowWhy((v) => !v)} style={{ cursor: "pointer" }}>
            {showWhy ? "hide" : "show"} what this assumes
          </a>
          <Collapse isOpen={showWhy}>
            <ul className="small muted">{estimate.assumptions.map((a) => <li key={a}>{a}</li>)}</ul>
          </Collapse>
        </>
      )}
    </>
  );
}

export function EstimatePanel({ spacecraftId, definitions }: { spacecraftId: string; definitions: Definitions | undefined }) {
  const scenarios = useMemo(() => scenariosOf(definitions), [definitions]);
  const [choice, setChoice] = useState("none");
  const scenario = scenarios.find((s) => s.id === choice) ?? scenarios[0]!;

  const { data, error, loading } = usePoll(
    (signal) => post<TimeToSafeAnswer>("/api/functions/estimate-time-to-safe",
      { spacecraft_id: spacecraftId, command: scenario.command ?? null, arguments: scenario.arguments ?? {} }, { signal }),
    5000, [spacecraftId, scenario.id]);

  return (
    <Card data-testid="estimate-panel">
      <div className="spread">
        <H5 style={{ margin: 0 }}>Time to safe mode</H5>
        <label className="inline small">
          if I send:&nbsp;
          <HTMLSelect value={choice} onChange={(e) => setChoice(e.target.value)} data-testid="estimate-scenario">
            {scenarios.map((s) => <option key={s.id} value={s.id}>{s.label}</option>)}
          </HTMLSelect>
        </label>
      </div>
      <div style={{ marginTop: 10 }}>
        {loading && !data && <Spinner size={20} />}
        {error && <Callout intent="warning" icon="warning-sign">{error.message}</Callout>}
        {data && <EstimateView data={data} label={scenario.label} />}
      </div>
    </Card>
  );
}
