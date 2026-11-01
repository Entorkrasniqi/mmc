"""Everything the API reads from the database. All of it runs as the ``app_reader`` role (it cannot write), in a read-only
transaction with a statement timeout. Values always travel as query parameters; the only text put into SQL is fixed in code.

Writes are not here: they go through the action runner (protocols/action-runner-and-audit.md).
"""
from __future__ import annotations

import math
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Iterator, List, Optional, Sequence, Tuple

from psycopg.rows import dict_row

from ..ontology.definitions import CommandDefinition, Definitions
from ..ontology.functions import mode_label, telemetry_period_s
from ..spec import Spec

__all__ = ["Store", "STATEMENT_TIMEOUT_MS", "MAX_PAGE", "operator_view", "spacecraft_view", "command_view", "iso_ms"]

STATEMENT_TIMEOUT_MS = 5000
MAX_PAGE = 500
FINITE = "value BETWEEN -1e308 AND 1e308"          # false for NaN and the infinities (PostgreSQL sorts NaN above everything)


def iso_ms(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000.0, tz=timezone.utc).isoformat(timespec="milliseconds")


class Store:
    """Opens a short-lived read-only connection per call. ``connect`` returns a new connection as the reader role."""

    def __init__(self, connect: Callable[[], Any]):
        self._connect = connect

    @contextmanager
    def session(self) -> Iterator[Any]:
        conn = self._connect()
        try:
            conn.row_factory = dict_row
            conn.read_only = True
            conn.execute(f"SET LOCAL statement_timeout = {int(STATEMENT_TIMEOUT_MS)}")
            yield conn
        finally:
            conn.rollback()
            conn.close()


# ------------------------------------------------------------------------------------------------ small helpers

class Where:
    """Builds a WHERE clause out of fixed text and parameters."""

    def __init__(self):
        self.clauses: List[str] = []
        self.params: Dict[str, Any] = {}

    def add(self, clause: str, **params) -> "Where":
        self.clauses.append(clause)
        self.params.update(params)
        return self

    def sql(self) -> str:
        return (" WHERE " + " AND ".join(self.clauses)) if self.clauses else ""


def _page(limit: int, offset: int) -> Tuple[int, int]:
    return max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))


def _finite_or_none(value) -> Optional[float]:
    return float(value) if value is not None and math.isfinite(value) else None


# ------------------------------------------------------------------------------------------------ operators

def operator_view(row: dict, full: bool) -> dict:
    """Display name only for everybody but supervisors (ontology.md, Operator)."""
    view = {"operator_id": row["operator_id"], "display_name": row["display_name"]}
    if full:
        view.update(kind=row["kind"], role=row["role"], created_at=row["created_at"])
    return view


def get_operator(conn, operator_id: str) -> Optional[dict]:
    return conn.execute("SELECT operator_id, display_name, kind, role, created_at FROM ops.operator WHERE operator_id = %s",
                        (operator_id,)).fetchone()


def list_operators(conn) -> List[dict]:
    return conn.execute("SELECT operator_id, display_name, kind, role, created_at FROM ops.operator "
                        "ORDER BY operator_id").fetchall()


# ------------------------------------------------------------------------------------------------ spacecraft

def list_spacecraft(conn) -> List[dict]:
    return conn.execute("SELECT * FROM ops.spacecraft ORDER BY spacecraft_id").fetchall()


def get_spacecraft(conn, spacecraft_id: str) -> Optional[dict]:
    return conn.execute("SELECT * FROM ops.spacecraft WHERE spacecraft_id = %s", (spacecraft_id,)).fetchone()


def bounds(pair) -> Optional[List[Optional[float]]]:
    """A (low, high) limit as a JSON list; either end may be null (no limit on that side)."""
    return list(pair) if pair else None


