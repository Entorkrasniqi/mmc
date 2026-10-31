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

## What the code does today

The rules marked *(built)* are implemented in `src/minisat/ontology/actions/commands.py`, `automation.py` and `worker.py` and tested in
`tests/db/test_command_lifecycle.py`, `test_ingest_automation.py` and `test_ground_udp.py`. The database also enforces some of them by itself
(two-person rule, only a human approves, nothing beyond PROPOSED without an approver, the telemetry baseline stored when sending): see migrations 0001 and 0002.

## Before approval

1. **Argument validation** against the spec: type, enum, range (the same check as `encode_tc(validate=True)`).
2. **Preflight** *(built)*: run `preflight_command` against the current state. It replays the command on a throw-away copy of the satellite model, so the prediction cannot drift from the on-board rules. A predicted on-board rejection (for example `SetMode PAYLOAD` below 30 % charge) stops an operator approving. A supervisor may approve with a written note. The check is run again when approving, against the state at that moment.
3. **Fresh state**: preflight uses telemetry no older than 3x the Housekeeping period (initial value). Otherwise the approver is told the state is stale.
4. **No conflicts** *(built)*: at most one open execution per spacecraft and command (for example two pending `SetMode`); and, when releasing, **at most one command in flight per spacecraft** (RELEASED, SENT or ACCEPTED). Telemetry reports counters and the id of the latest command, not which request they answer, so verification is sound only one command at a time. This is stricter than the first version of this protocol, deliberately; it can be relaxed when commands are acknowledged individually (PUS, roadmap M8).
5. **Expiry** *(built)*: a proposal expires after 15 minutes (initial value); the same deadline applies to releasing an approved command. The automations cancel expired proposals.
6. **Two-person rule for VITAL**: the approver must be a Supervisor and a different operator from the proposer. An agent never counts as the approver.

## Release

- Requires a contact window that covers the current time, planned or active *(built)*. A supervisor may override with a reason; the override is recorded on the execution, audited, and returned as a warning.
- The exact bytes are built when the command is proposed and stored on the execution (`raw_bytes_hex`), so the approver approves precisely what will be sent *(built)*.
- Delivery is **at most once** *(built)*: the outbox worker records the command as SENT first and only then puts the bytes on the link. If it dies in between, the command shows as SENT, never went out, and ends FAILED when no answer comes. Nothing re-sends it.
- A vital command is never auto-released, never in flight together with another command (rule 4), and never retried automatically.

## Verification

- Each command has an `expected_effect` *(built, `functions.expected_effect`)*, stored on the execution when it is proposed. `SetMode X` -> `mode = X`; `SetHeater` -> `heater = state`; `Reboot` -> the uptime decreases and the mode is SAFE; `Noop` and `SetTmRate` have no visible effect, so their counter alone verifies them. (`load_current_a` is not checked: whether it rises depends on the mode it starts from.)
- The system watches telemetry after SENT *(built)* and compares it with the telemetry stored at the moment of sending (`send_baseline`). Initial windows, in wall-clock time from sending: 5 s to see the counters change, 10 s to see the effect; they are widened to three telemetry periods after a `SetTmRate` that slows the telemetry down.
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
| Lifecycle, two-person rule, expiry, preflight, contact window, one in flight, verification, at-most-once delivery | action runner, automations and worker; `tests/db/test_command_lifecycle.py`, `test_ingest_automation.py`, `test_ground_udp.py`; 23 Python mutations in `tools/mutation_check.py` | Enforced |
| Notifying approvers of a vital proposal | outbox message | Not built (a HIGH anomaly already queues a notification) |
