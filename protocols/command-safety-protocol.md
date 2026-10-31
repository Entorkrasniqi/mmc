# Command safety protocol

**Status:** Proposed. **Applies to:** every telecommand, whoever or whatever proposes it.

## Principle

A telecommand acts on a machine nobody can touch, often with no undo. Treat "sent" as a promise, not a result. A command is finished only when telemetry shows its effect.

Defence in depth: the ground checks, and the spacecraft checks again, because the spacecraft cannot assume the ground was careful. The simulator already does this (`SetTmRate` is range-checked on the ground *and* on board).

## Lifecycle

```
PROPOSED -> APPROVED -> RELEASED -> SENT -> ACCEPTED -> VERIFIED
    |           |                             |-> REJECTED_ONBOARD
    |           |                             `-> FAILED (no effect seen)
    `-----------`--> CANCELLED
```

| From | To | Who / what | Condition |
| --- | --- | --- | --- |
| (new) | PROPOSED | Operator, Supervisor, Agent | arguments valid against the spec |
| PROPOSED | APPROVED | Operator (NORMAL), Supervisor (VITAL) | rules below |
| APPROVED | RELEASED | Operator, Supervisor | contact window active (or audited override) |
| RELEASED | SENT | system | bytes handed to the link |
| SENT | ACCEPTED | system | `cmd_accepted` increased and `last_cmd_id` matches |
| SENT | REJECTED_ONBOARD | system | `cmd_rejected` increased |
| ACCEPTED | VERIFIED | system | expected effect observed in time |
| SENT / ACCEPTED | FAILED | system | no matching counter change, or effect not seen, in time |
| PROPOSED / APPROVED | CANCELLED | proposer, Operator, Supervisor | any time before release |

Transitions not in the table are rejected by the action runner.

## Classification

- **NORMAL** and **VITAL** come from `significance` in `spec/minisat.yaml`. `Reboot` is vital today.
- The classification can be raised by an ADR but is never lowered at runtime.

## Before approval

1. **Argument validation** against the spec: type, enum, range (the same check as `encode_tc(validate=True)`).
2. **Preflight**: run `preflight_command` against current state. A predicted on-board rejection (for example `SetMode PAYLOAD` below 30 % charge) is shown to the approver as a blocking warning. A supervisor may approve with a written reason.
3. **Fresh state**: preflight uses telemetry no older than 3x the Housekeeping period (initial value). Otherwise the approver is told the state is stale.
4. **No conflicts**: at most one open command per spacecraft that changes the same state (for example two pending `SetMode`).
5. **Expiry**: a proposal expires after 15 minutes (initial value). An approval is invalid if the spacecraft state changed beyond tolerance since the preflight; the preflight is re-run.
6. **Two-person rule for VITAL**: the approver must be a Supervisor and a different operator from the proposer. An agent never counts as the approver.

## Release

- Requires an ACTIVE contact window. A supervisor may override with a reason; the override is audited and shown in the UI.
- The exact bytes sent are stored on the execution (`rawBytesHex`), so what was sent can be compared with what was intended.
- A vital command is never auto-released, never batched with other commands, and never retried automatically.

## Verification

- Each command definition has an `expected_effect` function. Examples: `SetMode PAYLOAD` -> `mode = PAYLOAD` and `load_current_a` increases; `Noop` -> only `cmd_accepted` increases.
- The system watches telemetry after SENT. Initial windows: 5 s to see the counters change, 10 s to see the effect (scaled with the telemetry period and any simulator speed-up).
- Possible outcomes are the lifecycle states above. FAILED is not an error to hide; it is information for the operator.
- "The packet was sent" is never shown as success.

## After a failure

- REJECTED_ONBOARD shows the satellite's reason.
- FAILED prompts the operator to investigate, and may open an Anomaly.
- A retry is a **new proposal** with its own approval. Nothing retries itself.

## Required tests

- Each illegal lifecycle transition is refused.
- A vital command cannot be approved by its proposer or by an agent.
- An expired proposal cannot be released.
- Release without an active contact window fails; override works only for a supervisor and writes an audit row.
- Verification: accepted, rejected and no-effect paths each end in the right state (using the simulator, seeded).
- A command crafted to bypass ground validation is still rejected on board (existing model test; keep it).

## Enforcement

| Rule | Mechanism | State |
| --- | --- | --- |
| Argument validation | `encode_tc(validate=True)` | Enforced (existing) |
| On-board re-check | `Spacecraft.handle_command` tests | Enforced (existing) |
| Lifecycle, two-person rule, expiry, verification | action runner + tests above | Not yet |
