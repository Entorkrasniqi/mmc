// The one place that talks to the API. It sends the caller's token, gives every request a correlation id (the API logs it,
// stores it on audit rows and returns it, so a click can be followed to the telemetry effect), and turns failures into
// ApiError with what the server said.
import type { ActionResponse } from "./types";

const TOKEN_KEY = "minisat.dev-token";

/** DEV ONLY: the token lives in sessionStorage, so it disappears when the tab closes. It is never put in a URL. */
export function getToken(): string | null {
  try {
    return window.sessionStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string): void {
  try {
    window.sessionStorage.setItem(TOKEN_KEY, token);
  } catch {
    /* storage unavailable (private window): the session then lasts until reload */
  }
}

export function clearToken(): void {
  try {
    window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* nothing to clear */
  }
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly outcome?: string,
    readonly auditId?: number,
    readonly correlationId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

let onUnauthorized: () => void = () => undefined;
/** The session registers here so that an expired or wrong token sends the user back to the sign-in screen. */
export function setUnauthorizedHandler(handler: () => void): void {
  onUnauthorized = handler;
}

function newCorrelationId(): string {
  return typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : "00000000-0000-4000-8000-" + Math.random().toString(16).slice(2, 14).padEnd(12, "0");
}

type Query = Record<string, string | number | boolean | undefined | null>;

export interface RequestOptions {
  method?: "GET" | "POST";
  query?: Query;
  body?: unknown;
  idempotencyKey?: string;
  signal?: AbortSignal;
  /** Use this token instead of the stored one (the sign-in screen checks a token before keeping it). */
  token?: string;
}

function describe(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => `${(d.loc ?? []).slice(1).join(".") || "request"}: ${d.msg ?? "invalid"}`)
      .join("; ");
  }
  return "the request failed";
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = new URL(path, window.location.origin);
  for (const [key, value] of Object.entries(options.query ?? {})) {
    if (value !== undefined && value !== null && value !== "") url.searchParams.set(key, String(value));
  }
  const token = options.token ?? getToken();
  const headers: Record<string, string> = { Accept: "application/json", "X-Correlation-ID": newCorrelationId() };
  if (token) headers.Authorization = `Bearer ${token}`;
  if (options.body !== undefined) headers["Content-Type"] = "application/json";
  if (options.idempotencyKey) headers["Idempotency-Key"] = options.idempotencyKey;

  let response: Response;
  try {
    response = await fetch(url, {
      method: options.method ?? (options.body !== undefined ? "POST" : "GET"),
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
      signal: options.signal,
    });
  } catch (error) {
    if ((error as Error).name === "AbortError") throw error;
    throw new ApiError("cannot reach the API: is 'minisat api' running?", 0);
  }

  const text = await response.text();
  let data: unknown;
  try {
    data = text ? JSON.parse(text) : undefined;
  } catch {
    data = undefined;
  }
  if (!response.ok) {
    if (response.status === 401 && options.token === undefined) onUnauthorized();
    const body = (data ?? {}) as { detail?: unknown; outcome?: string; audit_id?: number; correlation_id?: string };
    throw new ApiError(
      describe(body.detail ?? response.statusText),
      response.status,
      body.outcome,
      body.audit_id,
      body.correlation_id ?? response.headers.get("X-Correlation-ID") ?? undefined,
    );
  }
  return data as T;
}

export const get = <T,>(path: string, query?: Query, signal?: AbortSignal): Promise<T> =>
  request<T>(path, { query, signal });

export const post = <T,>(path: string, body: unknown, options: Omit<RequestOptions, "body" | "method"> = {}): Promise<T> =>
  request<T>(path, { ...options, method: "POST", body });

/** Run an action as the signed-in operator. A fresh idempotency key per attempt makes a double click harmless. */
export function runAction(slug: string, params: Record<string, unknown>, idempotencyKey?: string): Promise<ActionResponse> {
  return post<ActionResponse>(`/api/actions/${slug}`, params, { idempotencyKey: idempotencyKey ?? newCorrelationId() });
}
