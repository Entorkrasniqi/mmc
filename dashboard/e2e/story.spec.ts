// PLAN.md phase 5, "done when": start the stack, watch the alarms fire, and recover the spacecraft with an approved command, in the
// browser. The stack (tools/e2e_stack.py) starts a satellite with a battery at 14.9 %, just under the 15 % at which it protects
// itself, so it goes to SAFE mode within a second of the first packet. Nothing is mocked: PostgreSQL, the ground station, the API
// and the simulator are the real ones, and every number on screen comes from the satellite's own telemetry.
//
// The tests build on each other (one story, in order), each as the person who would do that step.
import { expect, test, type Browser, type BrowserContext, type Page } from "@playwright/test";

import { NAMES, openTab, signedIn, token, utc } from "./stack";

test.describe.configure({ mode: "serial" });

let alice: Page, bob: Page, sam: Page, tina: Page;
const everyone: BrowserContext[] = [];

async function as(browser: Browser, operator: string, hash = ""): Promise<Page> {
  const page = await signedIn(browser, operator, hash);
  everyone.push(page.context());
  return page;
}

test.afterAll(async () => {
  for (const context of everyone) await context.close();
});

test("signing in needs a token the API accepts, survives a reload, and signing out forgets it", async ({ browser }) => {
  const context = await browser.newContext();
  everyone.push(context);
  const page = await context.newPage();
  await page.goto("/");
  await expect(page.getByText("Development sign-in")).toBeVisible();
  await expect(page.getByRole("button", { name: "Sign in" })).toBeDisabled();

  await page.getByLabel("Operator token").fill("not-a-real-token-not-a-real-token");
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByText("That token is not accepted.")).toBeVisible();

  await page.getByLabel("Operator token").fill(token("vera"));
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page.getByTestId("who")).toContainText("Vera");
  await expect(page.getByTestId("who")).toContainText("viewer");

  await page.reload();                                                          // the token lives in this tab's sessionStorage
  await expect(page.getByTestId("who")).toContainText("Vera");
  expect(await page.evaluate(() => window.localStorage.getItem("minisat.dev-token"))).toBeNull();      // never in localStorage

  await page.getByTestId("sign-out").click();
  await expect(page.getByText("Development sign-in")).toBeVisible();
  await page.reload();
  await expect(page.getByText("Development sign-in")).toBeVisible();
});

test("the overview shows live telemetry, the limits on the charts and a time-to-safe estimate", async ({ browser }) => {
  alice = await as(browser, "alice");
  await expect(alice.getByTestId("who")).toContainText(`${NAMES.alice} · operator`);
  // the satellite protected itself within a second of the first packet
  await expect(alice.getByTestId("health-tag")).toHaveText(/SAFE MODE|CRITICAL|WARNING/);
  await expect(alice.getByTestId("tile-battery_soc_pct")).toContainText("%");
  await expect(alice.getByTestId("tile-uptime_s")).toBeVisible();
  await expect(alice.getByTestId("contact-age")).toContainText("last telemetry");
  await expect(alice.getByTestId("stale-callout")).toHaveCount(0);

  for (const chart of ["chart-soc", "chart-voltage", "chart-temperature", "chart-currents"]) {
    await expect(alice.getByTestId(chart).locator(".trace-main path.recharts-line-curve").first()).toBeVisible({ timeout: 40_000 });
  }
  await expect(alice.getByTestId("chart-soc").locator(".recharts-reference-area").first()).toBeVisible();    // the alarm limits

  await expect(alice.getByTestId("estimate-verdict")).toBeVisible();
  await alice.getByTestId("estimate-scenario").selectOption("SetMode:PAYLOAD");
  await expect(alice.getByTestId("estimate-preflight")).toContainText(/would (accept|REJECT) SetMode PAYLOAD/);
  await expect(alice.getByTestId("events-table")).toContainText("FDIR");
});

test("an unplanned SAFE mode opened an anomaly, with the alarm and the FDIR event that explain it", async () => {
  await openTab(alice, "anomalies");
  const open = alice.getByTestId("column-OPEN");
  await expect(open.getByTestId("anomaly-card").filter({ hasText: "Unplanned SAFE mode" })).toBeVisible();
  await open.getByTestId("anomaly-card").filter({ hasText: "Unplanned SAFE mode" }).click();
  const detail = alice.getByTestId("anomaly-detail");
  await expect(detail).toContainText("HIGH");
  await expect(detail).toContainText("battery soc pct");
  await expect(detail).toContainText("FDIR");
  await alice.keyboard.press("Escape");
});

