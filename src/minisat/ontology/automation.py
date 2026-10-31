"""Automations (ontology.md section 5): what the system does by itself when telemetry arrives or time passes.

Every effect goes through the action runner as the SYSTEM operator, so automations get the same validation, the same database
rules and the same audit trail as a person clicking a button. They never send a command and never approve anything.

On each telemetry packet:  link restored, packet loss, events derived from what changed, alarms raised/escalated/cleared,
an anomaly for an unplanned SAFE mode, command verification (SENT -> ACCEPTED -> VERIFIED, or REJECTED_ONBOARD),
health status.
On each tick:  commands that got no answer in time fail, stale proposals are cancelled, a silent link is reported.
"""
from __future__ import annotations

import math
import threading
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, List, Optional

from ..spec import Spec
from .definitions import TelemetryParameter
from .functions import command_signal, derive_events, effects_met, health_status, telemetry_period_s
from .ingest import IngestResult, SharedConnection
from .runner import ActionError, ActionResult, ActionRunner, utcnow

__all__ = ["AutomationConfig", "AutomationEngine"]


@dataclass(frozen=True)
class AutomationConfig:
    accept_window_s: float = 5.0        # a sent command must show in the counters within this long
    effect_window_s: float = 10.0       # ... and its effect in telemetry within this long, both counted from sending
    link_timeout_factor: float = 3.0    # no telemetry for this many Housekeeping periods = link lost


def _limit_text(p: TelemetryParameter, severity: str, value: float) -> str:
    low, high = p.critical if severity == "CRITICAL" else p.warning
    level = severity.lower()
    if low is not None and value < low:
        return f"below {level} minimum {low:g}"
    return f"above {level} maximum {high:g}"


