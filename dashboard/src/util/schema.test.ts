import { describe, expect, it } from "vitest";

import type { SchemaProperty } from "../api/types";
import schemas from "../test/action-schemas.json";
import { buildParams, fieldKind, label, resolve } from "./schema";

type Schema = { properties: Record<string, SchemaProperty>; required?: string[] };
// the real JSON Schemas of the actions, dumped from the Python registry (tests/test_dashboard_fixtures.py keeps them current)
const schema = (action: keyof typeof schemas) => (schemas[action] as unknown as { schema: Schema }).schema;

describe("fieldKind, on what pydantic really writes", () => {
  const kind = (action: keyof typeof schemas, field: string) => fieldKind(schema(action).properties[field]!);

  it.each([
    ["Plan Contact", "start_at", "datetime"], ["Plan Contact", "station_id", "text"], ["Plan Contact", "max_elevation_deg", "number"],
    ["Open Anomaly", "severity", "enum"], ["Open Anomaly", "alarm_ids", "list"], ["Propose Command", "arguments", "object"],
    ["Update Anomaly", "root_cause", "text"], ["Approve Command", "execution_id", "text"], ["Release Command", "override_reason", "text"],
  ] as const)("%s.%s is %s", (action, field, expected) => expect(kind(action, field)).toBe(expected));

  it("looks through Optional[...] (anyOf with null)", () => {
    expect(resolve({ anyOf: [{ type: "string" }, { type: "null" }] }).type).toBe("string");
    expect(fieldKind({ anyOf: [{ type: "number" }, { type: "null" }] })).toBe("number");
  });
});

describe("buildParams", () => {
  const { properties, required } = schema("Plan Contact");

  it("coerces numbers, keeps text, and takes the fixed parameters as they are", () => {
    const built = buildParams(properties, required ?? [], { station_id: "HEL", start_at: "2026-11-01T12:00:00.000Z", end_at: "2026-11-01T12:10:00.000Z", max_elevation_deg: "62.5" }, { spacecraft_id: "MINISAT-1" });
    expect(built.errors).toEqual({});
    expect(built.params).toEqual({ spacecraft_id: "MINISAT-1", station_id: "HEL", start_at: "2026-11-01T12:00:00.000Z", end_at: "2026-11-01T12:10:00.000Z", max_elevation_deg: 62.5 });
  });

  it("leaves out empty optional fields so the server's defaults apply", () => {
    const built = buildParams(properties, required ?? [], { station_id: "HEL", start_at: "a", end_at: "b", max_elevation_deg: "  " }, { spacecraft_id: "X" });
    expect("max_elevation_deg" in built.params).toBe(false);
  });

  it("reports a missing required field and a value that is not a number", () => {
    const built = buildParams(properties, required ?? [], { station_id: "", start_at: "a", end_at: "b", max_elevation_deg: "high" }, { spacecraft_id: "X" });
    expect(built.errors).toEqual({ station_id: "required", max_elevation_deg: "not a number" });
  });

  it("splits a list on commas and spaces, and parses an object as JSON", () => {
    const open = schema("Open Anomaly");
    const list = buildParams(open.properties, open.required ?? [], { title: "t", severity: "HIGH", alarm_ids: "a1, a2  a3,,a4" }, { spacecraft_id: "X" });
    expect(list.params.alarm_ids).toEqual(["a1", "a2", "a3", "a4"]);
    const propose = schema("Propose Command");
    const ok = buildParams(propose.properties, propose.required ?? [], { spacecraft_id: "X", command: "SetMode", reason: "r", arguments: '{"mode": "PAYLOAD"}' });
    expect(ok.params.arguments).toEqual({ mode: "PAYLOAD" });
    for (const [text, error] of [["{oops", "not valid JSON"], ["[1]", "must be a JSON object"], ["5", "must be a JSON object"]] as const) {
      expect(buildParams(propose.properties, propose.required ?? [], { spacecraft_id: "X", command: "c", reason: "r", arguments: text }).errors).toEqual({ arguments: error });
    }
  });

  it("does not touch a hidden field even if it has a value", () => {
    const anomaly = schema("Update Anomaly");
    const built = buildParams(anomaly.properties, anomaly.required ?? [], { root_cause: "typed" }, { anomaly_id: "A", status: "INVESTIGATING", root_cause: undefined });
    expect(built.params.root_cause).toBeUndefined();
  });
});

describe("label", () => {
  it("turns a parameter name into a readable label", () => {
    expect(label("responds_to_alarm_id")).toBe("Responds to alarm id");
    expect(label("note")).toBe("Note");
  });
});
