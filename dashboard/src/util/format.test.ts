import { describe, expect, it } from "vitest";

import { formatDateTime, formatDuration, formatTime, formatValue, healthIntent, severityIntent, statusIntent, words } from "./format";

describe("formatDuration", () => {
  it.each([[0, "0 s"], [42, "42 s"], [59.6, "1 min 00 s"], [200, "3 min 20 s"], [3600, "1 h 00 min"], [3900, "1 h 05 min"], [86400, "24 h 00 min"]])(
    "%f s -> %s", (seconds, expected) => expect(formatDuration(seconds)).toBe(expected));
  it.each([[null], [undefined], [NaN], [Infinity], [-1]])("%s -> a dash", (value) => expect(formatDuration(value as number)).toBe("—"));
});

describe("times are UTC", () => {
  it("shows the clock time and the date", () => {
    expect(formatTime("2026-11-01T14:02:07.250Z")).toBe("14:02:07");
    expect(formatTime("2026-11-01T14:02:07+02:00")).toBe("12:02:07");          // converted to UTC, not shown as written
    expect(formatDateTime("2026-11-01T14:02:07Z")).toBe("2026-11-01 14:02:07");
  });
  it("shows a dash for nothing or nonsense", () => {
    for (const bad of [null, undefined, "", "yesterday"]) {
      expect(formatTime(bad)).toBe("—");
      expect(formatDateTime(bad)).toBe("—");
    }
  });
});

describe("formatValue", () => {
  it("keeps whole numbers whole, rounds the rest, and adds the unit", () => {
    expect(formatValue(3)).toBe("3");
    expect(formatValue(3.14159)).toBe("3.14");
    expect(formatValue(3.14159, "V", 3)).toBe("3.142 V");
    expect(formatValue(5, "A")).toBe("5 A");
  });
  it("shows a dash for missing and non-finite values", () => {
    for (const bad of [null, undefined, NaN, Infinity]) expect(formatValue(bad as number)).toBe("—");
  });
});

describe("intents", () => {
  it("colours health, severity and command status", () => {
    expect([healthIntent("NOMINAL"), healthIntent("WARNING"), healthIntent("CRITICAL"), healthIntent("SAFE_MODE")]).toEqual(["success", "warning", "danger", "danger"]);
    expect([severityIntent("WARNING"), severityIntent("CRITICAL"), severityIntent(null)]).toEqual(["warning", "danger", "none"]);
    expect([statusIntent("VERIFIED"), statusIntent("REJECTED_ONBOARD"), statusIntent("FAILED"), statusIntent("SENT"), statusIntent("CANCELLED")])
      .toEqual(["success", "danger", "danger", "primary", "none"]);
  });
  it("writes codes as words", () => expect(words("REJECTED_ONBOARD")).toBe("REJECTED ONBOARD"));
});