test("an alarm for the low battery is raised by the ground station, and a person acknowledges it", async () => {
  await openTab(alice, "alarms");
  const row = alice.getByTestId("alarm-battery_soc_pct");
  await expect(row).toBeVisible();
  await expect(row).toContainText(/CRITICAL|WARNING/);
  await expect(row).toContainText("ACTIVE");
  await row.getByTestId("acknowledge").click();
  await alice.getByTestId("field-note").fill("seen: battery is recovering in sunlight");
  await alice.getByTestId("action-submit").click();
  await expect(alice.getByTestId("action-dialog")).toHaveCount(0);
  await expect(row).toContainText("ACKNOWLEDGED");
  await expect(row).toContainText("by Alice");
});

test("a viewer sees everything and is offered nothing to change", async ({ browser }) => {
  const vera = await as(browser, "vera", "#/commands");
  await expect(vera.getByTestId("propose")).toBeDisabled();
  await openTab(vera, "alarms");
  await expect(vera.getByTestId("alarm-battery_soc_pct")).toBeVisible();
  await expect(vera.getByTestId("acknowledge").first()).toBeDisabled();
});

test("a vital command needs a second person, and the dashboard says so", async ({ browser }) => {
  sam = await as(browser, "sam", "#/commands");
  await sam.getByTestId("propose").click();
  await sam.getByTestId("command-select").click();
  await sam.getByRole("option", { name: /Reboot/ }).click();
  await expect(sam.getByText("A vital command: a supervisor other than you must approve it.")).toBeVisible();
  await sam.getByTestId("reason").fill("clear a suspected fault");
  await expect(sam.getByTestId("estimate-preflight")).toContainText("would accept Reboot");
  await sam.getByTestId("propose-submit").click();
  await expect(sam.getByTestId("propose-dialog")).toHaveCount(0);

  const detail = sam.getByTestId("command-detail");
  await expect(detail).toContainText("Reboot");
  await expect(detail.getByTestId("status-tag")).toHaveText("PROPOSED");
  await expect(detail.getByTestId("bytes")).toHaveText("100ac00000010004");        // header, length 1, command id 4
  await expect(sam.getByTestId("btn-approve")).toBeDisabled();                  // two-person rule: sam proposed it

  tina = await as(browser, "tina", "#/commands");
  await tina.getByTestId("command-Reboot").click();
  await expect(tina.getByTestId("btn-approve")).toBeEnabled();
  await tina.getByTestId("btn-approve").click();
  await tina.getByTestId("field-note").fill("agreed");
  await tina.getByTestId("action-submit").click();
  await expect(tina.getByTestId("command-detail").getByTestId("status-tag")).toHaveText("APPROVED");
  await expect(tina.getByTestId("evidence")).toContainText("Tina");

  // nobody wants a reboot right now: the proposer takes it back
  await expect(sam.getByTestId("btn-cancel")).toBeEnabled();
  await sam.getByTestId("btn-cancel").click();
  await sam.getByTestId("field-reason").fill("not needed after all");
  await sam.getByTestId("action-submit").click();
  await expect(sam.getByTestId("command-detail").getByTestId("status-tag")).toHaveText("CANCELLED");
});

test("a supervisor plans a contact window, and commands can be released inside it", async () => {
  await expect(sam.getByTestId("contact-bar")).toContainText("No contact window now");
  await sam.getByTestId("plan-contact").click();
  const now = Date.now();
  await sam.locator("#f-start_at").fill(utc(new Date(now - 10 * 60_000)));
  await sam.locator("#f-end_at").fill(utc(new Date(now + 3 * 3600_000)));
  await sam.locator("#f-end_at").blur();
  await sam.getByTestId("action-submit").click();
  await expect(sam.getByTestId("action-dialog")).toHaveCount(0);
  await expect(sam.getByTestId("contact-bar")).toContainText("In contact with HEL");
});