def spacecraft_view(spec: Spec, defs: Definitions, row: dict, now: datetime, stale_factor: float = 3.0) -> dict:
    """The Spacecraft object (ontology.md): its newest values, read against the definitions."""
    values = row["latest_values"] or {}
    age = (now - row["last_contact_at"]).total_seconds() if row["last_contact_at"] else None
    parameters = []
    for p in defs.parameters:
        if p.name not in values:
            continue
        value = values[p.name]
        label = next((lab for lab, v in (p.enum_labels or ()) if v == value), None)
        parameters.append({"name": p.name, "value": value, "unit": p.unit, "label": label, "severity": p.severity_of(value),
                           "warning": bounds(p.warning), "critical": bounds(p.critical)})
    return {"spacecraft_id": row["spacecraft_id"], "name": row["name"], "health_status": row["health_status"],
            "mode": mode_label(spec, values["mode"]) if "mode" in values else None,
            "last_contact_at": row["last_contact_at"], "telemetry_age_s": age,
            "telemetry_stale": age is None or age > stale_factor * telemetry_period_s(spec),
            "created_at": row["created_at"], "values": values, "parameters": parameters}


# ------------------------------------------------------------------------------------------------ commands

def command_view(defs: Definitions, row: dict) -> dict:
    """A CommandExecution with the contact it was released in, and its enum arguments spelled out."""
    view = dict(row)
    contact_id = view.get("contact_id")
    view["contact"] = ({"contact_id": contact_id, "station_id": view["contact_station_id"],
                        "start_at": view["contact_start_at"], "end_at": view["contact_end_at"]} if contact_id else None)
    for key in ("contact_station_id", "contact_start_at", "contact_end_at"):
        view.pop(key, None)
    try:
        definition: CommandDefinition = defs.command(view["command_id"])
        labels = {}
        for arg in definition.arguments:
            if arg.enum_labels and arg.name in view["arguments"]:
                labels[arg.name] = next((lab for lab, v in arg.enum_labels if v == view["arguments"][arg.name]), None)
        view["arguments_text"] = labels
    except KeyError:                          # a command that is no longer in the specification
        view["arguments_text"] = {}
    return view


_COMMAND_SELECT = ("SELECT ce.*, cw.station_id AS contact_station_id, cw.start_at AS contact_start_at, "
                   "cw.end_at AS contact_end_at FROM ops.command_execution ce "
                   "LEFT JOIN ops.contact_window cw ON cw.contact_id = ce.contact_id")


def list_commands(conn, defs: Definitions, spacecraft_id: Optional[str], statuses: Sequence[str], command: Optional[str],
                  since: Optional[datetime], until: Optional[datetime], responds_to: Optional[Any], limit: int,
                  offset: int) -> List[dict]:
    where = Where()
    if spacecraft_id:
        where.add("ce.spacecraft_id = %(sc)s", sc=spacecraft_id)
    if statuses:
        where.add("ce.status = ANY(%(statuses)s)", statuses=list(statuses))
    if command:
        where.add("ce.command_name = %(command)s", command=command)
    if since:
        where.add("ce.proposed_at >= %(since)s", since=since)
    if until:
        where.add("ce.proposed_at < %(until)s", until=until)
    if responds_to:
        where.add("ce.responds_to_alarm_id = %(alarm)s", alarm=responds_to)
    limit, offset = _page(limit, offset)
    rows = conn.execute(f"{_COMMAND_SELECT}{where.sql()} ORDER BY ce.proposed_at DESC, ce.execution_id "
                        f"LIMIT {limit} OFFSET {offset}", where.params).fetchall()
    return [command_view(defs, r) for r in rows]


def get_command(conn, defs: Definitions, execution_id) -> Optional[dict]:
    row = conn.execute(f"{_COMMAND_SELECT} WHERE ce.execution_id = %s", (execution_id,)).fetchone()
    return command_view(defs, row) if row else None


# ------------------------------------------------------------------------------------------------ alarms, events, anomalies

