# Testing and verification protocol

**Status:** Proposed (the existing test suite already follows much of it). **Applies to:** all code and generated artifacts.

## Principle

A passing test proves only what it can fail on. The best evidence is a **second, independent reader** that shares no code with the thing it checks. The repo already does this for XTCE (`tests/xtce_interp.py` reads only the XML). Extend that habit; do not weaken it.

## Evidence levels

Use these words when describing how sure we are. Do not use a higher level than has been reached.

| Level | Meaning | Example today |
| --- | --- | --- |
| E0 Claimed | written down or believed; never run | the Yamcs configuration working live |
| E1 Unit-tested | passes tests written by the same author | most of `model.py` |
| E2 Independently checked | an oracle with no shared code agrees | codec vs the XTCE interpreter |
| E3 Integrated | runs against the real dependency | UDP tests on real sockets; later, real PostgreSQL |
| E4 Observed in the real target | seen working in the real system | not yet reached for Yamcs |

A README or CV claim must name its level honestly ("the XTCE database agrees with an independent interpreter and validates against the XTCE 1.2 schema", not "works with Yamcs").

## Test layers

| Layer | What it covers | Where | Notes |
| --- | --- | --- | --- |
| Hand-computed bytes | packets and headers worked out on paper | `tests/test_ccsds.py`, `test_codec.py` | catches bugs encoder and decoder share |
| Property tests | random valid inputs round-trip; invalid ones fail with a specific error | add with `hypothesis` | the 500-case header test becomes a property |
| Model tests | physics, FDIR, command rules | `tests/test_model.py` | deterministic seed |
| Independent oracle | generated XTCE vs the codec | `tests/xtce_interp.py` | keep it free of imports from `minisat` |
| Action tests | permissions, validation, audit, atomicity | new | see [action-runner-and-audit.md](action-runner-and-audit.md) |
| Database tests | real PostgreSQL, migrations up/down, grants | new | a container, never a mock |
| Integration | simulator -> ingestion -> database -> API | new | seeded, with injected clock |
| End to end | browser against the running stack | new | a few key flows only |
| Agent evals | non-deterministic behaviour | [agent-evaluation.md](agent-evaluation.md) | separate from unit tests |
| Mutation checks | inject known bugs, expect a failing test | `tools/mutation_check.py` | extend to runner and permissions |

## Rules

1. **Independent expected values.** The expected result in a test is computed by hand or by an independent oracle, not by calling the function under test.
2. **No mocks for the thing being protected.** Database behaviour is tested on PostgreSQL, packet behaviour over real bytes, permissions with real database roles.
3. **Deterministic by default.** Seeds are fixed, time is injected, nothing sleeps for wall-clock seconds. A test that needs real time is marked and kept few.
4. **Negative tests are required** for every permission, validation and lifecycle rule. "It works for the right user" is half a test.
5. **Boundary values.** Test at the limit, just inside and just outside (the existing alarm-boundary and range tests are the model).
6. **Mutation check for safety logic.** When adding the lifecycle, two-person rule or permission checks, add mutations that break each one and confirm a test fails. A rule no mutation can break is not tested.
7. **Flaky tests** are fixed or quarantined within a day. A test that is "usually green" is not evidence.
8. **Coverage** is a signal, not a target. Report it; do not chase a number. Safety-relevant modules (codec, runner, lifecycle, permissions) get reviewed for untested branches by hand.
9. **Every bug gets a regression test** that fails before the fix.
10. **Generated files are tested for freshness**, as `minisat gen-xtce --check` already does. Apply the same idea to any new generated file (API types, JSON Schema).

## Verification of claims

- A claim in documentation about an external system (Yamcs, CCSDS, XTCE behaviour) cites its source or is marked `unverified`.
- When something could not be run (as with Yamcs in the README), say so where the reader will see it, and say what would change the status.
- A result quoted in a README is reproducible by a command given next to it.

## Performance and resource checks

Not a target now. When added, measure first (ingest rate, query latency for the ontology questions, memory in a long run), record the baseline in this file, and gate only on regressions beyond a stated margin.

## Enforcement

| Rule | Mechanism | State |
| --- | --- | --- |
| Tests, lint, freshness check | CI | Enforced (existing) |
| Mutation check | `tools/mutation_check.py`, run manually (about 80 s) | Manual |
| Real-PostgreSQL tests | `tests/db` (needs `MINISAT_TEST_ADMIN_URL`; `MINISAT_REQUIRE_DB=1` turns a skip into a failure); CI `database` job with a service container | Enforced locally (PostgreSQL 14 and 16); CI job written, not yet run on GitHub |
| Mutation check covers the database rules | 14 database mutations in `tools/mutation_check.py`, run when a server is configured | Manual (all 28 mutations caught on the last run) |
| Property tests | `hypothesis` | Not yet |
| Mutation check in CI (nightly) | scheduled workflow | Not yet |