class AutomationEngine:
    """Reacts to telemetry and to the passing of time. ``on_telemetry`` and ``tick`` may be called from different threads."""

    def __init__(self, spec: Spec, runner: ActionRunner, connect: Callable, system_operator: str = "automation",
                 clock: Callable[[], datetime] = utcnow, config: Optional[AutomationConfig] = None,
                 log: Optional[Callable[[str], None]] = None):
        self.spec = spec
        self.runner = runner
        self.defs = runner.definitions
        self.operator = system_operator
        self.clock = clock
        self.config = config or AutomationConfig()
        self.log = log or (lambda message: None)
        self._db = SharedConnection(connect)
        self._link_lost = set()
        self._lock = threading.Lock()

    def close(self) -> None:
        self._db.close()

    # ---------------------------------------------------------------------------------------------- helpers
    def _act(self, results: List[ActionResult], action: str, cid, **params) -> Optional[ActionResult]:
        """Run one action as the system. A refusal is already audited by the runner; it must not stop the pipeline."""
        try:
            result = self.runner.run(self.operator, action, params, correlation_id=cid)
        except ActionError as exc:
            self.log(f"automation: '{action}' was refused: {exc}")
            return None
        results.append(result)
        shown = {k: v for k, v in params.items() if k not in ("spacecraft_id", "occurred_at") and v not in ({}, [])}
        detail = ", ".join(f"{k}={round(v, 3) if isinstance(v, float) else v}" for k, v in shown.items())
        self.log(f"automation: {action} {detail}")
        return result

    def _query(self, query: str, params=()):
        with self._db as conn:
            return conn.execute(query, params).fetchall()

    @staticmethod
    def _sc_datetime(sc_time_ms: int) -> datetime:
        return datetime.fromtimestamp(sc_time_ms / 1000.0, tz=timezone.utc)

    # ---------------------------------------------------------------------------------------------- telemetry
    def on_telemetry(self, result: IngestResult) -> List[ActionResult]:
        if result.duplicate:
            return []
        with self._lock:
            return self._on_telemetry(result)

    def _on_telemetry(self, result: IngestResult) -> List[ActionResult]:
        sc, cid, out = result.spacecraft_id, uuid.uuid4(), []
        current = result.current
        if sc in self._link_lost:
            self._link_lost.discard(sc)
            self._act(out, "Record Spacecraft Event", cid, spacecraft_id=sc, event_type="LINK_RESTORED",
                      occurred_at=result.received_at.isoformat(), details={})
        if result.lost:
            self._act(out, "Record Spacecraft Event", cid, spacecraft_id=sc, event_type="PACKET_LOSS",
                      occurred_at=self._sc_datetime(result.sc_time_ms).isoformat(),
                      details={"apid": result.apid, "lost": result.lost, "seq_count": result.seq_count})
        if result.out_of_order:
            return out                                                  # old news: it must not change state or raise alarms

        fdir_events = []
        for event in derive_events(self.spec, result.previous, current):
            params = {}
            if event.command_id is not None:
                rows = self._query("SELECT execution_id FROM ops.command_execution WHERE spacecraft_id = %s "
                                   "AND command_id = %s AND status IN ('SENT', 'ACCEPTED') ORDER BY sent_at DESC LIMIT 1",
                                   (sc, event.command_id))
                if rows:
                    params["caused_by_execution_id"] = str(rows[0]["execution_id"])
            done = self._act(out, "Record Spacecraft Event", cid, spacecraft_id=sc, event_type=event.event_type,
                             occurred_at=self._sc_datetime(result.sc_time_ms).isoformat(), details=event.details, **params)
            if done and event.unplanned_safe:
                fdir_events.append(done.result["event_id"])

        self._alarms(sc, result.values, cid, out)
        if fdir_events:
            free_alarms = [str(r["alarm_id"]) for r in self._query(
                "SELECT alarm_id FROM ops.alarm WHERE spacecraft_id = %s AND state <> 'CLEARED' AND anomaly_id IS NULL",
                (sc,))]
            self._act(out, "Open Anomaly", cid, spacecraft_id=sc, title="Unplanned SAFE mode", severity="HIGH",
                      alarm_ids=free_alarms, event_ids=fdir_events)
        self._verify(sc, current, cid, out)
        self._health(sc, current, cid, out)
        return out

    def _alarms(self, sc: str, values, cid, out: List[ActionResult]) -> None:
        open_alarms = {r["parameter_name"]: r for r in self._query(
            "SELECT alarm_id, parameter_name, severity FROM ops.alarm WHERE spacecraft_id = %s AND state <> 'CLEARED'",
            (sc,))}
        for name, value in values.items():
            p = self.defs.parameter(name)
            if (p.warning is None and p.critical is None) or not math.isfinite(value):
                continue
            severity, existing = p.severity_of(value), open_alarms.get(name)
            if severity is None:
                if existing:
                    self._act(out, "Clear Alarm", cid, alarm_id=str(existing["alarm_id"]))
            elif existing is None:
                self._act(out, "Raise Alarm", cid, spacecraft_id=sc, parameter_name=name, severity=severity,
                          trigger_value=value, limit_violated=_limit_text(p, severity, value))
            elif existing["severity"] != severity:
                self._act(out, "Update Alarm", cid, alarm_id=str(existing["alarm_id"]), severity=severity,
                          trigger_value=value, limit_violated=_limit_text(p, severity, value))

    def _health(self, sc: str, current, cid, out: List[ActionResult]) -> None:
        severities = [r["severity"] for r in self._query(
            "SELECT severity FROM ops.alarm WHERE spacecraft_id = %s AND state <> 'CLEARED'", (sc,))]
        wanted = health_status(self.spec, current.get("mode"), severities)
        (row,) = self._query("SELECT health_status FROM ops.spacecraft WHERE spacecraft_id = %s", (sc,))
        if row["health_status"] != wanted:
            self._act(out, "Set Health Status", cid, spacecraft_id=sc, health_status=wanted)

    def _verify(self, sc: str, current, cid, out: List[ActionResult]) -> None:
        """Follow commands on their way: the counters say if the satellite took them, telemetry if they worked."""
        for row in self._query("SELECT execution_id, command_name, status, send_baseline, expected_effect "
                               "FROM ops.command_execution WHERE spacecraft_id = %s AND status IN ('SENT', 'ACCEPTED') "
                               "ORDER BY sent_at", (sc,)):
            eid, status = str(row["execution_id"]), row["status"]
            baseline = row["send_baseline"]
            if status == "SENT":
                signal = command_signal(self.spec, row["command_name"], baseline, current)
                if signal == "REJECTED":
                    self._act(out, "Record Command Outcome", cid, execution_id=eid, outcome="REJECTED_ONBOARD",
                              reason="rejected on board: the rejected-commands counter rose (the satellite's own log "
                                     "has the reason)")
                    continue
                if signal != "ACCEPTED" or not self._act(out, "Record Command Outcome", cid, execution_id=eid,
                                                         outcome="ACCEPTED"):
                    continue
            if effects_met(row["expected_effect"], baseline, current):
                self._act(out, "Record Command Outcome", cid, execution_id=eid, outcome="VERIFIED")

    # ---------------------------------------------------------------------------------------------- time
    def tick(self, spacecraft_id: str) -> List[ActionResult]:
        """Things that happen because time passed rather than because telemetry arrived."""
        with self._lock:
            return self._tick(spacecraft_id)

    def _tick(self, sc: str) -> List[ActionResult]:
        now, cid, out = self.clock(), uuid.uuid4(), []
        cfg = self.config
        for row in self._query("SELECT execution_id, command_name, status, sent_at, arguments "
                               "FROM ops.command_execution WHERE spacecraft_id = %s AND status IN ('SENT', 'ACCEPTED')",
                               (sc,)):
            age = (now - row["sent_at"]).total_seconds()
            slow = 3.0 * float(row["arguments"].get("period_s", 0))          # SetTmRate slows the very telemetry we watch
            if row["status"] == "SENT" and age > max(cfg.accept_window_s, slow):
                reason = f"no sign of the command in the telemetry within {max(cfg.accept_window_s, slow):g} s of sending"
            elif row["status"] == "ACCEPTED" and age > max(cfg.effect_window_s, slow):
                reason = f"the satellite accepted it but the expected effect did not show within {cfg.effect_window_s:g} s"
            else:
                continue
            self._act(out, "Record Command Outcome", cid, execution_id=str(row["execution_id"]), outcome="FAILED",
                      reason=reason)
        for row in self._query("SELECT execution_id FROM ops.command_execution WHERE spacecraft_id = %s "
                               "AND status IN ('PROPOSED', 'APPROVED') AND expires_at <= %s", (sc, now)):
            self._act(out, "Cancel Command", cid, execution_id=str(row["execution_id"]),
                      reason="expired without being released")
        (contact,) = self._query("SELECT last_contact_at FROM ops.spacecraft WHERE spacecraft_id = %s", (sc,))
        last = contact["last_contact_at"]
        silence = (now - last).total_seconds() if last else None
        if silence is not None and silence > cfg.link_timeout_factor * telemetry_period_s(self.spec) \
                and sc not in self._link_lost:
            self._link_lost.add(sc)
            self._act(out, "Record Spacecraft Event", cid, spacecraft_id=sc, event_type="LINK_LOST",
                      occurred_at=now.isoformat(), details={"silent_for_s": round(silence, 1)})
        return out
