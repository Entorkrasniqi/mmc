import type { CommandExecution, Me } from "../api/types";

/**
 * What the buttons of a command may offer. This only decides what to SHOW (a button that would certainly be refused is
 * disabled, with the reason beside it). It is not a security check: the action runner decides, always, and a refusal from it is
 * shown as it comes (ADR 0003: the backend cannot trust the browser).
 */
export interface Availability {
  enabled: boolean;
  reason?: string;
  /** The runner wants a written note (approving a command the satellite is predicted to reject). */
  needsNote?: boolean;
  /** No contact window now: only a supervisor, with a written reason, may release anyway. */
  needsOverride?: boolean;
}

export interface CommandContext {
  me: Me;
  now: Date;
  /** Another command of this spacecraft that is RELEASED, SENT or ACCEPTED (one at a time). */
  inFlight?: Pick<CommandExecution, "execution_id" | "command_name" | "status">;
  inContact: boolean;
}

const PEOPLE = new Set(["OPERATOR", "SUPERVISOR"]);

const no = (reason: string): Availability => ({ enabled: false, reason });

export function approveAvailability(c: CommandExecution, ctx: CommandContext): Availability {
  if (c.status !== "PROPOSED") return no(`only a proposed command can be approved; this one is ${c.status}`);
  if (!PEOPLE.has(ctx.me.role)) return no(`a ${ctx.me.role.toLowerCase()} cannot approve commands`);
  if (new Date(c.expires_at) <= ctx.now) return no("the proposal has expired: propose it again");
  if (c.vital && ctx.me.role !== "SUPERVISOR") return no("a vital command must be approved by a supervisor");
  if (c.vital && ctx.me.operator_id === c.proposed_by) return no("two-person rule: you proposed this vital command");
  if (c.preflight.accepted === false) {
    if (ctx.me.role !== "SUPERVISOR") return no("the satellite is predicted to reject it: only a supervisor may approve it anyway");
    return { enabled: true, needsNote: true };
  }
  return { enabled: true };
}

export function releaseAvailability(c: CommandExecution, ctx: CommandContext): Availability {
  if (c.status !== "APPROVED") return no(`only an approved command can be released; this one is ${c.status}`);
  if (!PEOPLE.has(ctx.me.role)) return no(`a ${ctx.me.role.toLowerCase()} cannot release commands`);
  if (new Date(c.expires_at) <= ctx.now) return no("the approval has expired: propose it again");
  if (ctx.inFlight && ctx.inFlight.execution_id !== c.execution_id) {
    return no(`${ctx.inFlight.command_name} is still in flight (${ctx.inFlight.status}): one command at a time`);
  }
  if (!ctx.inContact) {
    if (ctx.me.role !== "SUPERVISOR") return no("no contact window with the spacecraft now: a supervisor may release anyway");
    return { enabled: true, needsOverride: true };
  }
  return { enabled: true };
}

export function cancelAvailability(c: CommandExecution, ctx: CommandContext): Availability {
  if (c.status !== "PROPOSED" && c.status !== "APPROVED") return no(`a command can be cancelled only before it is released`);
  if (ctx.me.role === "VIEWER") return no("a viewer cannot change anything");
  if (ctx.me.role === "AGENT" && ctx.me.operator_id !== c.proposed_by) return no("an agent may cancel only its own proposals");
  return { enabled: true };
}

/** The steps of the normal path, in order. A command that did not make it ends in its outcome instead of the later steps. */
export const LIFECYCLE = ["PROPOSED", "APPROVED", "RELEASED", "SENT", "ACCEPTED", "VERIFIED"] as const;

export type StepState = "done" | "current" | "todo" | "failed";

export function lifecycleSteps(status: CommandExecution["status"]): { step: string; state: StepState }[] {
  if (status === "CANCELLED") return [{ step: "PROPOSED", state: "done" }, { step: "CANCELLED", state: "failed" }];
  if (status === "REJECTED_ONBOARD" || status === "FAILED") {
    // it was sent (nothing is rejected or fails before that); whether it was also accepted first is in the record
    return [...LIFECYCLE.slice(0, 4).map((step) => ({ step, state: "done" as StepState })), { step: status, state: "failed" }];
  }
  const index = LIFECYCLE.indexOf(status);
  return LIFECYCLE.map((step, i) => ({
    step,
    state: i < index ? "done" : i === index ? (status === "VERIFIED" ? "done" : "current") : "todo",
  }));
}
