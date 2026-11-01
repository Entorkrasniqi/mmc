# Observability and operations protocol

**Status:** Proposed. Targets are initial values, to be replaced with measured ones.

## Principle

An operator or developer must be able to answer "what is it doing, is it healthy, and why did that happen?" from the system's own outputs, without attaching a debugger.

## Logging

- Structured JSON logs, one event per line, UTC timestamps.
- Every log line in a request or run carries a `correlationId`; the same ID is stored on audit rows, agent traces and command executions, so one command can be followed from click to telemetry effect.
- Levels: `ERROR` needs attention, `WARN` is unusual but handled, `INFO` is a business event (action run, alarm raised), `DEBUG` is off by default.
- Never log secrets, tokens, or full model prompts that may contain them.
- The simulator's existing human-readable lines (`ACCEPT ...`, `REJECT ... reason`) stay; the ingestion layer also records them as `SpacecraftEvent`s.

## Metrics

| Metric | Why |
| --- | --- |
| telemetry packets received per APID | is data flowing? |
| packets lost (from sequence gaps) | link quality (roadmap M3) |
| ingest lag = `receivedAt` - spacecraft time | clock or pipeline problems |
| decode errors / rejected datagrams | bad or hostile input |
| action count and latency by name and outcome | runner health |
| command lifecycle counts by state, time-to-VERIFIED | commanding health |
| alarms active by severity | operational picture |
| outbox backlog and age | stuck side effects |
| agent runs, proposals, approvals, rejections | agent value and risk |
| database connections, slow queries | capacity |

Expose through a standard endpoint (for example Prometheus format) and graph with whatever is available; the tool is secondary to having the numbers.

## Health

- `/health/live`: the process is up.
- `/health/ready`: the database is reachable, migrations are current, and the latest telemetry is not older than 3x the Housekeeping period (or the stack is configured as having no live source).
- Used by Docker health checks and, later, Kubernetes probes.

## Initial targets

| Item | Target |
| --- | --- |
| Telemetry visible in the UI after arrival | under 2 s |
| Action latency (p95, local) | under 500 ms |
| Command SENT -> ACCEPTED/REJECTED detected | within 5 s at real-time speed |
| Alarm raised after a limit is crossed | within one telemetry period |

These are aims for a local demo. Measure, then correct them.

## Runbook

| Symptom | First checks | Action |
| --- | --- | --- |
| No telemetry in the UI | ingestion running? port 10015 free (only one listener)? simulator printing "telemetry ->"? | restart ingestion; if Yamcs is also running, stop one |
| Telemetry "stale" warning | ingest lag metric; simulator speed-up set? | align speed, restart simulator |
| Commands stay SENT, never ACCEPTED | simulator log for ACCEPT/REJECT; TC port; contact window state | fix link; mark FAILED; do not auto-retry |
| Many rejected commands | rejection reasons; battery state | investigate before sending more |
| Database unavailable | container health, disk, connections | restore service; actions fail closed (no writes), reads may degrade |
| Outbox backlog grows | worker logs | restart worker; side effects are idempotent by key |
| Agent misbehaving | agent trace, proposals, kill switch | disable the Agent role's grants, keep logs, add an eval scenario |
| Suspected audit tampering | compare against backups, hash chain if enabled | treat as an incident |

## Incidents

- Handle problems in a blameless way: the aim is to find which control was missing.
- Record each real incident in `protocols/incidents/YYYY-MM-DD-title.md`: timeline, impact, cause, what detected it, what fixed it, follow-ups with owners. Turn follow-ups into tests, evals or protocol changes.
- An agent incident always produces a new eval scenario.

## Data

- Telemetry is retained as long as disk allows; thin to 1-minute aggregates after a chosen period only when needed. Keep the operations records and audit log indefinitely.
- No personal data beyond operator display names. If real users are added later, review privacy handling first.
- Back up PostgreSQL on a schedule and test a restore at least once; a backup never restored is a guess.

## Enforcement

| Rule | Mechanism | State |
| --- | --- | --- |
| Correlation IDs on requests, responses, log lines and audit rows | `src/minisat/api/` (`app.py`, `logs.py`); `tests/api/test_api_ops.py` | Enforced for the API. The ground station's own log lines are plain text and carry no id |
| Structured JSON logs, no secrets in them | `JsonFormatter`; a test that a token never reaches a log line | Enforced for the API |
| `/health/live`, `/health/ready` (database as reader and runner, migration revision, telemetry no older than 3 periods) | `health.py`; `tests/api/test_api_ops.py` (including: nothing leaks when the database is down) | Enforced |
| Metrics: actions by name and outcome, requests by route template, alarms by severity, commands by state, time to VERIFIED, outbox backlog and age, telemetry age and ingest lag, packets lost, database up | `metrics.py` (read from the database at scrape time); `tests/api/test_api_ops.py` | Enforced. **Missing:** packets per APID and decode errors (the ground station is another process), agent metrics (no agent yet), database connection and slow-query metrics |
| Restore test | documented procedure + a one-off run | Not yet |
