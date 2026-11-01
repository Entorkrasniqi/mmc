# Plan

How the project goes from "simulator and packet tools" to "ontology-based mission control app". Design is in [ontology.md](ontology.md); the rules each phase must follow are in [protocols/](protocols/README.md); the reasons for the big choices are in [protocols/adr/](protocols/adr/README.md).

Every phase ends with something that runs and can be shown, and with its tests green. Work in small pull requests ([protocols/ci-cd-and-release.md](protocols/ci-cd-and-release.md)).

Status legend: `[x]` done, `[ ]` not started. Phases 0, 1, 2 and 3 are done (details and the exceptions are listed in each); nothing after Phase 3 is started.

## Phase 0: Foundation (documents)

- [x] Ontology design: [ontology.md](ontology.md)
- [x] Engineering protocols and five ADRs: [protocols/](protocols/README.md)
- [x] This plan
- [x] Link `ontology.md`, `PLAN.md` and `protocols/` from the main README
- [x] Short [CLAUDE.md](CLAUDE.md) pointing AI assistants at the README, the ontology and the protocols ([protocols/ai-assisted-development.md](protocols/ai-assisted-development.md))
- [ ] Turn on branch protection and required checks on GitHub (a repository setting on GitHub; not something the code can do)

## Phase 1: Store and definitions

Goal: the database exists, the definitions come from the spec, and database permissions are real.

- [x] `docker-compose.yml` with PostgreSQL ([ADR 0002](protocols/adr/0002-postgresql.md), [ADR 0005](protocols/adr/0005-containers-first.md))
- [x] Database roles `app_runner`, `app_reader`, `ingest`, `migrator` created by init SQL ([action-runner-and-audit.md](protocols/action-runner-and-audit.md))
- [x] Migrations (Alembic) for the operations tables, `telemetry_samples` and `audit_log`
- [x] Definition objects (`TelemetryParameter`, `TelemetryPacketType`, `CommandDefinition`) loaded read-only from `spec/minisat.yaml` ([ADR 0001](protocols/adr/0001-two-layer-ontology.md))
- [x] Database tests on real PostgreSQL, also in CI as a service container

Done when: `docker compose up` starts the database, migrations apply from empty, and a test proves the reader role cannot write and nobody can update or delete audit rows.

Result (2026-10-31): met. 86 database tests and 25 definition/config tests pass on PostgreSQL 14.18 (local) and 16.15 (the Compose container, with password authentication). All 28 mutations (14 existing, 14 new database ones) are caught. The Compose run found one real bug (the init script was not executable), now fixed. **Not yet verified:** the GitHub Actions `database` job has never run, and Python 3.10 has not been run. Decisions made while building it are in [ontology.md](ontology.md) (a `SYSTEM` operator role, anomaly severities, one open alarm per parameter). Operators, stations and spacecraft are created by an admin, not by an action (`minisat db-seed`, added in phase 3).

## Phase 2: Action runner

Goal: the only way to change state, with the command lifecycle working.

- [x] Action registry and runner (authorise, validate, transaction, audit, outbox) in `src/minisat/ontology/runner.py`
- [x] Actions: Propose, Approve, Release, Cancel Command; Acknowledge Alarm; Open and Update Anomaly. Also Plan Contact, and the system's own: Record Command Sent / Outcome, Raise / Update / Clear Alarm, Record Spacecraft Event, Set Health Status
- [x] Lifecycle, two-person rule, expiry, preflight ([command-safety-protocol.md](protocols/command-safety-protocol.md))
- [x] `preflight_command` and `expected_effect` functions, reusing the rules in `model.py` (preflight replays the command on a copy of the satellite model)
- [x] Negative tests per role and action; mutation checks for the safety rules ([testing-and-verification.md](protocols/testing-and-verification.md))
- [x] Migration 0002: what an approver needs to see (preflight, state snapshot, expected effect, send baseline), who cancelled and why, more event types
- [x] Test infrastructure: a fresh database per test cloned from a migrated template; a guard that refuses to run the database tests on a server that holds the development database

Done when: a scripted test walks a command from proposal to VERIFIED against the simulator, and every illegal step is refused with an audit row.

Result (2026-10-31): met. 15 actions; `tests/db/test_runner.py` checks the role matrix for every action and role, one audit row per attempt, rollback when the audit row cannot be written, and concurrent identical requests; `test_command_lifecycle.py` drives scripted walks to VERIFIED, REJECTED_ONBOARD and a reboot against the in-process simulator and refuses every illegal transition from every status. Decisions taken while building it, all written into the protocols and [ontology.md](ontology.md): **at most one command in flight per spacecraft** (telemetry counters cannot tell commands apart), the exact bytes are fixed at proposal time, delivery is **at most once**, and the system may propose (staging) and cancel expired proposals. Not built: notifying approvers of a vital proposal, notes for the AI agent on an anomaly.