def list_alarms(conn, spacecraft_id: Optional[str], states: Sequence[str], parameter: Optional[str],
                since: Optional[datetime], until: Optional[datetime], limit: int, offset: int) -> List[dict]:
    where = Where()
    if spacecraft_id:
        where.add("spacecraft_id = %(sc)s", sc=spacecraft_id)
    if states:
        where.add("state = ANY(%(states)s)", states=list(states))
    if parameter:
        where.add("parameter_name = %(parameter)s", parameter=parameter)
    if since:
        where.add("raised_at >= %(since)s", since=since)
    if until:
        where.add("raised_at < %(until)s", until=until)
    limit, offset = _page(limit, offset)
    return conn.execute(f"SELECT * FROM ops.alarm{where.sql()} ORDER BY raised_at DESC, alarm_id "
                        f"LIMIT {limit} OFFSET {offset}", where.params).fetchall()


def get_alarm(conn, alarm_id) -> Optional[dict]:
    alarm = conn.execute("SELECT * FROM ops.alarm WHERE alarm_id = %s", (alarm_id,)).fetchone()
    if alarm is None:
        return None
    alarm["responding_commands"] = conn.execute(
        "SELECT execution_id, command_name, status, proposed_by, proposed_at FROM ops.command_execution "
        "WHERE responds_to_alarm_id = %s ORDER BY proposed_at", (alarm_id,)).fetchall()
    return alarm


def list_events(conn, spacecraft_id: Optional[str], types: Sequence[str], since: Optional[datetime],
                until: Optional[datetime], anomaly_id: Optional[Any], limit: int, offset: int) -> List[dict]:
    where = Where()
    if spacecraft_id:
        where.add("spacecraft_id = %(sc)s", sc=spacecraft_id)
    if types:
        where.add("event_type = ANY(%(types)s)", types=list(types))
    if since:
        where.add("occurred_at >= %(since)s", since=since)
    if until:
        where.add("occurred_at < %(until)s", until=until)
    if anomaly_id:
        where.add("anomaly_id = %(anomaly)s", anomaly=anomaly_id)
    limit, offset = _page(limit, offset)
    return conn.execute(f"SELECT * FROM ops.spacecraft_event{where.sql()} ORDER BY occurred_at DESC, event_id "
                        f"LIMIT {limit} OFFSET {offset}", where.params).fetchall()


def list_anomalies(conn, spacecraft_id: Optional[str], statuses: Sequence[str], limit: int, offset: int) -> List[dict]:
    where = Where()
    if spacecraft_id:
        where.add("spacecraft_id = %(sc)s", sc=spacecraft_id)
    if statuses:
        where.add("status = ANY(%(statuses)s)", statuses=list(statuses))
    limit, offset = _page(limit, offset)
    return conn.execute(f"SELECT * FROM ops.anomaly{where.sql()} ORDER BY detected_at DESC, anomaly_id "
                        f"LIMIT {limit} OFFSET {offset}", where.params).fetchall()


def get_anomaly(conn, defs: Definitions, anomaly_id) -> Optional[dict]:
    """The anomaly with everything linked to it: Part Of (alarms, events) and Resolved Through (commands)."""
    anomaly = conn.execute("SELECT * FROM ops.anomaly WHERE anomaly_id = %s", (anomaly_id,)).fetchone()
    if anomaly is None:
        return None
    anomaly["alarms"] = conn.execute("SELECT * FROM ops.alarm WHERE anomaly_id = %s ORDER BY raised_at",
                                     (anomaly_id,)).fetchall()
    anomaly["events"] = conn.execute("SELECT * FROM ops.spacecraft_event WHERE anomaly_id = %s ORDER BY occurred_at",
                                     (anomaly_id,)).fetchall()
    rows = conn.execute(f"{_COMMAND_SELECT} JOIN ops.anomaly_command_execution link ON link.execution_id = ce.execution_id "
                        f"WHERE link.anomaly_id = %s ORDER BY ce.proposed_at", (anomaly_id,)).fetchall()
    anomaly["commands"] = [command_view(defs, r) for r in rows]
    return anomaly


