import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

import type { Browser, Page } from "@playwright/test";

const here = dirname(fileURLToPath(import.meta.url));

/** The DEV-ONLY tokens tools/e2e_stack.py made for this run (random every time). */
export function token(operator: string): string {
  const tokens = JSON.parse(readFileSync(join(here, "..", "..", ".e2e", "tokens.json"), "utf8")) as Record<string, string>;
  const value = tokens[operator];
  if (!value) throw new Error(`no token for ${operator}`);
  return value;
}

export const NAMES: Record<string, string> = { alice: "Alice", bob: "Bob", sam: "Sam", tina: "Tina", vera: "Vera", helper: "Helper (AI agent)" };

/** A page signed in as one operator, in its own browser context (so several people can be signed in at once). */
export async function signedIn(browser: Browser, operator: string, hash = ""): Promise<Page> {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const page = await context.newPage();
  await page.goto("/" + hash);
  await page.getByLabel("Operator token").fill(token(operator));
  await page.getByRole("button", { name: "Sign in" }).click();
  await page.getByTestId("who").waitFor();
  return page;
}

export async function openTab(page: Page, id: "overview" | "alarms" | "commands" | "anomalies" | "track"): Promise<void> {
  await page.getByTestId(`tab-${id}`).click();
}

/** A UTC time as the contact dialog wants it, "2026-11-01 12:30". */
export const utc = (d: Date): string => d.toISOString().slice(0, 16).replace("T", " ");
