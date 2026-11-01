import { Button, Callout, Card, H4, NonIdealState, Tag, Tooltip } from "@blueprintjs/core";
import { useEffect, useMemo, useState } from "react";

import { get } from "../api/client";
import type { CommandExecution, ContactWindow, GroundStation, Page, Spacecraft } from "../api/types";
import { ActionDialog } from "../components/ActionDialog";
import { CommandDetail } from "../components/CommandDetail";
import { ProposeCommandDialog } from "../components/ProposeCommandDialog";
import { StatusTag } from "../components/Tags";
import { LIVE_MS, useData } from "../Data";
import { usePoll } from "../hooks/usePoll";
import { formatTime } from "../util/format";

const IN_FLIGHT = new Set(["RELEASED", "SENT", "ACCEPTED"]);
const DONE = new Set(["VERIFIED", "REJECTED_ONBOARD", "FAILED", "CANCELLED"]);

function ContactBar({ contacts, now }: { contacts: ContactWindow[]; now: Date }) {
  const current = contacts.find((c) => new Date(c.start_at) <= now && now < new Date(c.end_at) && (c.status === "PLANNED" || c.status === "ACTIVE"));
  const next = contacts.filter((c) => new Date(c.start_at) > now && c.status !== "MISSED")[0];
  if (current) {
    return (
      <Callout intent="success" icon="satellite" data-testid="contact-bar">
        In contact with <strong>{current.station_id}</strong> until {formatTime(current.end_at)} UTC. Commands can be released.
      </Callout>
    );
  }
  return (
    <Callout intent="warning" icon="offline" title="No contact window now" data-testid="contact-bar">
      A command can be released only during a planned contact; a supervisor may override that with a written reason.
      {next ? ` Next contact: ${next.station_id} at ${formatTime(next.start_at)} UTC.` : " No contact is planned."}
    </Callout>
  );
}

export function Commands({ spacecraft, respondTo, onResponded }: { spacecraft: Spacecraft; respondTo?: string; onResponded: () => void }) {
  const { me, definitions, actions, operatorNames } = useData();
  const id = spacecraft.spacecraft_id;
  const list = usePoll((signal) => get<Page<CommandExecution>>(`/api/spacecraft/${id}/commands`, { limit: 60 }, signal), LIVE_MS, [id]);
  const contacts = usePoll((signal) => get<Page<ContactWindow>>(`/api/spacecraft/${id}/contacts`,
    { since: new Date().toISOString(), until: new Date(Date.now() + 24 * 3600 * 1000).toISOString(), limit: 20 }, signal), 5000, [id]);
  const stations = usePoll((signal) => get<{ items: GroundStation[] }>("/api/ground-stations", undefined, signal), null);
  const [selectedId, setSelectedId] = useState<string>();
  const [proposing, setProposing] = useState<string | boolean>(false);
  const [planning, setPlanning] = useState(false);

  useEffect(() => {
    if (respondTo) setProposing(respondTo);
  }, [respondTo]);

  const commands = useMemo(() => list.data?.items ?? [], [list.data]);
  const selected = commands.find((c) => c.execution_id === selectedId) ?? commands.find((c) => !DONE.has(c.status)) ?? commands[0];
  const inFlight = commands.find((c) => IN_FLIGHT.has(c.status));
  const now = new Date();
  const inContact = (contacts.data?.items ?? []).some((c) => new Date(c.start_at) <= now && now < new Date(c.end_at) && (c.status === "PLANNED" || c.status === "ACTIVE"));
  const canPropose = actions.find((a) => a.name === "Propose Command")?.allowed_for_me ?? false;
  const planContact = actions.find((a) => a.name === "Plan Contact");

  return (
    <div className="page">
      <div className="spread">
        <H4 style={{ margin: 0 }}>Commands for {spacecraft.name}</H4>
        <div className="inline">
          {planContact?.allowed_for_me && <Button icon="calendar" text="Plan contact" onClick={() => setPlanning(true)} data-testid="plan-contact" />}
          <Tooltip content={canPropose ? "" : `a ${me.role.toLowerCase()} cannot propose commands`} disabled={canPropose}>
            <Button intent="primary" icon="send-message" text="Propose command" disabled={!canPropose} onClick={() => setProposing(true)} data-testid="propose" />
          </Tooltip>
        </div>
      </div>
      <ContactBar contacts={contacts.data?.items ?? []} now={now} />
      {list.error && <Callout intent="danger">{list.error.message}</Callout>}
      <div className="split">
        <Card style={{ padding: 0 }} data-testid="command-list">
          {commands.length === 0 ? (
            <NonIdealState icon="send-message" title="No commands yet" description="Propose one. Nothing is sent until a person approves and releases it." />
          ) : commands.map((c) => (
            <div key={c.execution_id} role="button" tabIndex={0} className={`list-item ${selected?.execution_id === c.execution_id ? "selected" : ""}`}
              data-testid={`command-${c.command_name}`} onClick={() => setSelectedId(c.execution_id)}
              onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && setSelectedId(c.execution_id)}>
              <div className="spread">
                <strong>{c.command_name} <span className="muted">{Object.entries(c.arguments).map(([k, v]) => c.arguments_text[k] ?? `${k}=${v}`).join(", ")}</span></strong>
                <span className="inline">{c.vital && <Tag minimal intent="danger">VITAL</Tag>}<StatusTag status={c.status} /></span>
              </div>
              <div className="small muted">{operatorNames[c.proposed_by] ?? c.proposed_by} at {formatTime(c.proposed_at)} &middot; {c.reason}</div>
            </div>
          ))}
        </Card>
        {selected ? (
          <CommandDetail command={selected} actions={actions} onChanged={list.refresh}
            context={{ me, now, inFlight, inContact }} />
        ) : <Card><NonIdealState icon="document" title="Nothing selected" /></Card>}
      </div>

      {proposing && definitions && (
        <ProposeCommandDialog spacecraftId={id} commands={definitions.commands} respondsToAlarm={typeof proposing === "string" ? proposing : undefined}
          onClose={() => { setProposing(false); onResponded(); }}
          onDone={(r) => { setProposing(false); onResponded(); setSelectedId(String(r.result.execution_id)); list.refresh(); }} />
      )}
      {planning && (
        <ActionDialog isOpen action={planContact} onClose={() => setPlanning(false)} onDone={contacts.refresh}
          fixed={{ spacecraft_id: id }} hide={["max_elevation_deg"]} initial={{ station_id: stations.data?.items[0]?.station_id ?? "" }}
          title="Plan a contact window" submitText="Plan contact" summary="Contact planned"
          intro={<p>A contact window is when a station can talk to the spacecraft. Commands are released only inside one.</p>} />
      )}
    </div>
  );
}
