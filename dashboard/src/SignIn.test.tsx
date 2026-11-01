import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { getToken, get, setToken } from "./api/client";
import { SessionProvider, useSession } from "./Session";
import { SignIn } from "./SignIn";
import { mockFetch } from "./test/helpers";

const ALICE = { operator_id: "alice", display_name: "Alice", kind: "HUMAN", role: "OPERATOR" };

function Probe() {
  const { status, me } = useSession();
  return <div data-testid="probe">{status}:{me?.display_name ?? "nobody"}</div>;
}
const app = () => render(<SessionProvider><Probe /><SignIn /></SessionProvider>);

afterEach(() => vi.unstubAllGlobals());

describe("signing in", () => {
  it("does not ask the API anything while there is no stored token", async () => {
    const calls = mockFetch(() => ({ status: 500 }));
    app();
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("signed-out:nobody"));
    expect(calls).toHaveLength(0);
  });

  it("keeps a token the API accepts for this tab, and sends it as a bearer token", async () => {
    const calls = mockFetch(() => ({ json: ALICE }));
    app();
    await userEvent.type(screen.getByLabelText(/operator token/i), "  tok-for-alice-0123456789  ");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("signed-in:Alice"));
    expect(calls[0]!.url.pathname).toBe("/api/me");
    expect(calls[0]!.headers.Authorization).toBe("Bearer tok-for-alice-0123456789");        // trimmed
    expect(getToken()).toBe("tok-for-alice-0123456789");
    expect(calls[0]!.headers["X-Correlation-ID"]).toMatch(/^[0-9a-f-]{36}$/);
  });

  it("says so, and keeps nothing, when the API refuses the token", async () => {
    mockFetch(() => ({ status: 401, json: { detail: "authentication required" } }));
    app();
    await userEvent.type(screen.getByLabelText(/operator token/i), "wrong-token-wrong-token");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText("That token is not accepted.")).toBeInTheDocument();
    expect(getToken()).toBeNull();
    expect(screen.getByTestId("probe")).toHaveTextContent("signed-out:nobody");
  });

  it("explains when the API cannot be reached", async () => {
    mockFetch(() => new TypeError("Failed to fetch"));
    app();
    await userEvent.type(screen.getByLabelText(/operator token/i), "some-token-some-token");
    await userEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByText(/cannot reach the API/i)).toBeInTheDocument();
  });

  it("does not offer to sign in with an empty token", () => {
    mockFetch(() => ({ json: ALICE }));
    app();
    expect(screen.getByRole("button", { name: /sign in/i })).toBeDisabled();
  });

  it("restores the session from the tab's stored token", async () => {
    setToken("tok-for-alice-0123456789");
    mockFetch(() => ({ json: ALICE }));
    app();
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("signed-in:Alice"));
  });

  it("signs out, and forgets the token, when the API stops accepting it", async () => {
    setToken("tok-for-alice-0123456789");
    let accepted = true;
    mockFetch(() => (accepted ? { json: ALICE } : { status: 401, json: { detail: "authentication required" } }));
    app();
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("signed-in:Alice"));
    accepted = false;
    await expect(get("/api/spacecraft")).rejects.toThrow("authentication required");
    await waitFor(() => expect(screen.getByTestId("probe")).toHaveTextContent("signed-out:nobody"));
    expect(getToken()).toBeNull();
  });
});
