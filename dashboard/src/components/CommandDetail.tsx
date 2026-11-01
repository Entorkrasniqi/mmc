import { Button, ButtonGroup, Callout, Card, H5, Tag, Tooltip } from "@blueprintjs/core";
import { useState } from "react";

import type { ActionInfo, CommandExecution, Definitions } from "../api/types";
import { useData } from "../Data";
import { approveAvailability, cancelAvailability, lifecycleSteps, releaseAvailability, type Availability, type CommandContext } from "../util/commands";
import { formatDateTime, formatValue, words } from "../util/format";
import { ActionDialog } from "./ActionDialog";
import { StatusTag } from "./Tags";

type Pending = "approve" | "release" | "cancel" | undefined;

export function effectText(effect: CommandExecution["expected_effect"][number], definitions: Definitions | undefined): string {
  const labels = definitions?.parameters.find((p) => p.name === effect.parameter)?.enum_labels;
  const shown = effect.value === undefined ? "" : labels?.find((l) => l.value === effect.value)?.label ?? String(effect.value);
  const op = { eq: "=", decreases: "decreases", increases: "increases" }[effect.op] ?? effect.op;
  return `${effect.parameter} ${op}${shown ? ` ${shown}` : ""}`;
}

function Gated({ what, availability, intent, icon, onClick }: { what: string; availability: Availability; intent?: "primary" | "danger" | "none"; icon: "tick" | "send-to" | "cross"; onClick: () => void }) {
  const button = (
    <Button text={what} icon={icon} intent={intent ?? "none"} disabled={!availability.enabled} onClick={onClick} data-testid={`btn-${what.toLowerCase()}`} />
  );
  return availability.enabled ? button : <Tooltip content={availability.reason} placement="top"><span>{button}</span></Tooltip>;
}

function Fact({ term, children }: { term: string; children: React.ReactNode }) {
  return <><dt>{term}</dt><dd>{children}</dd></>;
}

const SNAPSHOT = ["mode", "battery_soc_pct", "battery_voltage", "in_eclipse", "heater"] as const;

/**
 * One command execution with the evidence a reviewer needs (what is being approved: the exact bytes, the preflight verdict, the
 * satellite's state at proposal time, the effect telemetry must show), where it stands, and the steps this person may take next.
 */
