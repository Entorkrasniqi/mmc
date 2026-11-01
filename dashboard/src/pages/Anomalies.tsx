import { Button, Callout, Card, Drawer, DrawerSize, H4, H5, HTMLTable, NonIdealState, Tag } from "@blueprintjs/core";
import { useState } from "react";

import { get } from "../api/client";
import type { Anomaly, AnomalyStatus, Page, Spacecraft } from "../api/types";
import { ActionDialog } from "../components/ActionDialog";
import { SeverityTag, StatusTag } from "../components/Tags";
import { LIVE_MS, useData } from "../Data";
import { usePoll } from "../hooks/usePoll";
import { formatDateTime, formatTime, words } from "../util/format";

const COLUMNS: { status: AnomalyStatus; title: string }[] = [
  { status: "OPEN", title: "Open" },
  { status: "INVESTIGATING", title: "Investigating" },
  { status: "RESOLVED", title: "Resolved" },
];

function AnomalyDetail({ id, onChange }: { id: string; onChange: () => void }) {
  const { actions, operatorNames } = useData();
  const { data, refresh } = usePoll((signal) => get<Anomaly>(`/api/anomalies/${id}`, undefined, signal), 3000, [id]);
  const [step, setStep] = useState<"INVESTIGATING" | "RESOLVED">();
  const update = actions.find((a) => a.name === "Update Anomaly");
  if (!data) return null;
  const next = data.status === "OPEN" ? "INVESTIGATING" : data.status === "INVESTIGATING" ? "RESOLVED" : undefined;
  const done = () => { refresh(); onChange(); };

  return (
    <div style={{ padding: 16 }} data-testid="anomaly-detail">
      <div className="inline"><H4 style={{ margin: 0 }}>{data.title}</H4><SeverityTag severity={data.severity} /><Tag minimal>{data.status}</Tag></div>
      <p className="muted small">Detected {formatDateTime(data.detected_at)} UTC, opened by {operatorNames[data.opened_by] ?? data.opened_by}.</p>
      {next && (
        <Button intent="primary" icon={next === "RESOLVED" ? "tick-circle" : "search"} text={next === "RESOLVED" ? "Resolve…" : "Start investigating"}
          disabled={!update?.allowed_for_me} onClick={() => setStep(next)} data-testid="anomaly-next"
          title={update?.allowed_for_me ? undefined : "only an operator or supervisor can update an anomaly"} />
      )}
      {data.status === "RESOLVED" && (
        <Callout intent="success" icon="tick-circle" title="Resolved" style={{ marginTop: 8 }}>
          <strong>Root cause:</strong> {data.root_cause}{data.resolution_note ? <><br /><strong>Resolution:</strong> {data.resolution_note}</> : null}
        </Callout>
      )}
      <H5 style={{ marginTop: 16 }}>Alarms</H5>
      {(data.alarms ?? []).length === 0 ? <div className="muted small">none linked</div> : (
        <HTMLTable compact width="100%"><tbody>{(data.alarms ?? []).map((a) => (
          <tr key={a.alarm_id}><td className="mono nowrap">{formatTime(a.raised_at)}</td><td><SeverityTag severity={a.severity} /></td>
            <td>{words(a.parameter_name)}</td><td className="small">{a.limit_violated}</td><td><Tag minimal>{a.state}</Tag></td></tr>
        ))}</tbody></HTMLTable>
      )}
      <H5 style={{ marginTop: 16 }}>Events</H5>
      {(data.events ?? []).length === 0 ? <div className="muted small">none linked</div> : (
        <HTMLTable compact width="100%"><tbody>{(data.events ?? []).map((e) => (
          <tr key={e.event_id}><td className="mono nowrap">{formatTime(e.occurred_at)}</td><td><Tag minimal intent={e.event_type === "FDIR" ? "danger" : "none"}>{words(e.event_type)}</Tag></td>
            <td className="small muted">{Object.entries(e.details).map(([k, v]) => `${k}: ${String(v)}`).join(", ")}</td></tr>
        ))}</tbody></HTMLTable>
      )}
      <H5 style={{ marginTop: 16 }}>Commands that resolved it</H5>
      {(data.commands ?? []).length === 0 ? <div className="muted small">none linked</div> : (
        <HTMLTable compact width="100%"><tbody>{(data.commands ?? []).map((c) => (
          <tr key={c.execution_id}><td>{c.command_name} {Object.entries(c.arguments).map(([k, v]) => c.arguments_text[k] ?? `${k}=${v}`).join(", ")}</td>
            <td><StatusTag status={c.status} /></td><td className="small muted">{operatorNames[c.proposed_by] ?? c.proposed_by}</td></tr>
        ))}</tbody></HTMLTable>
      )}
      {step && (
        <ActionDialog isOpen action={update} onClose={() => setStep(undefined)} onDone={done}
          fixed={{ anomaly_id: id, status: step }} hide={step === "RESOLVED" ? [] : ["root_cause", "resolution_note", "execution_ids"]}
          require={step === "RESOLVED" ? ["root_cause"] : []}
          title={step === "RESOLVED" ? "Resolve the anomaly" : "Start investigating"} submitText={step === "RESOLVED" ? "Resolve" : "Start"}
          summary={step === "RESOLVED" ? "Anomaly resolved" : "Investigation started"}
          intro={step === "RESOLVED" ? <p>Resolving needs a root cause. A resolved anomaly stays on record; it is never deleted.</p> : undefined} />
      )}
    </div>
  );
}

