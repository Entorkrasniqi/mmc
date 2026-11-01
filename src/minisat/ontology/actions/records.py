"""Alarms, anomalies, spacecraft events, health and contact windows.

Raising and clearing alarms, recording events and setting the health status are done by the SYSTEM operator (the automations
in ``automation.py``); a person acknowledges an alarm, opens and works anomalies, and a supervisor plans contacts.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from psycopg import errors as pg_errors
from pydantic import BaseModel, ConfigDict, Field

from ..runner import Action, ActionContext, Outcome

EVENT_TYPES = Literal["MODE_CHANGE", "FDIR", "REBOOT", "ECLIPSE_ENTRY", "ECLIPSE_EXIT", "COMMAND_ACCEPTED",
                      "COMMAND_REJECTED", "PACKET_LOSS", "LINK_LOST", "LINK_RESTORED"]
SYSTEM = frozenset({"SYSTEM"})


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _blank(text: Optional[str]) -> bool:
    return text is None or not text.strip()


def _spacecraft(ctx: ActionContext, spacecraft_id: str) -> dict:
    row = ctx.one("SELECT * FROM ops.spacecraft WHERE spacecraft_id = %s", (spacecraft_id,))
    if row is None:
        ctx.invalid(f"unknown spacecraft {spacecraft_id!r}")
    return row


def _one(ctx: ActionContext, table: str, key_col: str, key, row_before, row_after, result: dict) -> Outcome:
    k = f"{table}:{key}"
    return Outcome(result, {k: row_before}, {k: row_after})


# ------------------------------------------------------------------------------------------------ alarms

class AcknowledgeAlarmParams(_Params):
    alarm_id: uuid.UUID
    note: Optional[str] = None


class RaiseAlarmParams(_Params):
    spacecraft_id: str
    parameter_name: str
    severity: Literal["WARNING", "CRITICAL"]
    trigger_value: float
    limit_violated: str


class UpdateAlarmParams(_Params):
    alarm_id: uuid.UUID
    severity: Literal["WARNING", "CRITICAL"]
    trigger_value: float
    limit_violated: str


class ClearAlarmParams(_Params):
    alarm_id: uuid.UUID


def acknowledge_alarm(ctx: ActionContext, p: AcknowledgeAlarmParams) -> Outcome:
    row = ctx.lock("alarm", "alarm_id", p.alarm_id, "alarm")
    if row["state"] != "ACTIVE":
        ctx.invalid(f"only an ACTIVE alarm can be acknowledged; this one is {row['state']}")
    before, after = ctx.update("alarm", "alarm_id", p.alarm_id, state="ACKNOWLEDGED",
                               acknowledged_by=ctx.operator.operator_id, acknowledged_at=ctx.now,
                               acknowledge_note=p.note)
    return _one(ctx, "alarm", "alarm_id", p.alarm_id, before, after, {"alarm_id": str(p.alarm_id), "state": "ACKNOWLEDGED"})


def raise_alarm(ctx: ActionContext, p: RaiseAlarmParams) -> Outcome:
    _spacecraft(ctx, p.spacecraft_id)
    try:
        parameter = ctx.definitions.parameter(p.parameter_name)
    except KeyError:
        ctx.invalid(f"unknown telemetry parameter {p.parameter_name!r}")
    if parameter.warning is None and parameter.critical is None:
        ctx.invalid(f"{p.parameter_name} has no alarm limits in the specification")
    try:
        with ctx.conn.transaction():                               # a savepoint, so a clash does not poison the transaction
            row = ctx.insert("alarm", spacecraft_id=p.spacecraft_id, parameter_name=p.parameter_name,
                             severity=p.severity, trigger_value=p.trigger_value, limit_violated=p.limit_violated,
                             raised_at=ctx.now)
    except pg_errors.UniqueViolation:
        ctx.invalid(f"{p.parameter_name} already has an open alarm on {p.spacecraft_id}")
    aid = row["alarm_id"]
    return Outcome({"alarm_id": str(aid), "severity": p.severity},
                   after={f"alarm:{aid}": ctx.snapshot("alarm", "alarm_id", aid)})


def update_alarm(ctx: ActionContext, p: UpdateAlarmParams) -> Outcome:
    row = ctx.lock("alarm", "alarm_id", p.alarm_id, "alarm")
    if row["state"] == "CLEARED":
        ctx.invalid("a cleared alarm cannot be updated; a new violation raises a new alarm")
    before, after = ctx.update("alarm", "alarm_id", p.alarm_id, severity=p.severity, trigger_value=p.trigger_value,
                               limit_violated=p.limit_violated)
    return _one(ctx, "alarm", "alarm_id", p.alarm_id, before, after, {"alarm_id": str(p.alarm_id), "severity": p.severity})


def clear_alarm(ctx: ActionContext, p: ClearAlarmParams) -> Outcome:
    row = ctx.lock("alarm", "alarm_id", p.alarm_id, "alarm")
    if row["state"] == "CLEARED":
        ctx.invalid("this alarm is already cleared")
    before, after = ctx.update("alarm", "alarm_id", p.alarm_id, state="CLEARED", cleared_at=ctx.now)
    return _one(ctx, "alarm", "alarm_id", p.alarm_id, before, after, {"alarm_id": str(p.alarm_id), "state": "CLEARED"})


# ------------------------------------------------------------------------------------------------ anomalies

class OpenAnomalyParams(_Params):
    spacecraft_id: str
    title: str
    severity: Literal["LOW", "MEDIUM", "HIGH"]
    alarm_ids: List[uuid.UUID] = Field(default_factory=list)
    event_ids: List[uuid.UUID] = Field(default_factory=list)
    execution_ids: List[uuid.UUID] = Field(default_factory=list)


class UpdateAnomalyParams(_Params):
    anomaly_id: uuid.UUID
    status: Literal["INVESTIGATING", "RESOLVED"]
    root_cause: Optional[str] = None
    resolution_note: Optional[str] = None
    execution_ids: List[uuid.UUID] = Field(default_factory=list)       # commands that resolved it


ANOMALY_NEXT = {"OPEN": ("INVESTIGATING",), "INVESTIGATING": ("RESOLVED",)}


def _link_executions(ctx: ActionContext, anomaly_id, spacecraft_id: str, execution_ids) -> None:
    for eid in execution_ids:
        row = ctx.one("SELECT spacecraft_id FROM ops.command_execution WHERE execution_id = %s", (eid,))
        if row is None or row["spacecraft_id"] != spacecraft_id:
            ctx.invalid(f"command execution {eid} does not exist for {spacecraft_id}")
        ctx.conn.execute("INSERT INTO ops.anomaly_command_execution (anomaly_id, execution_id) VALUES (%s, %s) "
                         "ON CONFLICT DO NOTHING", (anomaly_id, eid))


def open_anomaly(ctx: ActionContext, p: OpenAnomalyParams) -> Outcome:
    _spacecraft(ctx, p.spacecraft_id)
    if _blank(p.title):
        ctx.invalid("a title is required")
    row = ctx.insert("anomaly", spacecraft_id=p.spacecraft_id, title=p.title.strip(), severity=p.severity,
                     detected_at=ctx.now, opened_by=ctx.operator.operator_id)
    aid = row["anomaly_id"]
    before: Dict[str, Any] = {}
    after: Dict[str, Any] = {f"anomaly:{aid}": ctx.snapshot("anomaly", "anomaly_id", aid)}
    for table, key_col, ids, what in (("alarm", "alarm_id", p.alarm_ids, "alarm"),
                                      ("spacecraft_event", "event_id", p.event_ids, "spacecraft event")):
        for key in ids:
            linked = ctx.lock(table, key_col, key, what)
            if linked["spacecraft_id"] != p.spacecraft_id:
                ctx.invalid(f"{what} {key} belongs to another spacecraft")
            if linked["anomaly_id"] is not None:
                ctx.invalid(f"{what} {key} is already part of anomaly {linked['anomaly_id']}")
            b, a = ctx.update(table, key_col, key, anomaly_id=aid)
            before[f"{table}:{key}"], after[f"{table}:{key}"] = b, a
    _link_executions(ctx, aid, p.spacecraft_id, p.execution_ids)
    if p.severity == "HIGH":
        ctx.outbox("notify_supervisors",
                   {"anomaly_id": str(aid), "title": p.title.strip(), "spacecraft_id": p.spacecraft_id})
    return Outcome({"anomaly_id": str(aid), "status": "OPEN"}, before, after)


def update_anomaly(ctx: ActionContext, p: UpdateAnomalyParams) -> Outcome:
    row = ctx.lock("anomaly", "anomaly_id", p.anomaly_id, "anomaly")
    if p.status not in ANOMALY_NEXT.get(row["status"], ()):
        allowed = ", ".join(ANOMALY_NEXT.get(row["status"], ())) or "nothing: it is resolved for good"
        ctx.invalid(f"an anomaly that is {row['status']} can move only to: {allowed}")
    fields: Dict[str, Any] = {"status": p.status}
    if p.root_cause is not None:
        fields["root_cause"] = p.root_cause.strip()
    if p.resolution_note is not None:
        fields["resolution_note"] = p.resolution_note.strip()
    if p.status == "RESOLVED":
        if _blank(p.root_cause) and _blank(row["root_cause"]):
            ctx.invalid("resolving an anomaly needs a root cause")
        fields["resolved_at"] = ctx.now
    before, after = ctx.update("anomaly", "anomaly_id", p.anomaly_id, **fields)
    _link_executions(ctx, p.anomaly_id, row["spacecraft_id"], p.execution_ids)
    return _one(ctx, "anomaly", "anomaly_id", p.anomaly_id, before, after,
                {"anomaly_id": str(p.anomaly_id), "status": p.status})


# ------------------------------------------------------------------------------------------------ events and health

class RecordSpacecraftEventParams(_Params):
    spacecraft_id: str
    event_type: EVENT_TYPES
    occurred_at: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    caused_by_execution_id: Optional[uuid.UUID] = None


class SetHealthStatusParams(_Params):
    spacecraft_id: str
    health_status: Literal["NOMINAL", "WARNING", "CRITICAL", "SAFE_MODE"]


def record_spacecraft_event(ctx: ActionContext, p: RecordSpacecraftEventParams) -> Outcome:
    _spacecraft(ctx, p.spacecraft_id)
    if p.occurred_at.tzinfo is None:
        ctx.invalid("occurred_at must include a time zone")
    row = ctx.insert("spacecraft_event", spacecraft_id=p.spacecraft_id, event_type=p.event_type,
                     occurred_at=p.occurred_at, details=p.details, caused_by_execution_id=p.caused_by_execution_id)
    eid = row["event_id"]
    return Outcome({"event_id": str(eid), "event_type": p.event_type},
                   after={f"spacecraft_event:{eid}": ctx.snapshot("spacecraft_event", "event_id", eid)})


def set_health_status(ctx: ActionContext, p: SetHealthStatusParams) -> Outcome:
    _spacecraft(ctx, p.spacecraft_id)
    before, after = ctx.update("spacecraft", "spacecraft_id", p.spacecraft_id, health_status=p.health_status)
    return _one(ctx, "spacecraft", "spacecraft_id", p.spacecraft_id, before, after,
                {"spacecraft_id": p.spacecraft_id, "health_status": p.health_status})


# ------------------------------------------------------------------------------------------------ contacts

class PlanContactParams(_Params):
    spacecraft_id: str
    station_id: str
    start_at: datetime
    end_at: datetime
    max_elevation_deg: Optional[float] = None


def plan_contact(ctx: ActionContext, p: PlanContactParams) -> Outcome:
    _spacecraft(ctx, p.spacecraft_id)
    if ctx.one("SELECT 1 AS x FROM ops.ground_station WHERE station_id = %s", (p.station_id,)) is None:
        ctx.invalid(f"unknown ground station {p.station_id!r}")
    if p.start_at.tzinfo is None or p.end_at.tzinfo is None:
        ctx.invalid("start_at and end_at must include a time zone")
    if p.end_at <= p.start_at:
        ctx.invalid("the contact must end after it starts")
    try:
        with ctx.conn.transaction():
            row = ctx.insert("contact_window", spacecraft_id=p.spacecraft_id, station_id=p.station_id,
                             start_at=p.start_at, end_at=p.end_at, max_elevation_deg=p.max_elevation_deg,
                             created_by=ctx.operator.operator_id)
    except pg_errors.ExclusionViolation:
        ctx.invalid(f"station {p.station_id} already has a contact that overlaps this one")
    cid = row["contact_id"]
    return Outcome({"contact_id": str(cid), "status": "PLANNED"},
                   after={f"contact_window:{cid}": ctx.snapshot("contact_window", "contact_id", cid)})


PEOPLE = frozenset({"OPERATOR", "SUPERVISOR"})
ANOMALY_OPENERS = frozenset({"OPERATOR", "SUPERVISOR", "AGENT", "SYSTEM"})

ACTIONS = (
    Action("Acknowledge Alarm", AcknowledgeAlarmParams, PEOPLE, acknowledge_alarm,
           "A person takes responsibility for an active alarm."),
    Action("Raise Alarm", RaiseAlarmParams, SYSTEM, raise_alarm, "A telemetry value left its limits."),
    Action("Update Alarm", UpdateAlarmParams, SYSTEM, update_alarm, "An open alarm escalated or eased."),
    Action("Clear Alarm", ClearAlarmParams, SYSTEM, clear_alarm, "The value is back inside its limits."),
    Action("Open Anomaly", OpenAnomalyParams, ANOMALY_OPENERS, open_anomaly,
           "Start tracking unexpected behaviour, linking the alarms, events and commands involved.", agent_callable=True),
    Action("Update Anomaly", UpdateAnomalyParams, PEOPLE, update_anomaly,
           "Move an anomaly to INVESTIGATING or RESOLVED (resolving needs a root cause)."),
    Action("Record Spacecraft Event", RecordSpacecraftEventParams, SYSTEM, record_spacecraft_event,
           "Something happened on board or on the link."),
    Action("Set Health Status", SetHealthStatusParams, SYSTEM, set_health_status,
           "The derived health of the spacecraft changed."),
    Action("Plan Contact", PlanContactParams, frozenset({"SUPERVISOR", "SYSTEM"}), plan_contact,
           "Plan a contact window between a spacecraft and a ground station."),
)
