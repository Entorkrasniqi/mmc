// Shapes of the API's answers (src/minisat/api). Written by hand and kept to what the dashboard reads; the API's own
// OpenAPI document (/openapi.json) is the full description.

export type Role = "VIEWER" | "OPERATOR" | "SUPERVISOR" | "AGENT";
export type Severity = "WARNING" | "CRITICAL";
export type Health = "NOMINAL" | "WARNING" | "CRITICAL" | "SAFE_MODE";
export type CommandStatus =
  | "PROPOSED"
  | "APPROVED"
  | "RELEASED"
  | "SENT"
  | "ACCEPTED"
  | "REJECTED_ONBOARD"
  | "VERIFIED"
  | "FAILED"
  | "CANCELLED";
export type AlarmState = "ACTIVE" | "ACKNOWLEDGED" | "CLEARED";
export type AnomalyStatus = "OPEN" | "INVESTIGATING" | "RESOLVED";

export type Bounds = [number | null, number | null];

export interface Me {
  operator_id: string;
  display_name: string;
  kind: string;
  role: Role;
}

export interface Operator {
  operator_id: string;
  display_name: string;
  kind?: string;
  role?: Role;
}

export interface ParameterState {
  name: string;
  value: number;
  unit: string | null;
  label: string | null;
  severity: Severity | null;
  warning: Bounds | null;
  critical: Bounds | null;
}

export interface Spacecraft {
  spacecraft_id: string;
  name: string;
  health_status: Health;
  mode: string | null;
  last_contact_at: string | null;
  telemetry_age_s: number | null;
  telemetry_stale: boolean;
  values: Record<string, number>;
  parameters: ParameterState[];
}

export interface ParameterDefinition {
  name: string;
  unit: string | null;
  description: string;
  enum_labels: { label: string; value: number }[] | null;
  warning: Bounds | null;
  critical: Bounds | null;
}

export interface CommandArgumentDefinition {
  name: string;
  data_type: string;
  description: string;
  unit: string | null;
  enum_labels: { label: string; value: number }[] | null;
  range_min: number | null;
  range_max: number | null;
}

export interface CommandDefinition {
  command_id: number;
  name: string;
  description: string;
  significance: "NORMAL" | "VITAL";
  arguments: CommandArgumentDefinition[];
}

export interface Definitions {
  mission_name: string;
  parameters: ParameterDefinition[];
  commands: CommandDefinition[];
}

export interface SeriesPoint {
  t_ms: number;
  t: string;
  v: number | null;
  min?: number | null;
  max?: number | null;
  n?: number;
}

export interface Series {
  spacecraft_id: string;
  parameter: ParameterDefinition;
  from: string | null;
  to: string | null;
  resolution: "raw" | "bucketed";
  bucket_ms: number | null;
  samples: number;
  points: SeriesPoint[];
}

export interface Preflight {
  known: boolean;
  accepted: boolean | null;
  reason: string | null;
  state_age_s: number | null;
  stale: boolean;
}

export interface ContactRef {
  contact_id: string;
  station_id: string;
  start_at: string;
  end_at: string;
}

export interface CommandExecution {
  execution_id: string;
  spacecraft_id: string;
  command_id: number;
  command_name: string;
  vital: boolean;
  arguments: Record<string, number>;
  arguments_text: Record<string, string | null>;
  reason: string;
  status: CommandStatus;
  rejection_reason: string | null;
  proposed_by: string;
  approved_by: string | null;
  approval_note: string | null;
  cancelled_by: string | null;
  cancel_reason: string | null;
  override_reason: string | null;
  responds_to_alarm_id: string | null;
  raw_bytes_hex: string | null;
  proposed_at: string;
  expires_at: string;
  approved_at: string | null;
  released_at: string | null;
  sent_at: string | null;
  verified_at: string | null;
  preflight: Partial<Preflight>;
  state_snapshot: Record<string, number>;
  expected_effect: { parameter: string; op: string; value?: number }[];
  contact: ContactRef | null;
}

export interface Alarm {
  alarm_id: string;
  spacecraft_id: string;
  parameter_name: string;
  severity: Severity;
  trigger_value: number;
  limit_violated: string;
  state: AlarmState;
  raised_at: string;
  cleared_at: string | null;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  acknowledge_note: string | null;
  anomaly_id: string | null;
  responding_commands?: { execution_id: string; command_name: string; status: CommandStatus; proposed_by: string }[];
}

export interface SpacecraftEvent {
  event_id: string;
  spacecraft_id: string;
  event_type: string;
  occurred_at: string;
  details: Record<string, unknown>;
  caused_by_execution_id: string | null;
  anomaly_id: string | null;
}

export interface Anomaly {
  anomaly_id: string;
  spacecraft_id: string;
  title: string;
  severity: "LOW" | "MEDIUM" | "HIGH";
  status: AnomalyStatus;
  detected_at: string;
  resolved_at: string | null;
  root_cause: string | null;
  resolution_note: string | null;
  opened_by: string;
  alarms?: Alarm[];
  events?: SpacecraftEvent[];
  commands?: CommandExecution[];
}

export interface ContactWindow {
  contact_id: string;
  spacecraft_id: string;
  station_id: string;
  start_at: string;
  end_at: string;
  max_elevation_deg: number | null;
  status: "PLANNED" | "ACTIVE" | "COMPLETED" | "MISSED";
  packet_loss_events: number;
  packets_lost_observed: number;
}

export interface GroundStation {
  station_id: string;
  name: string;
  latitude_deg: number;
  longitude_deg: number;
  min_elevation_deg: number;
}

export interface TimeToSafe {
  known: boolean;
  reaches_safe: boolean;
  seconds: number | null;
  horizon_s: number;
  min_soc_pct: number | null;
  command_accepted: boolean | null;
  phase_known: boolean;
  assumptions: string[];
}

export interface TimeToSafeAnswer {
  spacecraft_id: string;
  command: string | null;
  arguments: Record<string, number> | null;
  preflight: Preflight | null;
  time_to_safe: TimeToSafe;
}

/** A property of an action's JSON Schema (pydantic's output), as far as the generic form needs it. */
export interface SchemaProperty {
  type?: string;
  format?: string;
  title?: string;
  description?: string;
  enum?: string[];
  items?: SchemaProperty;
  anyOf?: SchemaProperty[];
  default?: unknown;
  additionalProperties?: unknown;
}

export interface ActionInfo {
  name: string;
  slug: string;
  path: string;
  description: string;
  roles: Role[];
  agent_callable: boolean;
  requires_human_confirmation: boolean;
  allowed_for_me: boolean;
  schema: { properties: Record<string, SchemaProperty>; required?: string[] };
}

export interface ActionResponse {
  action: string;
  audit_id: number;
  result: Record<string, unknown>;
  warnings: string[];
  replayed: boolean;
  correlation_id: string;
}

export interface Page<T> {
  items: T[];
  limit: number;
  offset: number;
}