export function Anomalies({ spacecraft }: { spacecraft: Spacecraft }) {
  const { actions, me } = useData();
  const id = spacecraft.spacecraft_id;
  const { data, error, refresh } = usePoll((signal) => get<Page<Anomaly>>(`/api/spacecraft/${id}/anomalies`, { limit: 100 }, signal), LIVE_MS, [id]);
  const [open, setOpen] = useState<string>();
  const [opening, setOpening] = useState(false);
  const openAnomaly = actions.find((a) => a.name === "Open Anomaly");
  const anomalies = data?.items ?? [];

  return (
    <div className="page">
      <div className="spread">
        <H4 style={{ margin: 0 }}>Anomalies of {spacecraft.name}</H4>
        <Button icon="issue-new" text="Open anomaly" disabled={!openAnomaly?.allowed_for_me} onClick={() => setOpening(true)} data-testid="open-anomaly"
          title={openAnomaly?.allowed_for_me ? undefined : `a ${me.role.toLowerCase()} cannot open anomalies`} />
      </div>
      <Callout minimal icon="info-sign">
        An anomaly is unexpected behaviour somebody decided to track. The ground station opens one when the satellite protects itself (an unplanned SAFE mode);
        people open the others. Anomalies are resolved, with a root cause, and never deleted.
      </Callout>
      {error && <Callout intent="danger">{error.message}</Callout>}
      {anomalies.length === 0 ? <Card><NonIdealState icon="tick-circle" title="No anomalies" description="Nothing unexpected has been recorded." /></Card> : (
        <div className="board" data-testid="board">
          {COLUMNS.map((column) => (
            <div key={column.status} className="board-column" data-testid={`column-${column.status}`}>
              <H5>{column.title} <Tag round minimal>{anomalies.filter((a) => a.status === column.status).length}</Tag></H5>
              {anomalies.filter((a) => a.status === column.status).map((a) => (
                <Card key={a.anomaly_id} interactive onClick={() => setOpen(a.anomaly_id)} data-testid="anomaly-card">
                  <div className="spread"><strong>{a.title}</strong><SeverityTag severity={a.severity} /></div>
                  <div className="small muted">{formatDateTime(a.detected_at)} UTC</div>
                </Card>
              ))}
            </div>
          ))}
        </div>
      )}
      <Drawer isOpen={open !== undefined} onClose={() => setOpen(undefined)} size={DrawerSize.STANDARD} title="Anomaly" icon="issue">
        {open && <AnomalyDetail id={open} onChange={refresh} />}
      </Drawer>
      {opening && (
        <ActionDialog isOpen action={openAnomaly} onClose={() => setOpening(false)} onDone={refresh} fixed={{ spacecraft_id: id }}
          hide={["event_ids", "execution_ids"]} initial={{ severity: "MEDIUM" }} title="Open an anomaly" submitText="Open" summary="Anomaly opened"
          intro={<p>Alarm ids can be pasted to link them. Look them up on the Alarms page.</p>} />
      )}
    </div>
  );
}
