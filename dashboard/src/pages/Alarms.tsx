import { Button, Callout, Card, Collapse, H4, HTMLTable, NonIdealState, SegmentedControl, Tag } from "@blueprintjs/core";
import { Fragment, useState } from "react";

import { get } from "../api/client";
import type { Alarm, Page, Spacecraft } from "../api/types";
import { ActionDialog } from "../components/ActionDialog";
import { SeverityTag, StatusTag } from "../components/Tags";
import { useData } from "../Data";
import { usePoll } from "../hooks/usePoll";
import { formatDateTime, formatTime, formatValue, words } from "../util/format";

function Responses({ alarmId }: { alarmId: string }) {
  const { data } = usePoll((signal) => get<Alarm>(`/api/alarms/${alarmId}`, undefined, signal), 4000, [alarmId]);
  const { operatorNames } = useData();
  const commands = data?.responding_commands ?? [];
  return commands.length === 0 ? (
    <div className="muted small">No command has been proposed in response to this alarm.</div>
  ) : (
    <div>
      <div className="small muted">Commands proposed in response:</div>
      {commands.map((c) => (
        <div key={c.execution_id} className="inline" style={{ marginTop: 4 }}>
          <strong>{c.command_name}</strong> <StatusTag status={c.status} /> <span className="small muted">proposed by {operatorNames[c.proposed_by] ?? c.proposed_by}</span>
        </div>
      ))}
    </div>
  );
}

/** Open the proposal dialog on the Commands page with this alarm already linked. */
export function respondTo(alarmId: string): void {
  window.location.hash = `#/commands?respond=${alarmId}`;
}

export function Alarms({ spacecraft }: { spacecraft: Spacecraft }) {
  const { actions, me, operatorNames } = useData();
  const [filter, setFilter] = useState("open");
  const [expanded, setExpanded] = useState<string>();
  const [acknowledging, setAcknowledging] = useState<Alarm>();
  const id = spacecraft.spacecraft_id;
  const states = filter === "open" ? "ACTIVE,ACKNOWLEDGED" : undefined;
  const { data, error, refresh } = usePoll((signal) => get<Page<Alarm>>(`/api/spacecraft/${id}/alarms`, { state: states, limit: 100 }, signal), 2000, [id, filter]);
  const acknowledge = actions.find((a) => a.name === "Acknowledge Alarm");
  const alarms = data?.items ?? [];

  return (
    <div className="page">
      <div className="spread">
        <H4 style={{ margin: 0 }}>Alarms of {spacecraft.name}</H4>
        <SegmentedControl small value={filter} onValueChange={setFilter} options={[{ value: "open", label: "Open" }, { value: "all", label: "All" }]} />
      </div>
      <Callout minimal icon="info-sign">
        Alarms are raised by the ground station when a value leaves its limits, and cleared when it returns. A person acknowledges an alarm to say they have seen it.
      </Callout>
      {error && <Callout intent="danger">{error.message}</Callout>}
      <Card style={{ padding: 0 }}>
        {alarms.length === 0 ? (
          <NonIdealState icon="tick-circle" title={filter === "open" ? "No open alarms" : "No alarms yet"} description="Every value is inside its limits." />
        ) : (
          <HTMLTable width="100%" interactive={false} data-testid="alarms-table">
            <thead><tr><th>Raised</th><th>Severity</th><th>Parameter</th><th>Value</th><th>Limit</th><th>State</th><th /></tr></thead>
            <tbody>
              {alarms.map((a) => (
                <Fragment key={a.alarm_id}>
                  <tr data-testid={`alarm-${a.parameter_name}`}>
                    <td className="nowrap mono">{formatTime(a.raised_at)}</td>
                    <td><SeverityTag severity={a.severity} /></td>
                    <td><strong>{words(a.parameter_name)}</strong></td>
                    <td className="mono">{formatValue(a.trigger_value)}</td>
                    <td className="small">{a.limit_violated}</td>
                    <td>
                      <Tag minimal intent={a.state === "ACTIVE" ? "danger" : a.state === "ACKNOWLEDGED" ? "warning" : "none"}>{a.state}</Tag>
                      {a.acknowledged_by && <div className="small muted">by {operatorNames[a.acknowledged_by] ?? a.acknowledged_by}{a.acknowledge_note ? `: ${a.acknowledge_note}` : ""}</div>}
                      {a.cleared_at && <div className="small muted">cleared {formatDateTime(a.cleared_at)}</div>}
                    </td>
                    <td className="nowrap" style={{ textAlign: "right" }}>
                      {a.state === "ACTIVE" && (
                        <Button small icon="tick" text="Acknowledge" disabled={!acknowledge?.allowed_for_me} data-testid="acknowledge"
                          title={acknowledge?.allowed_for_me ? undefined : `a ${me.role.toLowerCase()} cannot acknowledge alarms`}
                          onClick={() => setAcknowledging(a)} />
                      )}{" "}
                      {a.state !== "CLEARED" && me.role !== "VIEWER" && <Button small icon="send-message" text="Respond" onClick={() => respondTo(a.alarm_id)} />}{" "}
                      <Button small minimal icon={expanded === a.alarm_id ? "chevron-up" : "chevron-down"} onClick={() => setExpanded(expanded === a.alarm_id ? undefined : a.alarm_id)} />
                    </td>
                  </tr>
                  <tr style={{ display: expanded === a.alarm_id ? undefined : "none" }}>
                    <td colSpan={7}><Collapse isOpen={expanded === a.alarm_id} keepChildrenMounted={false}>{expanded === a.alarm_id && <Responses alarmId={a.alarm_id} />}</Collapse></td>
                  </tr>
                </Fragment>
              ))}
            </tbody>
          </HTMLTable>
        )}
      </Card>
      {acknowledging && (
        <ActionDialog isOpen action={acknowledge} onClose={() => setAcknowledging(undefined)} onDone={refresh} fixed={{ alarm_id: acknowledging.alarm_id }}
          title={`Acknowledge: ${words(acknowledging.parameter_name)} ${acknowledging.limit_violated}`} submitText="Acknowledge" summary="Alarm acknowledged"
          intro={<p>By acknowledging, you say that you have seen this alarm and take responsibility for it.</p>} />
      )}
    </div>
  );
}
