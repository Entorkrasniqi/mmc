# ADR 0002: PostgreSQL as the system store
- Status: Accepted
- Date: 2026-10-31

## Context
The ontology's objects, links and actions are relational, and the design requires database-enforced permissions (only the action runner may write) and atomic action-plus-audit transactions. Telemetry is about one sample per parameter per second, on the order of a million rows a day.

## Options considered
1. SQLite: zero setup, but no roles or row-level security, so the write-path rule could only be enforced in application code.
2. PostgreSQL: roles, grants, row-level security, enums, JSONB, transactions, `LISTEN/NOTIFY`.
3. PostgreSQL plus the TimescaleDB extension for telemetry.
4. A graph database: links here are shallow and fixed, with no deep traversal.
5. A dedicated time-series database: more than this volume needs, and a second system to run.

## Decision
Option 2. Telemetry goes in an indexed append-only table. TimescaleDB (option 3) can be added later without changing the model if volume or query time demands it. This was a design judgement; no benchmark has been run.

## Consequences
- The stack needs a PostgreSQL instance (Docker Compose), one more prerequisite than pure Python.
- Tests that touch the database run on real PostgreSQL, not a mock.
- Role separation (`app_runner`, `app_reader`, `ingest`, `migrator`) is defined in the database init, see [../action-runner-and-audit.md](../action-runner-and-audit.md).
- Revisit if telemetry volume grows well beyond the current estimate.
