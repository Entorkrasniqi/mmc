import { describe, expect, it } from "vitest";

import type { CommandExecution, Me, Role } from "../api/types";
import { approveAvailability, cancelAvailability, lifecycleSteps, releaseAvailability, type CommandContext } from "./commands";

const NOW = new Date("2026-11-01T12:00:00Z");
const me = (operator_id: string, role: Role): Me => ({ operator_id, display_name: operator_id, kind: role === "AGENT" ? "AGENT" : "HUMAN", role });
const ALICE = me("alice", "OPERATOR");
const SAM = me("sam", "SUPERVISOR");
const TINA = me("tina", "SUPERVISOR");
const VERA = me("vera", "VIEWER");
const HELPER = me("helper", "AGENT");

function command(over: Partial<CommandExecution> = {}): CommandExecution {
  return {
    execution_id: "e1", spacecraft_id: "MINISAT-1", command_id: 1, command_name: "Noop", vital: false, arguments: {}, arguments_text: {},
    reason: "r", status: "PROPOSED", rejection_reason: null, proposed_by: "alice", approved_by: null, approval_note: null, cancelled_by: null,
    cancel_reason: null, override_reason: null, responds_to_alarm_id: null, raw_bytes_hex: "aa", proposed_at: "2026-11-01T11:55:00Z",
    expires_at: "2026-11-01T12:10:00Z", approved_at: null, released_at: null, sent_at: null, verified_at: null,
    preflight: { known: true, accepted: true }, state_snapshot: {}, expected_effect: [], contact: null, ...over,
  };
}
const ctx = (who: Me, over: Partial<CommandContext> = {}): CommandContext => ({ me: who, now: NOW, inContact: true, ...over });

describe("approving", () => {
  it("is open to an operator for an ordinary command", () => {
    expect(approveAvailability(command(), ctx(ALICE))).toEqual({ enabled: true });
  });

  it.each([[VERA], [HELPER]])("is closed to %o", (who) => {
    expect(approveAvailability(command(), ctx(who)).enabled).toBe(false);
  });

  it("wants a supervisor for a vital command, and not the one who proposed it (two-person rule)", () => {
    const vital = command({ vital: true, proposed_by: "sam" });
    expect(approveAvailability(vital, ctx(ALICE))).toMatchObject({ enabled: false, reason: expect.stringContaining("supervisor") });
    expect(approveAvailability(vital, ctx(SAM))).toMatchObject({ enabled: false, reason: expect.stringContaining("two-person") });
    expect(approveAvailability(vital, ctx(TINA)).enabled).toBe(true);
  });

  it("lets only a supervisor approve a command the satellite is predicted to reject, and asks for a note", () => {
    const risky = command({ preflight: { known: true, accepted: false, reason: "battery too low" } });
    expect(approveAvailability(risky, ctx(ALICE)).enabled).toBe(false);
    expect(approveAvailability(risky, ctx(SAM))).toEqual({ enabled: true, needsNote: true });
  });

  it("is closed once the proposal has expired (at the expiry instant, not after it) or is not PROPOSED any more", () => {
    expect(approveAvailability(command({ expires_at: NOW.toISOString() }), ctx(ALICE)).enabled).toBe(false);
    expect(approveAvailability(command({ expires_at: "2026-11-01T12:00:01Z" }), ctx(ALICE)).enabled).toBe(true);
    expect(approveAvailability(command({ status: "APPROVED" }), ctx(ALICE)).enabled).toBe(false);
  });

  it("trusts an unknown preflight (the server decides) rather than blocking", () => {
    expect(approveAvailability(command({ preflight: { known: false, accepted: null } }), ctx(ALICE)).enabled).toBe(true);
  });
});

describe("releasing", () => {
  const approved = command({ status: "APPROVED", approved_by: "bob" });

  it("is open to an operator inside a contact window", () => {
    expect(releaseAvailability(approved, ctx(ALICE))).toEqual({ enabled: true });
  });

  it("outside a contact window, only a supervisor may go on, with a reason", () => {
    expect(releaseAvailability(approved, ctx(ALICE, { inContact: false })).enabled).toBe(false);
    expect(releaseAvailability(approved, ctx(SAM, { inContact: false }))).toEqual({ enabled: true, needsOverride: true });
  });

  it("waits for a command that is in flight (one at a time), but not for itself", () => {
    const busy = { execution_id: "e2", command_name: "SetMode", status: "SENT" } as const;
    expect(releaseAvailability(approved, ctx(ALICE, { inFlight: busy }))).toMatchObject({ enabled: false, reason: expect.stringContaining("SetMode") });
    expect(releaseAvailability(approved, ctx(ALICE, { inFlight: { ...busy, execution_id: "e1" } })).enabled).toBe(true);
  });

  it("is closed to viewers and agents, to unapproved commands, and to expired approvals", () => {
    expect(releaseAvailability(approved, ctx(VERA)).enabled).toBe(false);
    expect(releaseAvailability(approved, ctx(HELPER)).enabled).toBe(false);
    expect(releaseAvailability(command(), ctx(ALICE)).enabled).toBe(false);
    expect(releaseAvailability({ ...approved, expires_at: "2026-11-01T11:59:59Z" }, ctx(ALICE)).enabled).toBe(false);
  });
});

describe("cancelling", () => {
  it("is possible before release, for people, and for an agent only on its own proposals", () => {
    expect(cancelAvailability(command(), ctx(ALICE)).enabled).toBe(true);
    expect(cancelAvailability(command({ status: "APPROVED" }), ctx(SAM)).enabled).toBe(true);
    expect(cancelAvailability(command({ proposed_by: "helper" }), ctx(HELPER)).enabled).toBe(true);
    expect(cancelAvailability(command({ proposed_by: "alice" }), ctx(HELPER)).enabled).toBe(false);
    expect(cancelAvailability(command(), ctx(VERA)).enabled).toBe(false);
  });

  it.each(["RELEASED", "SENT", "ACCEPTED", "VERIFIED", "FAILED", "CANCELLED"] as const)("is not possible once %s", (status) => {
    expect(cancelAvailability(command({ status }), ctx(SAM)).enabled).toBe(false);
  });
});

describe("lifecycleSteps", () => {
  const states = (status: CommandExecution["status"]) => lifecycleSteps(status).map((s) => `${s.step}:${s.state}`);

  it("marks the steps before the current one done and the ones after it to do", () => {
    expect(states("APPROVED")).toEqual(["PROPOSED:done", "APPROVED:current", "RELEASED:todo", "SENT:todo", "ACCEPTED:todo", "VERIFIED:todo"]);
  });

  it("shows a verified command as done all the way", () => {
    expect(lifecycleSteps("VERIFIED").every((s) => s.state === "done")).toBe(true);
  });

  it("ends a rejected or failed command in its outcome, after SENT", () => {
    expect(states("REJECTED_ONBOARD")).toEqual(["PROPOSED:done", "APPROVED:done", "RELEASED:done", "SENT:done", "REJECTED_ONBOARD:failed"]);
    expect(states("FAILED").at(-1)).toBe("FAILED:failed");
  });

  it("ends a cancelled command in CANCELLED", () => {
    expect(states("CANCELLED")).toEqual(["PROPOSED:done", "CANCELLED:failed"]);
  });
});
