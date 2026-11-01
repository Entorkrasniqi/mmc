import { Tag } from "@blueprintjs/core";

import type { CommandStatus, Health, Severity } from "../api/types";
import { healthIntent, severityIntent, statusIntent, words } from "../util/format";

export function HealthTag({ health }: { health: Health }) {
  return (
    <Tag intent={healthIntent(health)} large data-testid="health-tag">
      {words(health)}
    </Tag>
  );
}

export function SeverityTag({ severity }: { severity: Severity | "LOW" | "MEDIUM" | "HIGH" }) {
  const intent = severity === "HIGH" ? "danger" : severity === "MEDIUM" ? "warning" : severity === "LOW" ? "primary" : severityIntent(severity);
  return <Tag intent={intent}>{severity}</Tag>;
}

export function StatusTag({ status }: { status: CommandStatus }) {
  return (
    <Tag intent={statusIntent(status)} minimal={status === "CANCELLED"} data-testid="status-tag">
      {words(status)}
    </Tag>
  );
}