# ------------------------------------------------------------------------------------------------ stations and contacts

def list_stations(conn) -> List[dict]:
    return conn.execute("SELECT * FROM ops.ground_station ORDER BY station_id").fetchall()


def packet_loss(conn, spacecraft_id: str, start: datetime, end: datetime) -> Dict[str, int]:
    """Packets missing between two instants, counted from the PACKET_LOSS events the ground station recorded when the
    14-bit sequence counter jumped (ontology.md, packetLoss)."""
    row = conn.execute(
        "SELECT count(*)::bigint AS events, "
        "coalesce(sum(CASE WHEN jsonb_typeof(details -> 'lost') = 'number' THEN (details ->> 'lost')::numeric END), 0)::bigint "
        "AS lost FROM ops.spacecraft_event WHERE spacecraft_id = %s AND event_type = 'PACKET_LOSS' "
        "AND occurred_at >= %s AND occurred_at < %s", (spacecraft_id, start, end)).fetchone()
    return {"events": row["events"], "lost": row["lost"]}


_CONTACT_SELECT = (
    "SELECT cw.*, (SELECT count(*) FROM ops.spacecraft_event e WHERE e.spacecraft_id = cw.spacecraft_id "
    "AND e.event_type = 'PACKET_LOSS' AND e.occurred_at >= cw.start_at AND e.occurred_at < cw.end_at)::bigint "
    "AS packet_loss_events, (SELECT coalesce(sum(CASE WHEN jsonb_typeof(e.details -> 'lost') = 'number' THEN "
    "(e.details ->> 'lost')::numeric END), 0) FROM ops.spacecraft_event e WHERE e.spacecraft_id = cw.spacecraft_id "
    "AND e.event_type = 'PACKET_LOSS' AND e.occurred_at >= cw.start_at AND e.occurred_at < cw.end_at)::bigint "
    "AS packets_lost_observed FROM ops.contact_window cw")


def list_contacts(conn, spacecraft_id: Optional[str], since: Optional[datetime], until: Optional[datetime],
                  statuses: Sequence[str], limit: int, offset: int) -> List[dict]:
    """Contact windows that overlap [since, until), oldest first (so "the third pass of yesterday" is item 3)."""
    where = Where()
    if spacecraft_id:
        where.add("cw.spacecraft_id = %(sc)s", sc=spacecraft_id)
    if since:
        where.add("cw.end_at > %(since)s", since=since)
    if until:
        where.add("cw.start_at < %(until)s", until=until)
    if statuses:
        where.add("cw.status = ANY(%(statuses)s)", statuses=list(statuses))
    limit, offset = _page(limit, offset)
    return conn.execute(f"{_CONTACT_SELECT}{where.sql()} ORDER BY cw.start_at, cw.contact_id LIMIT {limit} OFFSET {offset}",
                        where.params).fetchall()


def get_contact(conn, contact_id) -> Optional[dict]:
    contact = conn.execute(f"{_CONTACT_SELECT} WHERE cw.contact_id = %s", (contact_id,)).fetchone()
    if contact is None:
        return None
    contact["commands"] = conn.execute(
        "SELECT execution_id, command_name, status, proposed_by, approved_by, released_at FROM ops.command_execution "
        "WHERE contact_id = %s ORDER BY released_at", (contact_id,)).fetchall()
    return contact


# ------------------------------------------------------------------------------------------------ telemetry series

def newest_sample_ms(conn, spacecraft_id: str, parameter: str) -> Optional[int]:
    row = conn.execute("SELECT max(sc_time_ms) AS t FROM ops.telemetry_samples WHERE spacecraft_id = %s "
                       "AND parameter_name = %s", (spacecraft_id, parameter)).fetchone()
    return row["t"]


