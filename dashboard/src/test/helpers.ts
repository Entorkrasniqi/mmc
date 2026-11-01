import { vi } from "vitest";

export interface Call {
  url: URL;
  method: string;
  headers: Record<string, string>;
  body: unknown;
}

/** Replace fetch with a function that answers from `respond` and remembers every call. */
export function mockFetch(respond: (call: Call) => { status?: number; json?: unknown } | Error) {
  const calls: Call[] = [];
  const fn = vi.fn(async (input: URL | string, init?: RequestInit) => {
    const call: Call = {
      url: new URL(String(input)),
      method: init?.method ?? "GET",
      headers: Object.fromEntries(Object.entries((init?.headers ?? {}) as Record<string, string>)),
      body: init?.body ? JSON.parse(String(init.body)) : undefined,
    };
    calls.push(call);
    const answer = respond(call);
    if (answer instanceof Error) throw answer;
    return new Response(answer.json === undefined ? "" : JSON.stringify(answer.json), { status: answer.status ?? 200 });
  });
  vi.stubGlobal("fetch", fn);
  return calls;
}
