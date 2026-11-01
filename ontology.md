# MiniSat Mission Control Ontology

The model that every UI, automation and agent in mini-mission-control reads and writes through.
Design rule: **model the spacecraft operation, not the packets.** Packets, UDP, XTCE and Yamcs are *sources and sinks* around the ontology, not the ontology itself.

## 0. Purpose
- **Decisions / workflow supported:** "Is the spacecraft healthy, and what may I safely command during this contact?" End to end: observe telemetry → raise and acknowledge alarms → propose a command → approve → release → verify it took effect → record anomalies.
- **Actors:** operators (people), a flight supervisor (person, approves risky commands), an AI assistant (agent, read plus *propose* only), the simulator and Yamcs (systems that feed observations and carry commands).
- **Systems of record:**
  - `spec/minisat.yaml` → the *definition* types (what parameters, packets, commands and limits exist). Read-only to the ontology; changed only by a reviewed pull request, then `minisat gen-xtce`.
  - Simulator (or Yamcs, later) → *observations* (telemetry).
  - The ontology database → everything operators *do* (command executions, alarm handling, anomalies, passes).

Two layers, deliberately separate:

| Layer | Question it answers | Mutable at runtime? |
| --- | --- | --- |
| **Definition layer** (generated from the YAML) | What can exist? | No (PR + regenerate) |
| **Operations layer** (this app's database) | What is happening, and what did people decide? | Only through actions |

## 1. Object types

### Spacecraft
- Represents: one satellite (MiniSat is the first; the model must not assume only one).
- Primary key: `spacecraftId` (e.g. `MINISAT-1`)
- Properties: name, mode (enum Mode: SAFE | NOMINAL | PAYLOAD), healthStatus (enum: NOMINAL | WARNING | CRITICAL | SAFE_MODE), lastContactAt, uptimeS, cmdAccepted, cmdRejected, lastCmdId, heaterOn, inEclipse, batterySocPct, batteryVoltageV, batteryTempC, latitudeDeg, longitudeDeg, altitudeKm
- Source: latest values folded in from telemetry (see TelemetryParameter); `healthStatus` is a function (§4), not hand-edited
- Readable by: all roles

### TelemetryPacketType  *(definition layer)*
- Represents: a kind of packet the spacecraft emits (Housekeeping, Position).
- Primary key: `apid`
- Properties: name, periodS, description, sizeBytes
- Source: generated from `spec/minisat.yaml`
- Readable by: all roles

### TelemetryParameter  *(definition layer)*
- Represents: one measured quantity (battery_soc_pct, mode, ...), independent of any value it ever had.
- Primary key: `parameterName` (unique across packets, already a rule in the spec)
- Properties: description, unit, dataType, enumName, warningLow/High, criticalLow/High
- Source: generated from the YAML (`limits` become the alarm bands)
- Readable by: all roles

### TelemetrySample  *(observation, high volume)*
- Represents: one value of one parameter at one spacecraft time.
- Primary key: (`spacecraftId`, `parameterName`, `scTimeMs`)
- Properties: value (number | enum label), scTimeMs, receivedAt, packetSeqCount
- Source: simulator or Yamcs
- **Not an object in the object store.** Stored as a time series (append-only table, later TimescaleDB); the ontology exposes it as a *time-series property* of Spacecraft (`spacecraft.series("battery_soc_pct", from, to)`). One object per sample would be a Kitchen Sink and would not scale.
- Readable by: all roles

### CommandDefinition  *(definition layer)*
- Represents: a command the spacecraft understands (Noop, SetMode, SetHeater, Reboot, SetTmRate).
- Primary key: `commandId` (the wire id, 1 to 65535)
- Properties: name, description, significance (enum: NORMAL | VITAL), arguments (typed list with range or enum)
- Source: generated from the YAML
- Readable by: all roles

### CommandExecution
- Represents: one attempt to make the spacecraft do something, from proposal to verified outcome. It has its own lifecycle, so it is its own object, not a field on Spacecraft.
- Primary key: `executionId`
- Properties: arguments (typed JSON), status (enum: PROPOSED | APPROVED | RELEASED | SENT | ACCEPTED | REJECTED_ONBOARD | VERIFIED | FAILED | CANCELLED), rejectionReason, proposedAt, releasedAt, verifiedAt, rawBytesHex
- Source: created by actions; `SENT → ACCEPTED/REJECTED` is derived by comparing `cmdAccepted`, `cmdRejected`, `lastCmdId` telemetry before and after the send
- Readable by: all roles

### Alarm
- Represents: one episode of a parameter being outside its limits (an *event*, with a start and an end).
- Primary key: `alarmId`
- Properties: severity (enum: WARNING | CRITICAL), triggerValue, limitViolated, raisedAt, clearedAt, state (enum: ACTIVE | ACKNOWLEDGED | CLEARED), acknowledgedAt, acknowledgeNote. At most one open (not CLEARED) alarm per spacecraft and parameter: an alarm is an episode and may escalate from WARNING to CRITICAL (enforced by the database).
- Source: raised by the automation in §5 (or by Yamcs, mapped in)
- Readable by: all roles

### Anomaly
- Represents: an unexpected spacecraft behaviour an operator has decided deserves tracking (e.g. unplanned SAFE mode).
- Primary key: `anomalyId`
- Properties: title, status (enum: OPEN | INVESTIGATING | RESOLVED), severity (enum: LOW | MEDIUM | HIGH), detectedAt, resolvedAt, rootCause, resolutionNote, openedBy. Resolving needs a root cause (enforced by the database).
- Source: opened by people or by an automation; **never deleted, resolved**
- Readable by: all roles

### SpacecraftEvent
- Represents: a discrete thing that happened on board or around it (mode change, FDIR trigger, reboot, eclipse entry/exit, command accepted/rejected).
- Primary key: `eventId`
- Properties: eventType (enum), occurredAt, details (JSON), spacecraftId
- Source: derived by comparing consecutive Housekeeping packets (roadmap M4 later makes the satellite send them itself)
- Readable by: all roles

### GroundStation
- Represents: an antenna site that can talk to the spacecraft.
- Primary key: `stationId`
- Properties: name, latitudeDeg, longitudeDeg, minElevationDeg
- Source: reference data (sibling project `leo-contact-planner`)
- Readable by: all roles

### ContactWindow
- Represents: a planned or actual period when a station can talk to the spacecraft (a pass).
- Primary key: `contactId`
- Properties: startAt, endAt, maxElevationDeg, status (enum: PLANNED | ACTIVE | COMPLETED | MISSED), packetsReceived, packetsLost
- Source: `leo-contact-planner` (planned); the link layer fills in actuals
- Readable by: all roles

### Operator
- Represents: a person or agent that acts in the system.
- Primary key: `operatorId`
- Properties: displayName, kind (enum: HUMAN | AGENT | SYSTEM), role (enum: VIEWER | OPERATOR | SUPERVISOR | AGENT | SYSTEM; the database only allows matching pairs: a HUMAN is a viewer, operator or supervisor, an AGENT has role AGENT, a SYSTEM has role SYSTEM)
- Source: created by administrators
- Readable by: all roles (display name only for non-supervisors)

## 2. Link types

| From | Link | To | Cardinality | Notes |
| --- | --- | --- | --- | --- |
| Spacecraft | Emits | TelemetryPacketType | many-to-many | which packet types this spacecraft flies |
| TelemetryPacketType | Contains | TelemetryParameter | one-to-many (ordered) | field order = wire order |
| Spacecraft | Accepts | CommandDefinition | many-to-many | |
| CommandExecution | Instance Of | CommandDefinition | many-to-one | |
| CommandExecution | Targets | Spacecraft | many-to-one | |
| CommandExecution | Proposed By | Operator | many-to-one | human or agent |
| CommandExecution | Approved By | Operator | many-to-one (optional) | must differ from Proposed By for VITAL commands |
| CommandExecution | Sent During | ContactWindow | many-to-one (optional) | |
| CommandExecution | Responds To | Alarm | many-to-one (optional) | "I sent this because of that alarm" |
| Alarm | Concerns | TelemetryParameter | many-to-one | |
| Alarm | On | Spacecraft | many-to-one | |
| Alarm | Acknowledged By | Operator | many-to-one (optional) | |
| Alarm | Part Of | Anomaly | many-to-one (optional) | |
| Anomaly | Involves | Spacecraft | many-to-one | |
| Anomaly | Resolved Through | CommandExecution | many-to-many | |
| SpacecraftEvent | Observed On | Spacecraft | many-to-one | |
| SpacecraftEvent | Caused By | CommandExecution | many-to-one (optional) | e.g. the mode change after SetMode |
| ContactWindow | Between | Spacecraft / GroundStation | many-to-one each | |

## 3. Action types
All writes happen here. Each action: authorise → validate → apply in one transaction → append an audit row (actor, kind, parameters, before, after) → side effects.

### Propose Command
- Changes: creates CommandExecution (PROPOSED), links Instance Of / Targets / Proposed By
- Parameters: spacecraftId, commandName, arguments, reason (text), respondsToAlarmId (optional)
- Who may run it: Operator, Supervisor, Agent, and the system (an automation may stage a proposal for a person to review)
- Validation: arguments type- and range-checked against CommandDefinition (same check as `encode_tc(validate=True)`); the exact bytes are built now and stored, so the approver approves what will be sent; `preflightCommand` (§4) must not predict an on-board rejection, or the proposal carries a warning; at most one open execution per spacecraft and command
- Side effects: none yet (notifying approvers of a VITAL command is not built)
- Agent-callable: **yes**; human confirmation: n/a (this only *proposes*)

### Approve Command
- Changes: CommandExecution PROPOSED → APPROVED; links Approved By
- Parameters: executionId, note
- Who may run it: Operator (NORMAL commands), Supervisor (VITAL commands)
- Validation: approver ≠ proposer for VITAL (and a VITAL command needs a supervisor); proposal not older than 15 minutes; the preflight is re-run against the state now, and a predicted on-board rejection can be approved only by a supervisor with a written note
- Agent-callable: **no**

### Release Command
- Changes: APPROVED → RELEASED → SENT; hands the bytes to the link (UDP now, Yamcs later); starts verification
- Parameters: executionId
- Who may run it: Operator, Supervisor
- Validation: a ContactWindow covers now (planned or active), or a supervisor gives an `override_reason`; the approval has not expired; **no other command of this spacecraft is in flight** (RELEASED, SENT or ACCEPTED). Telemetry reports counters, not which command they belong to, so one command at a time keeps verification sound until commands are acknowledged individually (PUS, roadmap M8)
- Side effects: the bytes are queued in the outbox; the outbox worker marks the command SENT and puts it on the link **at most once** (a command is never re-sent by itself); automations then watch `cmd_accepted`, `cmd_rejected`, `last_cmd_id`
- Agent-callable: **no**

### Cancel Command
- Changes: PROPOSED or APPROVED → CANCELLED
- Parameters: executionId, reason
- Who may run it: proposer, Operator, Supervisor
- Agent-callable: yes for its own proposals; human confirmation: no

### Acknowledge Alarm
- Changes: Alarm ACTIVE → ACKNOWLEDGED, sets acknowledgedBy/At
- Parameters: alarmId, note
- Who may run it: Operator, Supervisor
- Agent-callable: **no** (a person must take responsibility for an alarm)

### Open Anomaly
- Changes: creates Anomaly, links alarms and events as Part Of
- Parameters: title, severity, alarmIds, eventIds, spacecraftId
- Who may run it: Operator, Supervisor, Agent, automation
- Agent-callable: **yes**; human confirmation: no (it is a record, not an operation)

### Update Anomaly
- Changes: status transitions OPEN → INVESTIGATING → RESOLVED; rootCause, resolutionNote
- Who may run it: Operator, Supervisor. Resolving requires a root cause.
- Agent-callable: no (adding notes for the agent needs a place to store them, which is not built; planned with the agent in phase 6)

### Plan Contact
- Changes: creates or updates ContactWindow
- Parameters: spacecraftId, stationId, startAt, endAt
- Who may run it: Supervisor, `leo-contact-planner` import (the system)
- Validation: no overlap on the same station (the database refuses overlapping contacts that are not MISSED)

### Not an action: changing the interface itself
Adding a parameter, changing an alarm limit or adding a command is **a pull request to `spec/minisat.yaml`** followed by `minisat gen-xtce` and a database migration. Runtime edits of limits would let the ground and the XTCE database drift apart.

## 4. Functions
- `healthStatus(spacecraft) -> enum`: worst severity among ACTIVE alarms, or SAFE_MODE if mode is SAFE.
- `preflightCommand(spacecraft, commandName, args) -> {accepted, reason}`: replays the on-board rules from `model.py` (PAYLOAD refused below 30 % charge, SetTmRate range) against current state. Lets an operator see "this would be rejected" before sending.
- `estimateTimeToSafe(spacecraft[, command]) -> seconds | null`: from the SoC, the load of the (possibly commanded) mode and the eclipse schedule, when does charge reach the 15 % FDIR threshold? Null if it does not within the horizon (6 h by default). **Built in phase 4** (`functions.estimate_time_to_safe`, `POST /api/functions/estimate-time-to-safe`): it replays a copy of the satellite's own model, as `preflightCommand` does, and aligns the eclipse schedule with the last eclipse transition seen in the samples (worst case assumed when none was seen). It cannot see the phase of the model's solar wobble, so it is approximate (see `tests/test_ontology_time_to_safe.py` for the measured error).
- `nextEclipse(spacecraft, from) -> {start, end}`: uses `Orbit.in_eclipse`.
- `expectedEffect(commandName, args) -> list of {parameter, expected}`: what telemetry should show if the command worked (SetMode PAYLOAD → `mode = PAYLOAD`, `load_current_a` rises). Used for verification.
- `isInContact(spacecraft, t) -> bool`.
- `packetLoss(spacecraft, window) -> int`: from gaps in the CCSDS sequence counter per APID (roadmap M3). Built: the ground station records PACKET_LOSS events, and `GET /api/spacecraft/{id}/packet-loss` and the `packets_lost_observed` of each contact window sum them.

## 5. Automations
Built in phase 3 (`src/minisat/ontology/automation.py`); all of it runs as the SYSTEM operator through the action runner:

- When a telemetry value leaves its warning or critical band, **Raise Alarm**; if the severity changes, **Update Alarm**; when it returns inside the band, **Clear Alarm**. One open alarm per parameter. A NaN or infinite value is never judged.
- The derived health status (NOMINAL, WARNING, CRITICAL, SAFE_MODE; SAFE_MODE wins) is updated after every packet.
- When a CommandExecution is SENT and the counters show it (`cmd_accepted` rose and `last_cmd_id` is the command's id) → ACCEPTED; then, if the `expected_effect` shows in telemetry → VERIFIED (a command with no visible effect is verified by the counter alone). If `cmd_rejected` rose instead → REJECTED_ONBOARD (telemetry does not carry the satellite's reason; that is in its own log). If nothing shows within 5 s of sending, or the effect is missing 10 s after sending → FAILED. A reboot is recognised by the uptime reset, since it wipes the counters.
- When `mode` becomes SAFE and no accepted SetMode explains it → record an FDIR event and **Open Anomaly** ("Unplanned SAFE mode", HIGH, linked to the open alarms and the event); a HIGH anomaly queues a notification for supervisors.
- Events are derived from what changed between packets: mode changes, reboots, command accepted/rejected, eclipse entry and exit, and packet loss from gaps in the CCSDS sequence counter.
- No telemetry for 3 × the Housekeeping period is recorded as a LINK_LOST event (LINK_RESTORED when it returns). This is an event, not an alarm, because alarms in this model are about telemetry parameters.
- A proposal or approval that expired without being released is cancelled by the system.

Not built yet:

- When `estimateTimeToSafe` < 30 min and mode is PAYLOAD → **stage** a Propose Command `SetMode NOMINAL` for human review (staged, never auto-released). The function exists since phase 4; the automation does not.

## 6. Interfaces (shared shapes)
- **Alarmable**: `warningLow/High`, `criticalLow/High`. Implemented by TelemetryParameter; any future derived parameter reuses it.
- **TimeStamped**: `occurredAt`/`scTimeMs`. Implemented by TelemetrySample, SpacecraftEvent, Alarm.
- **Auditable**: `createdBy`, `createdAt`. Implemented by CommandExecution, Anomaly, ContactWindow.
- **Commandable**: `accepts`, `preflightCommand`. Implemented by Spacecraft (a future Payload subsystem could implement it too).

## 7. Roles and permissions
- **Viewer**: read everything. No actions.
- **Operator**: Propose, Approve (NORMAL only), Release, Cancel, Acknowledge Alarm, Open/Update Anomaly.
- **Supervisor**: everything an Operator can, plus Approve VITAL commands, override no-contact, Plan Contact, resolve anomalies.
- **Agent**: read everything, Propose Command, Open Anomaly, add anomaly notes. Cannot approve, release or acknowledge.
- **System** (a kind of operator for ingestion and automations, not a person): runs only the actions the automations in §5 need (create and clear Alarms, record SpacecraftEvents, move CommandExecutions from SENT to their outcome, open Anomalies). Never approves or acknowledges.
- **Spec Maintainer**: not a runtime role; changes the YAML through code review.
- The application database role has **no direct write access** to operations tables; only the action runner writes. Telemetry ingestion has its own narrow write role (append to the samples table and refresh the spacecraft's newest values, nothing else). Operators, spacecraft and ground stations are reference data created by administrators, not by actions. Phase 1 implements this with four database roles (`migrator`, `app_runner`, `app_reader`, `ingest`); see `migrations/versions/0001_operations_schema.py` and `tests/db/test_privileges.py`.

## 8. Agent tool surface
- **Read tools:** `get_spacecraft_state`, `get_series(parameter, from, to)`, `list_alarms(state)`, `list_command_executions(status)`, `get_command_definition`, `list_contacts`.
- **Compute tools:** `preflight_command`, `estimate_time_to_safe`, `next_eclipse`, `expected_effect`.
- **Action tools:** `propose_command` (always stages; a human must approve and release), `open_anomaly`, `add_anomaly_note`.
- Generated from the same action and function registry as the UI, so the agent gets the same validation and audit trail. The agent cannot send a command; the strongest thing it can do is a well-argued proposal.

## 9. Questions this model should answer by navigation
1. Which alarms are active, and what commands were sent in response?
2. Why is the spacecraft in SAFE mode? (events → alarms → the last PAYLOAD command and the SoC series before it)
3. Did the `SetMode PAYLOAD` I sent at 14:02 take effect, and if not, why? (CommandExecution → status, rejectionReason)
4. Who approved the last `Reboot`, and during which contact?
5. If I switch to PAYLOAD now, when would the battery reach the FDIR limit? (`estimateTimeToSafe` after `preflightCommand`)
6. How many packets did we lose in yesterday's third pass?

## 10. Implementation plan (Python, matches the repo)
1. **Definition layer first:** extend `spec.py`/a new `ontology/definitions.py` to expose TelemetryParameter, TelemetryPacketType and CommandDefinition as typed read-only objects straight from the spec. No new source of truth.
2. **Store:** SQLite (switchable to PostgreSQL) with tables for operations objects and an append-only `telemetry_samples` and `audit_log`. Pydantic models for object types.
3. **Action registry and runner:** each action is a definition (parameter model, permission, validator, handler, side effects). One runner does authorise → validate → transaction → audit → side effects. Direct table writes are not exposed.
4. **Ingestion adapter:** subscribes to the existing UDP telemetry (reusing `codec.py`), writes TelemetrySamples, updates Spacecraft latest values, emits events. A Yamcs adapter can replace it later without changing the ontology.
5. **Functions and automations:** `preflightCommand` reuses `model.py` rules; the automations run in a small worker loop reading an outbox table.
6. **API and dashboard:** FastAPI exposing objects, links and actions (built: `src/minisat/api/`); a React and Blueprint dashboard over it (built: `dashboard/`: overview, alarms, command workflow with evidence, anomaly board, ground track). The object explorer is not built.
7. **Agent surface:** an MCP server generated from the registry.
8. **Tests:** pytest as elsewhere. Add a test per action (permission, validation, audit row) and a test that no code path writes operations tables outside the runner.
