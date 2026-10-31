# Action runner and audit protocol

**Status:** Proposed. **Applies to:** every write to the operations layer ([../ontology.md](../ontology.md) §3).

## Principle

State changes only through actions. There is one runner, and it does the same steps every time. If a write path exists that bypasses it, the audit trail cannot be trusted, so such a path is a bug.

## Runner steps

1. **Authenticate** the caller to an `Operator` (human, agent or system).
2. **Authorise**: is the operator's role allowed to run this action, on this object?
3. **Validate** parameters against the action's typed schema, then run the action's business rules (lifecycle, two-person rule, contact window, ...).
4. **Apply** all changes in **one database transaction**.
5. **Audit**: append the audit row in the same transaction. If the audit insert fails, the action fails.
6. **Commit**.
7. **Side effects** (send UDP, notify) run after commit, driven from an outbox table, so a crash cannot send a command whose record was rolled back.

Failures at steps 1-3 are returned to the caller with a specific error and are also audited (as `DENIED` or `INVALID`) because refused attempts matter.

## Action definition

Each action is one registered definition:

- `name` (verb first: `Propose Command`);
- parameter schema (Pydantic model; JSON Schema is generated from it for the UI and agent tools);
- permission rule (roles, plus any object-level rule);
- validators and business rules;
- the handler, which receives a transaction and returns the changed objects;
- side effects (outbox messages);
- `agent_callable` and `requires_human_confirmation` flags.

The UI, the API and the agent tools are all generated from this registry. Nothing else defines what an action is.

## Audit record

Append-only table `audit_log`:

| Column | Notes |
| --- | --- |
| `auditId` | primary key |
| `occurredAt` | UTC, database time |
| `operatorId`, `operatorKind` | HUMAN / AGENT / SYSTEM |
| `action` | action name |
| `outcome` | OK / DENIED / INVALID / ERROR |
| `parameters` | JSON, with secrets removed |
| `before`, `after` | JSON of the changed objects |
| `correlationId` | links an agent run, an API request and its audit rows |
| `idempotencyKey` | see below |

Rules:

- The application role has `INSERT` and `SELECT` on `audit_log` only; no `UPDATE` or `DELETE`.
- Never store secrets or tokens in `parameters`.
- Optional hardening later: a hash chain (each row includes the hash of the previous) so tampering is detectable.
- Retention is stated in advance. For this project: keep for the life of the database; export before any reset.

## Idempotency

An action that could be retried by a client (for example after a timeout) takes an `idempotencyKey`. A repeat with the same key and the same parameters returns the first result and changes nothing. The same key with different parameters is an error.

## Time

- Store UTC only.
- Keep three clocks apart and name them: **spacecraft time** (`scTimeMs`, from the packet), **ingest time** (`receivedAt`), **record time** (`occurredAt`/`createdAt`). Lag between the first two is a health signal ([observability-and-operations.md](observability-and-operations.md)).
- Inject a clock into logic that depends on time, so tests do not sleep.

## Database permissions

| Role | Rights |
| --- | --- |
| `app_runner` | write operations tables (used only by the action runner) |
| `app_reader` | read only (API reads, dashboard, agent read tools) |
| `ingest` | append to `telemetry_samples` and update the latest-values on `Spacecraft`; nothing else |
| `migrator` | schema changes, used only by the migration job |

The application connects as `app_reader` by default and uses `app_runner` inside the runner only. No role used by a running service can alter the schema.

## Migrations

- Forward migrations are reviewed pull requests, tested on a database that already contains data.
- The `Definition` tables are rebuilt from the spec; operations tables are never rebuilt automatically.
- A change that removes or renames an operations column needs a documented data plan.

## Required tests

- For each action: allowed role succeeds; each other role is refused; invalid parameters are refused; one audit row per attempt, with the right outcome.
- Atomicity: if the audit insert fails, the object change is rolled back.
- Idempotency: a repeated key does not duplicate.
- A static check (or grep test) that nothing outside the runner module imports the write-capable connection.
- `UPDATE` and `DELETE` on `audit_log` fail for the application roles.

## Enforcement

| Rule | Mechanism | State |
| --- | --- | --- |
| Single write path | database: only `app_runner` can write (`tests/db/test_privileges.py`); Python module boundary and test | Database part enforced; runner not built yet |
| Append-only audit | no UPDATE/DELETE grants **and** a trigger that also stops the owner and superusers; tests as every role | Enforced |
| Role separation | `db/roles.sql`, `db/database.sql` (used by Docker and the tests); exact privilege matrix test | Enforced |
| Idempotency keys, lifecycle consistency, two-person rule, human-only approval | constraints and indexes in `migrations/versions/0001_operations_schema.py`; `tests/db/test_constraints.py` | Enforced in the database; the runner must still enforce them with good error messages |