def series(conn, spacecraft_id: str, parameter: str, from_ms: int, to_ms: int, max_points: int) -> Dict[str, Any]:
    """The samples of one parameter between two spacecraft times (inclusive), thinned to at most ``max_points``.

    Up to ``max_points`` samples come back as they are (``resolution: "raw"``). More than that are grouped into equal
    time buckets of ``bucket_ms``, each reported with its mean (``v``), lowest and highest value and sample count
    (``resolution: "bucketed"``); a spike inside a bucket is still visible in ``max``/``min``. NaN and infinity cannot be
    written in JSON: they come back as ``null`` (and are left out of a bucket's statistics).
    """
    bounds = {"sc": spacecraft_id, "p": parameter, "a": from_ms, "b": to_ms}
    n = conn.execute("SELECT count(*)::bigint AS n FROM ops.telemetry_samples WHERE spacecraft_id = %(sc)s "
                     "AND parameter_name = %(p)s AND sc_time_ms BETWEEN %(a)s AND %(b)s", bounds).fetchone()["n"]
    if n <= max_points:
        rows = conn.execute("SELECT sc_time_ms, value FROM ops.telemetry_samples WHERE spacecraft_id = %(sc)s "
                            "AND parameter_name = %(p)s AND sc_time_ms BETWEEN %(a)s AND %(b)s ORDER BY sc_time_ms",
                            bounds).fetchall()
        points = [{"t_ms": r["sc_time_ms"], "t": iso_ms(r["sc_time_ms"]), "v": _finite_or_none(r["value"])} for r in rows]
        return {"resolution": "raw", "bucket_ms": None, "samples": n, "points": points}
    width = -(-(to_ms - from_ms + 1) // max_points)                       # ceil: at most max_points buckets
    rows = conn.execute(
        f"SELECT min(sc_time_ms) AS t_ms, avg(value) FILTER (WHERE {FINITE}) AS v, min(value) FILTER (WHERE {FINITE}) AS lo, "
        f"max(value) FILTER (WHERE {FINITE}) AS hi, count(*)::bigint AS n FROM ops.telemetry_samples "
        f"WHERE spacecraft_id = %(sc)s AND parameter_name = %(p)s AND sc_time_ms BETWEEN %(a)s AND %(b)s "
        f"GROUP BY (sc_time_ms - %(a)s) / %(w)s ORDER BY min(sc_time_ms)", {**bounds, "w": width}).fetchall()
    points = [{"t_ms": r["t_ms"], "t": iso_ms(r["t_ms"]), "v": _finite_or_none(r["v"]), "min": _finite_or_none(r["lo"]),
               "max": _finite_or_none(r["hi"]), "n": r["n"]} for r in rows]
    return {"resolution": "bucketed", "bucket_ms": width, "samples": n, "points": points}


def eclipse_context(conn, spacecraft_id: str) -> Optional[Tuple[bool, Optional[Tuple[bool, float]]]]:
    """What telemetry shows about where the spacecraft is on its orbit: (in eclipse now, (that state, seconds since it
    began)). The second part is None while no change has been seen. Seconds are spacecraft time between samples, so a
    sped-up simulation is still consistent. None when no ``in_eclipse`` sample exists."""
    base = ("SELECT sc_time_ms, value FROM ops.telemetry_samples WHERE spacecraft_id = %s AND parameter_name = 'in_eclipse' ")
    latest = conn.execute(base + "ORDER BY sc_time_ms DESC LIMIT 1", (spacecraft_id,)).fetchone()
    if latest is None:
        return None
    current = latest["value"]
    other = conn.execute(base + "AND value <> %s ORDER BY sc_time_ms DESC LIMIT 1", (spacecraft_id, current)).fetchone()
    if other is None:
        return bool(current), None
    first = conn.execute("SELECT min(sc_time_ms) AS t FROM ops.telemetry_samples WHERE spacecraft_id = %s "
                         "AND parameter_name = 'in_eclipse' AND value = %s AND sc_time_ms > %s",
                         (spacecraft_id, current, other["sc_time_ms"])).fetchone()["t"]
    return bool(current), (bool(current), (latest["sc_time_ms"] - first) / 1000.0)
