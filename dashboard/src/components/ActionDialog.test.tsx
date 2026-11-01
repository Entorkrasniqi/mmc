import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { setToken } from "../api/client";
import type { ActionInfo, SchemaProperty } from "../api/types";
import schemas from "../test/action-schemas.json";
import { mockFetch } from "../test/helpers";
import { ActionDialog } from "./ActionDialog";

type Schema = ActionInfo["schema"];
function action(name: keyof typeof schemas): ActionInfo {
  const entry = schemas[name] as unknown as { slug: string; schema: Schema };
  return { name, slug: entry.slug, path: `/api/actions/${entry.slug}`, description: `${name} (test)`, roles: ["OPERATOR"], agent_callable: false,
    requires_human_confirmation: false, allowed_for_me: true, schema: entry.schema };
}

beforeEach(() => setToken("tok-for-alice-0123456789"));
afterEach(() => vi.unstubAllGlobals());

const OK = { json: { action: "Acknowledge Alarm", audit_id: 41, result: { state: "ACKNOWLEDGED" }, warnings: [], replayed: false, correlation_id: "c" } };

describe("an action dialog built from the action's schema", () => {
  it("shows the fields the user fills in, not the ones fixed or hidden", () => {
    mockFetch(() => OK);
    render(<ActionDialog isOpen action={action("Update Anomaly")} onClose={() => undefined} fixed={{ anomaly_id: "A1", status: "RESOLVED" }} hide={["execution_ids"]} />);
    expect(screen.getByLabelText(/root cause/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/resolution note/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/anomaly id/i)).toBeNull();
    expect(screen.queryByLabelText(/execution ids/i)).toBeNull();
  });

  it("sends exactly the typed and fixed parameters, with a token, an idempotency key and a correlation id", async () => {
    const calls = mockFetch(() => OK);
    const onDone = vi.fn();
    const onClose = vi.fn();
    render(<ActionDialog isOpen action={action("Acknowledge Alarm")} onClose={onClose} onDone={onDone} fixed={{ alarm_id: "11111111-1111-1111-1111-111111111111" }} />);
    await userEvent.type(screen.getByLabelText(/note/i), "seen it");
    await userEvent.click(screen.getByTestId("action-submit"));
    await waitFor(() => expect(onDone).toHaveBeenCalledOnce());
    expect(calls).toHaveLength(1);
    expect(calls[0]!.method).toBe("POST");
    expect(calls[0]!.url.pathname).toBe("/api/actions/acknowledge-alarm");
    expect(calls[0]!.body).toEqual({ alarm_id: "11111111-1111-1111-1111-111111111111", note: "seen it" });
    expect(calls[0]!.headers.Authorization).toBe("Bearer tok-for-alice-0123456789");
    expect(calls[0]!.headers["Idempotency-Key"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(calls[0]!.headers["X-Correlation-ID"]).toMatch(/^[0-9a-f-]{36}$/);
    expect(onClose).toHaveBeenCalled();
  });

  it("leaves an optional field out when it is empty", async () => {
    const calls = mockFetch(() => OK);
    render(<ActionDialog isOpen action={action("Acknowledge Alarm")} onClose={() => undefined} fixed={{ alarm_id: "A" }} />);
    await userEvent.click(screen.getByTestId("action-submit"));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]!.body).toEqual({ alarm_id: "A" });
  });

  it("does not send a request while a required field is empty, and says which", async () => {
    const calls = mockFetch(() => OK);
    render(<ActionDialog isOpen action={action("Cancel Command")} onClose={() => undefined} fixed={{ execution_id: "E1" }} />);
    await userEvent.click(screen.getByTestId("action-submit"));
    expect(await screen.findByText("required")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
  });

  it("can insist on a field the schema calls optional (the note for a risky approval)", async () => {
    const calls = mockFetch(() => OK);
    render(<ActionDialog isOpen action={action("Approve Command")} onClose={() => undefined} fixed={{ execution_id: "E1" }} require={["note"]} />);
    await userEvent.click(screen.getByTestId("action-submit"));
    expect(await screen.findByText("required")).toBeInTheDocument();
    expect(calls).toHaveLength(0);
    await userEvent.type(screen.getByLabelText(/note/i), "I know better");
    await userEvent.click(screen.getByTestId("action-submit"));
    await waitFor(() => expect(calls).toHaveLength(1));
    expect(calls[0]!.body).toEqual({ execution_id: "E1", note: "I know better" });
  });

  it("shows the server's refusal as it is, with the audit number, and stays open", async () => {
    mockFetch(() => ({ status: 403, json: { detail: "two-person rule: a vital command cannot be approved by the person who proposed it", outcome: "DENIED", audit_id: 7, correlation_id: "c" } }));
    const onDone = vi.fn();
    const onClose = vi.fn();
    render(<ActionDialog isOpen action={action("Approve Command")} onClose={onClose} onDone={onDone} fixed={{ execution_id: "E1" }} />);
    await userEvent.click(screen.getByTestId("action-submit"));
    const error = await screen.findByTestId("action-error");
    expect(error).toHaveTextContent("Refused: two-person rule");
    expect(error).toHaveTextContent("(audit #7)");
    expect(onDone).not.toHaveBeenCalled();
    expect(onClose).not.toHaveBeenCalled();
  });

  it("reports validation errors from the server field by field", async () => {
    mockFetch(() => ({ status: 422, json: { detail: "reason: Field required; command: Input should be a valid string", outcome: "INVALID", audit_id: 9 } }));
    render(<ActionDialog isOpen action={action("Cancel Command")} onClose={() => undefined} fixed={{ execution_id: "E1" }} initial={{ reason: "x" }} />);
    await userEvent.click(screen.getByTestId("action-submit"));
    expect(await screen.findByTestId("action-error")).toHaveTextContent("Not possible: reason: Field required");
  });

  it("offers the choices of an enum field", () => {
    mockFetch(() => OK);
    render(<ActionDialog isOpen action={action("Open Anomaly")} onClose={() => undefined} fixed={{ spacecraft_id: "S" }} />);
    const severity = screen.getByLabelText(/severity/i) as HTMLSelectElement;
    expect([...severity.options].map((o) => o.value)).toEqual(["", "LOW", "MEDIUM", "HIGH"]);
  });
});

// guard against a schema shape the form cannot handle: every exposed action's fields must map to a known kind
describe("every real action schema", () => {
  it.each(Object.keys(schemas))("%s can be rendered", (name) => {
    mockFetch(() => OK);
    const a = action(name as keyof typeof schemas);
    const { unmount } = render(<ActionDialog isOpen action={a} onClose={() => undefined} />);
    for (const field of Object.keys(a.schema.properties as Record<string, SchemaProperty>)) {
      expect(document.getElementById(`f-${field}`) ?? document.querySelector(`[data-testid="field-${field}"]`), field).not.toBeNull();
    }
    unmount();
  });
});
