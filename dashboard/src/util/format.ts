import type { CommandStatus, Health, Severity } from "../api/types";

export type Intent = "none" | "primary" | "success" | "warning" | "danger";

/** "1 h 05 min", "3 min 20 s", "42 s". Negative or missing values give an em dash. */
export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || !Number.isFinite(seconds) || seconds < 0) return "—";
  const total = Math.round(seconds);
  const h = Math.floor(total / 3600);
  const m = Math.floor((total % 3600) / 60);
  const s = total % 60;
  if (h > 0) return `${h} h ${String(m).padStart(2, "0")} min`;
  if (m > 0) return `${m} min ${String(s).padStart(2, "0")} s`;
  return `${s} s`;
}

/** UTC clock time of an ISO instant, "14:02:07". Times in the dashboard are UTC, like everything the API stores. */
export function formatTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toISOString().slice(11, 19);
}

/** "2026-11-01 14:02:07" in UTC. */
export function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "—" : d.toISOString().slice(0, 19).replace("T", " ");
}

export function formatValue(value: number | null | undefined, unit?: string | null, digits = 2): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const text = Number.isInteger(value) ? String(value) : value.toFixed(digits);
  return unit ? `${text} ${unit}` : text;
}

const HEALTH_INTENT: Record<Health, Intent> = { NOMINAL: "success", WARNING: "warning", CRITICAL: "danger", SAFE_MODE: "danger" };
export const healthIntent = (health: Health): Intent => HEALTH_INTENT[health];

export const severityIntent = (severity: Severity | null | undefined): Intent =>
  severity === "CRITICAL" ? "danger" : severity === "WARNING" ? "warning" : "none";

const STATUS_INTENT: Record<CommandStatus, Intent> = {
  PROPOSED: "primary",
  APPROVED: "primary",
  RELEASED: "primary",
  SENT: "primary",
  ACCEPTED: "primary",
  VERIFIED: "success",
  REJECTED_ONBOARD: "danger",
  FAILED: "danger",
  CANCELLED: "none",
};
export const statusIntent = (status: CommandStatus): Intent => STATUS_INTENT[status];

/** "SAFE_MODE" -> "SAFE MODE". */
export const words = (code: string): string => code.replace(/_/g, " ");