test("the spacecraft is recovered with an approved command, verified by its own telemetry", async ({ browser }) => {
  // the mode before: SAFE
  await openTab(alice, "overview");
  await expect(alice.getByTestId("mode-tag")).toContainText(/SAFE/);

  // alice proposes
  await openTab(alice, "commands");
  await alice.getByTestId("propose").click();
  await alice.getByTestId("command-select").click();
  await alice.getByRole("option", { name: /SetMode/ }).click();
  await alice.getByTestId("arg-mode").selectOption("NOMINAL");
  await alice.getByTestId("reason").fill("battery is back above 15 %: leave SAFE mode");
  await expect(alice.getByTestId("estimate-preflight")).toContainText("would accept SetMode");
  await alice.getByTestId("propose-submit").click();
  await expect(alice.getByTestId("propose-dialog")).toHaveCount(0);
  const mine = alice.getByTestId("command-detail");
  await expect(mine.getByTestId("detail-title")).toHaveText("SetMode mode=NOMINAL");
  await expect(mine.getByTestId("bytes")).toHaveText("100ac0000002000201");       // header, length 2, command id 2, mode NOMINAL = 1
  await expect(mine.getByTestId("evidence")).toContainText("mode = NOMINAL");      // what telemetry must show afterwards
  await expect(mine.getByTestId("evidence")).toContainText("mode SAFE");           // the state it was proposed in

  // bob reads the evidence and approves; he is not the proposer
  const bobPage = await as(browser, "bob", "#/commands");
  bob = bobPage;
  await bob.getByTestId("command-SetMode").click();
  await expect(bob.getByTestId("evidence")).toContainText("100ac0000002000201");
  await bob.getByTestId("btn-approve").click();
  await bob.getByTestId("action-submit").click();
  await expect(bob.getByTestId("command-detail").getByTestId("status-tag")).toHaveText("APPROVED");
  await expect(bob.getByTestId("contact-bar")).toContainText("In contact with HEL");

  // released to the link: SENT, ACCEPTED and VERIFIED come from the satellite's counters and mode, not from a click
  await bob.getByTestId("btn-release").click();
  await bob.getByTestId("action-submit").click();
  await expect(bob.getByTestId("command-detail").getByTestId("status-tag")).toHaveText("VERIFIED", { timeout: 60_000 });
  await expect(bob.getByTestId("steps").locator(".step.done")).toHaveCount(6);
  await expect(bob.getByText("Took effect")).toBeVisible();
  await expect(bob.getByTestId("evidence")).toContainText("HEL");

  // and the spacecraft says so
  await openTab(alice, "overview");
  await expect(alice.getByTestId("mode-tag")).toContainText("NOMINAL", { timeout: 30_000 });
  await expect(alice.getByTestId("health-tag")).not.toHaveText("SAFE MODE");
});

test("the anomaly is investigated and resolved with a root cause, and stays on record", async () => {
  await openTab(alice, "anomalies");
  await alice.getByTestId("column-OPEN").getByTestId("anomaly-card").filter({ hasText: "Unplanned SAFE mode" }).click();
  await alice.getByTestId("anomaly-next").click();                                // start investigating
  await alice.getByTestId("action-submit").click();
  await expect(alice.getByTestId("anomaly-detail")).toContainText("INVESTIGATING");
  await alice.getByTestId("anomaly-next").click();                                // resolve
  await alice.getByTestId("action-submit").click();                              // without a root cause: refused before it is sent
  await expect(alice.getByText("required", { exact: true })).toBeVisible();
  await alice.getByTestId("field-root_cause").fill("battery started below the 15 % FDIR threshold");
  await alice.getByTestId("field-resolution_note").fill("left SAFE mode with SetMode NOMINAL once the battery recovered");
  await alice.getByTestId("action-submit").click();
  await expect(alice.getByTestId("anomaly-detail")).toContainText("Root cause:");
  await alice.keyboard.press("Escape");
  await expect(alice.getByTestId("column-RESOLVED").getByTestId("anomaly-card")).toHaveCount(1);
  await expect(alice.getByTestId("column-OPEN").getByTestId("anomaly-card")).toHaveCount(0);
});

test("the ground track shows where the satellite has been, and the ground station", async () => {
  await openTab(alice, "track");
  const map = alice.getByTestId("ground-track");
  await expect(map.getByTestId("station-HEL")).toBeVisible();
  await expect(map.getByTestId("spacecraft-marker")).toBeVisible({ timeout: 40_000 });
  await expect(map.getByTestId("track-segment").first()).toBeAttached();
  await expect(map.getByTestId("position")).toContainText("lat");
  await expect(map.getByTestId("position")).toContainText("km");
});
