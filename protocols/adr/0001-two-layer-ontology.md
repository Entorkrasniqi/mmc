# ADR 0001: Two-layer ontology: generated definitions, database operations
- Status: Accepted
- Date: 2026-10-31

## Context
`spec/minisat.yaml` already defines every parameter, packet, command and alarm limit, and the XTCE database is generated from it. A Palantir-style ontology needs both those definitions and the live objects operators work with (command executions, alarms, anomalies). Storing the definitions a second time in a database would create two sources of truth, the problem the YAML was introduced to remove.

## Options considered
1. Put everything in the database and generate the YAML/XTCE from it.
2. Keep definitions in the YAML and mirror them into the database by hand.
3. Keep definitions in the YAML, load them into read-only definition objects at startup, and store only operations data in the database.

## Decision
Option 3. `TelemetryParameter`, `TelemetryPacketType` and `CommandDefinition` are generated from the spec and read-only at runtime. Changes to them are pull requests followed by `minisat gen-xtce`. The database holds the operations layer only.

## Consequences
- One source of truth for the interface; the existing freshness check stays meaningful.
- Alarm limits cannot be edited in the UI. That is deliberate: it keeps the ground and the XTCE database in step.
- The operations layer references definitions by stable names (`parameterName`, `commandId`); renaming one is a breaking change that needs a migration plan.
- Telemetry samples are a time series, not individual objects.
