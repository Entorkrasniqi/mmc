// A form for any action, built from the JSON Schema the API publishes for it (GET /api/actions). Nothing here knows an action's name.
import type { SchemaProperty } from "../api/types";

export type FieldKind = "text" | "enum" | "datetime" | "number" | "integer" | "boolean" | "list" | "object";

/** pydantic writes Optional[X] as anyOf [X, null]: look through that. */
export function resolve(property: SchemaProperty): SchemaProperty {
  if (property.anyOf) {
    const real = property.anyOf.find((p) => p.type !== "null");
    if (real) return { ...property, ...real, anyOf: undefined };
  }
  return property;
}

export function fieldKind(property: SchemaProperty): FieldKind {
  const p = resolve(property);
  if (p.enum) return "enum";
  if (p.type === "string" && p.format === "date-time") return "datetime";
  if (p.type === "number") return "number";
  if (p.type === "integer") return "integer";
  if (p.type === "boolean") return "boolean";
  if (p.type === "array") return "list";
  if (p.type === "object") return "object";
  return "text";
}

export interface Built {
  params: Record<string, unknown>;
  errors: Record<string, string>;
}

/**
 * Turn what the user typed (strings) into the parameters of an action. Empty optional fields are left out so the server's
 * defaults apply; a missing required field is an error here only for the user's convenience: the runner checks it again.
 */
export function buildParams(
  properties: Record<string, SchemaProperty>,
  required: string[],
  values: Record<string, string>,
  fixed: Record<string, unknown> = {},
): Built {
  const params: Record<string, unknown> = { ...fixed };
  const errors: Record<string, string> = {};
  for (const [name, property] of Object.entries(properties)) {
    if (name in fixed) continue;
    const raw = (values[name] ?? "").trim();
    if (raw === "") {
      if (required.includes(name)) errors[name] = "required";
      continue;
    }
    switch (fieldKind(property)) {
      case "number":
      case "integer": {
        const n = Number(raw);
        if (!Number.isFinite(n)) errors[name] = "not a number";
        else if (fieldKind(property) === "integer" && !Number.isInteger(n)) errors[name] = "not a whole number";
        else params[name] = n;
        break;
      }
      case "boolean":
        params[name] = raw === "true";
        break;
      case "list":
        params[name] = raw.split(/[\s,]+/).filter(Boolean);
        break;
      case "object":
        try {
          const parsed: unknown = JSON.parse(raw);
          if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed)) errors[name] = "must be a JSON object";
          else params[name] = parsed;
        } catch {
          errors[name] = "not valid JSON";
        }
        break;
      default:
        params[name] = raw;
    }
  }
  return { params, errors };
}

/** "spacecraft_id" -> "Spacecraft id". */
export const label = (name: string): string => name.charAt(0).toUpperCase() + name.slice(1).replace(/_/g, " ");
