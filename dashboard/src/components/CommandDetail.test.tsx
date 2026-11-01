import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setToken } from "../api/client";
import type { ActionInfo, CommandExecution, Definitions, Me, Role } from "../api/types";
import schemas from "../test/action-schemas.json";
import { mockFetch } from "../test/helpers";
import { CommandDetail, effectText } from "./CommandDetail";

const DEFINITIONS = {
  mission_name: "MiniSat",
  commands: [],
  parameters: [
    { name: "mode", unit: null, description: "", warning: null, critical: null, enum_labels: [{ label: "SAFE", value: 0 }, { label: "NOMINAL", value: 1 }, { label: "PAYLOAD", value: 2 }] },
    { name: "battery_soc_pct", unit: "%", description: "", warning: [35, null], critical: [20, null], enum_labels: null },
    { name: "uptime_s", unit: "s", description: "", warning: null, critical: null, enum_labels: null },
  ],
} as unknown as Definitions;

vi.mock("../Data", () => ({
  useData: () => ({ operatorNames: { alice: "Alice", bob: "Bob", sam: "Sam", tina: "Tina" }, definitions: DEFINITIONS }),
}));

const me = (operator_id: string, role: Role): Me => ({ operator_id, display_name: operator_id, kind: "HUMAN", role });
const NOW = new Date();
const soon = new Date(NOW.getTime() + 10 * 60_000).toISOString();

function action(name: keyof typeof schemas): ActionInfo {
  const entry = schemas[name] as unknown as { slug: string; schema: ActionInfo["schema"] };
  return { name, slug: entry.slug, path: `/api/actions/${entry.slug}`, description: "", roles: ["OPERATOR"], agent_callable: false, requires_human_confirmation: false, allowed_for_me: true, schema: entry.schema };
}
const ACTIONS = (["Approve Command", "Release Command", "Cancel Command"] as const).map(action);

function command(over: Partial<CommandExecution> = {}): CommandExecution {
  return {
    execution_id: "5b0c1d2e-0000-4000-8000-000000000001", spacecraft_id: "MINISAT-1", command_id: 2, command_name: "SetMode", vital: false,
    arguments: { mode: 2 }, arguments_text: { mode: "PAYLOAD" }, reason: "payload pass over Helsinki", status: "PROPOSED", rejection_reason: null,
    proposed_by: "alice", approved_by: null, approval_note: null, cancelled_by: null, cancel_reason: null, override_reason: null,
    responds_to_alarm_id: null, raw_bytes_hex: "100ac0000002000202", proposed_at: "2026-11-01T11:55:00Z", expires_at: soon, approved_at: null,
    released_at: null, sent_at: null, verified_at: null, preflight: { known: true, accepted: true, state_age_s: 0.4, stale: false },
    state_snapshot: { mode: 1, battery_soc_pct: 82.5, uptime_s: 900 }, expected_effect: [{ parameter: "mode", op: "eq", value: 2 }], contact: null, ...over,
  };
}

function show(c: CommandExecution, who: Me, ctx: { inContact?: boolean } = {}) {
  return render(<CommandDetail command={c} actions={ACTIONS} onChanged={() => undefined} context={{ me: who, now: new Date(), inContact: ctx.inContact ?? true }} />);
}

beforeEach(() => setToken("tok-for-test-0123456789"));
afterEach(() => vi.unstubAllGlobals());

describe("the evidence an approver sees", () => {
  it("shows the exact bytes, the reason, the state at proposal and the effect telemetry must show", () => {
    show(command(), me("bob", "OPERATOR"));
    const evidence = screen.getByTestId("evidence");
    expect(within(evidence).getByTestId("bytes")).toHaveTextContent("100ac0000002000202");
    expect(evidence).toHaveTextContent("payload pass over Helsinki");
    expect(evidence).toHaveTextContent("Alice at 2026-11-01 11:55:00");
    expect(evidence).toHaveTextContent("the satellite is predicted to accept it");
    expect(evidence).toHaveTextContent("battery soc pct 82.5 %");
    expect(evidence).toHaveTextContent("mode NOMINAL");
    expect(evidence).toHaveTextContent("mode = PAYLOAD");
    expect(screen.getByTestId("detail-title")).toHaveTextContent("SetMode mode=PAYLOAD");
  });

  it("warns, in words, about a command the satellite is predicted to reject", () => {
    show(command({ preflight: { known: true, accepted: false, reason: "battery too low for PAYLOAD mode (25 % < 30 %)", state_age_s: 1, stale: false } }), me("bob", "OPERATOR"));
    expect(screen.getByText("Predicted to be rejected")).toBeInTheDocument();
    expect(screen.getByTestId("evidence")).toHaveTextContent("predicted to REJECT: battery too low for PAYLOAD mode (25 % < 30 %)");
  });

  it("says when the state was unknown", () => {
    show(command({ preflight: { known: false, accepted: null }, state_snapshot: {} }), me("bob", "OPERATOR"));
    expect(screen.getByTestId("evidence")).toHaveTextContent("state unknown: the command could not be checked");
    expect(screen.getByTestId("evidence")).toHaveTextContent("no telemetry yet");
  });

  it("shows who approved, with the note, and the contact it went out in", () => {
    show(command({ status: "SENT", approved_by: "tina", approved_at: "2026-11-01T11:56:00Z", approval_note: "go ahead", sent_at: "2026-11-01T11:57:00Z",
      contact: { contact_id: "c1", station_id: "HEL", start_at: "2026-11-01T11:50:00Z", end_at: "2026-11-01T12:10:00Z" } }), me("bob", "OPERATOR"));
    const evidence = screen.getByTestId("evidence");
    expect(evidence).toHaveTextContent("Tina at 2026-11-01 11:56:00");
    expect(evidence).toHaveTextContent("go ahead");
    expect(evidence).toHaveTextContent("HEL, 2026-11-01 11:50:00 to 2026-11-01 12:10:00 UTC");
  });

  it("shows the satellite's rejection, the failure reason and the verification", () => {
    const { unmount } = show(command({ status: "REJECTED_ONBOARD", rejection_reason: "rejected on board: the counter rose" }), me("bob", "OPERATOR"));
    expect(screen.getByText("The satellite rejected it")).toBeInTheDocument();
    expect(screen.getByText(/the counter rose/)).toBeInTheDocument();
    unmount();
    show(command({ status: "VERIFIED", verified_at: "2026-11-01T11:58:30Z" }), me("bob", "OPERATOR"));
    expect(screen.getByText("Took effect")).toBeInTheDocument();
  });

  it("writes an expected effect with its enum label", () => {
    expect(effectText({ parameter: "mode", op: "eq", value: 2 }, DEFINITIONS)).toBe("mode = PAYLOAD");
    expect(effectText({ parameter: "uptime_s", op: "decreases" }, DEFINITIONS)).toBe("uptime_s decreases");
    expect(effectText({ parameter: "unknown", op: "eq", value: 7 }, DEFINITIONS)).toBe("unknown = 7");
  });
});