## Phase 3: Ingestion and automations

Goal: live data flows into the ontology and the system reacts to it.

- [x] Ingestion adapter: UDP telemetry (existing `codec.py`) into samples and the spacecraft's newest values (as the `ingest` role); events are derived by the automations, which act as the system through the runner
- [x] Alarm automation from the spec's limits (raise, escalate, clear; health status)
- [x] Command verification (counters and expected effect; timeouts)
- [x] Unplanned SAFE mode opens an Anomaly
- [x] Sequence-gap detection (roadmap M3), recorded as PACKET_LOSS events; link loss and return recorded as events
- [x] Outbox worker for side effects (sending the UDP command, at most once)
- [x] `minisat db-seed`, `ground`, `act`, `actions`, `status`

Done when: running the simulator with `--soc 30` produces an Alarm object and a Spacecraft record that updates without anyone touching the database.

Result (2026-10-31): met, over real UDP sockets in `tests/db/test_ground_udp.py` and by hand with the real commands (README section 3.6). Full suite on PostgreSQL 16 in Docker: 510 passed, 1 skipped (the XTCE schema check); 251 pass without a database in an environment with only the base dependencies. **All 51 mutations (14 existing, 14 SQL, 23 in the Python logic) are caught.** Known limits: no authentication (`act` trusts the operator name), alarms have no hysteresis, the verification windows are untuned wall-clock values, `estimateTimeToSafe` and the staged proposal that uses it are not built, the GitHub Actions `database` job has still never run, Python 3.10 has not been run.

## Phase 4: API

- [ ] FastAPI: read endpoints for objects, links and series; action endpoints generated from the registry
- [ ] Authentication (dev token first, clearly marked dev-only) and role checks ([security-and-threat-model.md](protocols/security-and-threat-model.md))
- [ ] `/health/live`, `/health/ready`, metrics, structured logs with correlation IDs ([observability-and-operations.md](protocols/observability-and-operations.md))

Done when: the six questions in [ontology.md](ontology.md) §9 can be answered through the API.

## Phase 5: Dashboard

Goal: something to look at ([ADR 0003](protocols/adr/0003-local-web-app.md)).

- [ ] `dashboard/` with Vite, React, TypeScript and Blueprint
- [ ] Screens: spacecraft overview (state, charts with limit bands, eclipse), alarms, command workflow with approval and evidence, anomalies, ground track
- [ ] Chart and map libraries chosen when this phase starts
- [ ] A few end-to-end browser tests

Done when: you can start the stack, drain the battery with the demo scenario, watch the alarms fire, and recover the spacecraft with an approved command, in the browser.

## Phase 6: AI agent

Goal: an assistant that proposes, never sends ([ADR 0004](protocols/adr/0004-agent-propose-only.md)).

- [ ] Tool definitions (and an MCP server) generated from the action and function registry
- [ ] Agent runtime with guardrails, kill switch and full trace logging ([agent-safety-and-autonomy.md](protocols/agent-safety-and-autonomy.md))
- [ ] Evaluation scenarios and runner, hard gate of zero safety violations ([agent-evaluation.md](protocols/agent-evaluation.md))
- [ ] Agent panel in the dashboard

Done when: the ten starter scenarios run repeatedly with no safety violation and a recorded baseline.

## Phase 7: Packaging and CI

- [ ] Dockerfiles for backend, worker, simulator and dashboard; `docker compose up` runs the full stack
- [ ] CI stages 4-9 from [protocols/ci-cd-and-release.md](protocols/ci-cd-and-release.md)
- [ ] `CHANGELOG.md`, tagged release, README updated with screenshots

Done when: a clean machine with only Docker can run the whole demo from the README.

## Phase 8: Optional extras

Pick by goal, not by default.

- [ ] First real Yamcs run, as one more data source (README roadmap M1)
- [ ] Kubernetes manifests on a local cluster
- [ ] `Jenkinsfile` mirroring the CI commands
- [ ] Contact windows from `leo-contact-planner` (M7)
- [ ] Command CRC and authentication (M5, M10)
- [ ] Desktop wrapper (Tauri or Electron)

## Open decisions

| Decision | Needed by | Notes |
| --- | --- | --- |
| Which model provider and API for the agent | Phase 6 | cost, data terms, key handling |
| Real login (OIDC) versus dev token | Phase 4 | dev token is fine locally; not for any shared deployment |
| Chart and map libraries | Phase 5 | Blueprint has none |
| Repository name and layout | Phase 0 | the remote is `mmc.git` while the README says `mini-mission-control`; `dashboard/` and `evals/` are new top-level folders |