export function CommandDetail({ command: c, context, actions, onChanged }: { command: CommandExecution; context: CommandContext; actions: ActionInfo[]; onChanged: () => void }) {
  const { operatorNames, definitions } = useData();
  const [pending, setPending] = useState<Pending>();
  const who = (id: string | null) => (id ? operatorNames[id] ?? id : "—");
  const approve = approveAvailability(c, context);
  const release = releaseAvailability(c, context);
  const cancel = cancelAvailability(c, context);
  const action = (name: string) => actions.find((a) => a.name === name);
  const steps = lifecycleSteps(c.status);
  const argText = Object.entries(c.arguments).map(([k, v]) => `${k}=${c.arguments_text[k] ?? v}`).join(", ");
  const pre = c.preflight;

  return (
    <Card data-testid="command-detail">
      <div className="spread">
        <div className="inline">
          <H5 style={{ margin: 0 }} data-testid="detail-title">{c.command_name}{argText ? ` ${argText}` : ""}</H5>
          <StatusTag status={c.status} />
          {c.vital && <Tag intent="danger" icon="shield">VITAL</Tag>}
        </div>
        <span className="small muted mono">{c.execution_id.slice(0, 8)}</span>
      </div>

      <div className="steps" style={{ margin: "12px 0" }} data-testid="steps">
        {steps.map((s) => <span key={s.step} className={`step ${s.state}`}>{words(s.step)}</span>)}
      </div>

      <div className="inline" style={{ marginBottom: 12 }}>
        <ButtonGroup>
          <Gated what="Approve" icon="tick" intent="primary" availability={approve} onClick={() => setPending("approve")} />
          <Gated what="Release" icon="send-to" intent="primary" availability={release} onClick={() => setPending("release")} />
          <Gated what="Cancel" icon="cross" availability={cancel} onClick={() => setPending("cancel")} />
        </ButtonGroup>
      </div>

      {c.status === "REJECTED_ONBOARD" && <Callout intent="danger" icon="ban-circle" title="The satellite rejected it" style={{ marginBottom: 12 }}>{c.rejection_reason}</Callout>}
      {c.status === "FAILED" && <Callout intent="danger" icon="error" title="Failed" style={{ marginBottom: 12 }}>{c.rejection_reason}</Callout>}
      {c.status === "VERIFIED" && <Callout intent="success" icon="tick-circle" title="Took effect" style={{ marginBottom: 12 }}>The telemetry showed the expected effect at {formatDateTime(c.verified_at)} UTC.</Callout>}
      {c.status === "CANCELLED" && <Callout icon="cross-circle" title={`Cancelled by ${who(c.cancelled_by)}`} style={{ marginBottom: 12 }}>{c.cancel_reason}</Callout>}
      {pre.accepted === false && c.status === "PROPOSED" && (
        <Callout intent="warning" icon="warning-sign" title="Predicted to be rejected" style={{ marginBottom: 12 }}>{pre.reason}</Callout>
      )}

      <dl className="facts" data-testid="evidence">
        <Fact term="Reason">{c.reason}</Fact>
        <Fact term="Proposed">{who(c.proposed_by)} at {formatDateTime(c.proposed_at)}, valid until {formatDateTime(c.expires_at)}</Fact>
        <Fact term="Exact bytes"><span className="mono" data-testid="bytes">{c.raw_bytes_hex ?? "—"}</span></Fact>
        <Fact term="Preflight">
          {pre.known === false ? "state unknown: the command could not be checked"
            : pre.accepted ? "the satellite is predicted to accept it" : `predicted to REJECT: ${pre.reason}`}
          {pre.state_age_s !== undefined && pre.state_age_s !== null && <span className="muted"> (state {formatValue(pre.state_age_s, "s", 0)} old{pre.stale ? ", stale" : ""})</span>}
        </Fact>
        <Fact term="State at proposal">
          {SNAPSHOT.filter((k) => k in c.state_snapshot).map((k) => {
            const def = definitions?.parameters.find((p) => p.name === k);
            const v = c.state_snapshot[k]!;
            const label = def?.enum_labels?.find((l) => l.value === v)?.label;
            return <span key={k} className="nowrap" style={{ marginRight: 12 }}>{k.replace(/_/g, " ")} <strong>{label ?? formatValue(v, def?.unit, 1)}</strong></span>;
          })}
          {Object.keys(c.state_snapshot).length === 0 && "no telemetry yet"}
        </Fact>
        <Fact term="Must show">{c.expected_effect.length ? c.expected_effect.map((e) => effectText(e, definitions)).join(" and ") : "nothing beyond the acceptance counter"}</Fact>
        <Fact term="Approved">{c.approved_by ? <>{who(c.approved_by)} at {formatDateTime(c.approved_at)}{c.approval_note ? <> &mdash; &ldquo;{c.approval_note}&rdquo;</> : null}</> : "—"}</Fact>
        <Fact term="Contact">{c.contact ? `${c.contact.station_id}, ${formatDateTime(c.contact.start_at)} to ${formatDateTime(c.contact.end_at)} UTC` : c.override_reason ? `none: released on override (${c.override_reason})` : "—"}</Fact>
        <Fact term="Sent">{formatDateTime(c.sent_at)}</Fact>
        {c.responds_to_alarm_id && <Fact term="Responds to alarm"><span className="mono small">{c.responds_to_alarm_id.slice(0, 8)}</span></Fact>}
      </dl>

      {pending === "approve" && (
        <ActionDialog isOpen action={action("Approve Command")} onClose={() => setPending(undefined)} onDone={onChanged} fixed={{ execution_id: c.execution_id }}
          require={approve.needsNote ? ["note"] : []} title={`Approve ${c.command_name}`} submitText="Approve" summary={`${c.command_name} approved`}
          intro={<>
            {c.vital && <Callout intent="warning" icon="shield">A vital command: the two-person rule applies.</Callout>}
            {approve.needsNote && <Callout intent="danger" icon="warning-sign">The satellite is predicted to reject this command ({pre.reason}). Approve it only if you know better, and say why.</Callout>}
          </>} />
      )}
      {pending === "release" && (
        <ActionDialog isOpen action={action("Release Command")} onClose={() => setPending(undefined)} onDone={onChanged} fixed={{ execution_id: c.execution_id }}
          hide={release.needsOverride ? [] : ["override_reason"]} require={release.needsOverride ? ["override_reason"] : []}
          title={`Release ${c.command_name} to the link`} submitText="Release" summary={`${c.command_name} released`}
          intro={<Callout intent={release.needsOverride ? "warning" : "primary"} icon="send-to">
            {release.needsOverride ? "There is no contact window with the spacecraft now. As a supervisor you may release anyway, with a reason." : "The command goes to the link once and is never re-sent by itself."}
          </Callout>} />
      )}
      {pending === "cancel" && (
        <ActionDialog isOpen action={action("Cancel Command")} onClose={() => setPending(undefined)} onDone={onChanged} fixed={{ execution_id: c.execution_id }}
          title={`Cancel ${c.command_name}`} submitText="Cancel the command" summary={`${c.command_name} cancelled`} />
      )}
    </Card>
  );
}