describe("which buttons each person is offered", () => {
  const state = (id: string) => (screen.getByTestId(id) as HTMLButtonElement).disabled;

  it("lets an operator approve an ordinary proposal but not release it yet", () => {
    show(command(), me("bob", "OPERATOR"));
    expect([state("btn-approve"), state("btn-release"), state("btn-cancel")]).toEqual([false, true, false]);
  });

  it("offers a viewer nothing", () => {
    show(command(), me("vera", "VIEWER"));
    expect([state("btn-approve"), state("btn-release"), state("btn-cancel")]).toEqual([true, true, true]);
  });

  it("keeps a vital command from its proposer and from an operator (two-person rule)", () => {
    const vital = command({ vital: true, proposed_by: "sam", command_name: "Reboot", arguments: {}, arguments_text: {} });
    const { unmount } = show(vital, me("sam", "SUPERVISOR"));
    expect(state("btn-approve")).toBe(true);
    unmount();
    const operator = show(vital, me("bob", "OPERATOR"));
    expect(state("btn-approve")).toBe(true);
    operator.unmount();
    show(vital, me("tina", "SUPERVISOR"));
    expect(state("btn-approve")).toBe(false);
  });

  it("offers release to an operator once approved, in contact; outside contact only a supervisor", () => {
    const approved = command({ status: "APPROVED", approved_by: "bob" });
    const inside = show(approved, me("alice", "OPERATOR"));
    expect(state("btn-release")).toBe(false);
    inside.unmount();
    const outside = show(approved, me("alice", "OPERATOR"), { inContact: false });
    expect(state("btn-release")).toBe(true);
    outside.unmount();
    show(approved, me("sam", "SUPERVISOR"), { inContact: false });
    expect(state("btn-release")).toBe(false);
  });
});

describe("running a step", () => {
  it("approving sends the execution id and the note, and asks for the note when the satellite is predicted to reject", async () => {
    const calls = mockFetch(() => ({ json: { action: "Approve Command", audit_id: 5, result: {}, warnings: [], replayed: false, correlation_id: "c" } }));
    const risky = command({ preflight: { known: true, accepted: false, reason: "battery too low", state_age_s: 1, stale: false } });
    show(risky, me("sam", "SUPERVISOR"));
    await userEvent.click(screen.getByTestId("btn-approve"));
    expect(await screen.findByText(/predicted to reject this command/i)).toBeInTheDocument();
    await userEvent.click(screen.getByTestId("action-submit"));
    expect(await screen.findByText("required")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
    await userEvent.type(screen.getByLabelText(/note/i), "payload data is worth it");
    await userEvent.click(screen.getByTestId("action-submit"));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]!.url.pathname).toBe("/api/actions/approve-command");
    expect(calls[0]!.body).toEqual({ execution_id: risky.execution_id, note: "payload data is worth it" });
  });

  it("releasing during a contact asks for nothing, and outside one a supervisor must give a reason", async () => {
    const calls = mockFetch(() => ({ json: { action: "Release Command", audit_id: 6, result: {}, warnings: [], replayed: false, correlation_id: "c" } }));
    const approved = command({ status: "APPROVED", approved_by: "bob" });
    const inside = show(approved, me("alice", "OPERATOR"));
    await userEvent.click(screen.getByTestId("btn-release"));
    expect(screen.queryByLabelText(/override reason/i)).toBeNull();
    await userEvent.click(screen.getByTestId("action-submit"));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]!.body).toEqual({ execution_id: approved.execution_id });
    inside.unmount();

    show(approved, me("sam", "SUPERVISOR"), { inContact: false });
    await userEvent.click(screen.getByTestId("btn-release"));
    await userEvent.click(screen.getByTestId("action-submit"));
    expect(await screen.findByText("required")).toBeInTheDocument();
    expect(calls).toHaveLength(1);
  });
});
