"""Functions of the ontology (ontology.md section 4): logic over spacecraft state that does not touch the database.

Everything here is a pure function of its arguments, so it is tested without a database. The MiniSat-specific knowledge
(which telemetry shows that a command worked, what counts as an unplanned SAFE mode) lives in this one module, in the
same way the on-board rules live in model.py. ``preflight_command`` does not copy those rules: it replays the command
on a throw-away copy of the satellite model, so the prediction can never drift from what the satellite does.
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Dict, List, Mapping, Optional, Tuple

from ..model import MODE_SAFE, SOC_FDIR, Orbit, Spacecraft
from ..spec import Spec

__all__ = ["Preflight", "preflight_command", "expected_effect", "effects_met", "command_signal", "DerivedEvent",
           "derive_events", "health_status", "SequenceTracker", "telemetry_period_s", "mode_label", "TimeToSafe",
           "estimate_time_to_safe"]

# telemetry names used below (all from spec/minisat.yaml)
MODE, CMD_ACCEPTED, CMD_REJECTED, LAST_CMD_ID = "mode", "cmd_accepted", "cmd_rejected", "last_cmd_id"
UPTIME, SOC, HEATER, ECLIPSE = "uptime_s", "battery_soc_pct", "heater", "in_eclipse"


def telemetry_period_s(spec: Spec) -> float:
    """The nominal period of the Housekeeping packet; how fresh "the latest state" can be expected to be."""
    return spec.tm_by_name("Housekeeping").period_s


def mode_label(spec: Spec, value) -> Optional[str]:
    for label, v in spec.enums["Mode"].items():
        if v == value:
            return label
    return None


# ------------------------------------------------------------------------------------------------ preflight

@dataclass(frozen=True)
class Preflight:
    """Would the spacecraft accept this command if it arrived now?"""
    known: bool                      # False when there is no telemetry to judge by
    accepted: Optional[bool]         # the model's verdict (None when unknown)
    reason: Optional[str]            # why it would be refused
    state_age_s: Optional[float]     # age of the newest telemetry
    stale: bool                      # older than a few telemetry periods (or never received)

    @property
    def predicts_rejection(self) -> bool:
        return self.known and self.accepted is False

    def to_dict(self) -> dict:
        return asdict(self)


def preflight_command(spec: Spec, latest_values: Mapping, command_name: str, args: Mapping, *,
                      last_contact_at: Optional[datetime], now: datetime, stale_factor: float = 3.0) -> Preflight:
    age = (now - last_contact_at).total_seconds() if last_contact_at else None
    stale = age is None or age > stale_factor * telemetry_period_s(spec)
    if not all(k in latest_values for k in (MODE, SOC, HEATER)):
        return Preflight(False, None, "no telemetry received yet", age, True)
    try:
        twin = Spacecraft(soc=latest_values[SOC] / 100.0, mode=int(latest_values[MODE]),
                          heater=bool(latest_values[HEATER]))
    except KeyError:                                   # a mode value the model does not know
        return Preflight(False, None, f"unknown mode {latest_values[MODE]!r} in telemetry", age, True)
    accepted, reason = twin.handle_command(spec.command_by_name(command_name), dict(args))
    return Preflight(True, accepted, None if accepted else reason, age, stale)


# ------------------------------------------------------------------------------------------------ time to safe mode

@dataclass(frozen=True)
class TimeToSafe:
    """When would the on-board protection (FDIR) put the spacecraft into SAFE mode, if nothing else is done?"""
    known: bool                         # False when there is no telemetry to start from
    reaches_safe: bool                  # SAFE mode is reached within the horizon
    seconds: Optional[float]            # from now until then (0 when already SAFE); None when not reached or unknown
    horizon_s: float                    # how far ahead the estimate looked
    min_soc_pct: Optional[float]        # lowest charge seen over the horizon (or until SAFE mode)
    command_accepted: Optional[bool]    # the verdict on the hypothetical command, when one was given
    phase_known: bool                   # the eclipse schedule was aligned with an eclipse transition seen in telemetry
    assumptions: Tuple[str, ...]        # what the estimate takes for granted; show these next to the number

    def to_dict(self) -> dict:
        data = asdict(self)
        data["assumptions"] = list(self.assumptions)
        return data


def _eclipse_transition_time(orbit: Orbit, entering: bool) -> float:
    """Model time within one lap at which the satellite enters (or leaves) the Earth's shadow, to 1 s."""
    period = int(orbit.period_s)
    previous = orbit.in_eclipse(period - 1.0)
    for t in range(period):
        now = orbit.in_eclipse(float(t))
        if now != previous and now == entering:
            return float(t)
        previous = now
    raise ValueError("the orbit has no eclipse" if entering else "the orbit is always in eclipse")


def estimate_time_to_safe(spec: Spec, latest_values: Mapping, *, command_name: Optional[str] = None,
                          args: Optional[Mapping] = None, eclipse_transition: Optional[Tuple[bool, float]] = None,
                          horizon_s: float = 6 * 3600.0, step_s: float = 5.0, orbit: Optional[Orbit] = None
                          ) -> TimeToSafe:
    """Replay the satellite's own power model forward from the newest telemetry until FDIR would force SAFE mode.

    Like :func:`preflight_command` this runs a throw-away copy of the satellite model, so the answer follows the on-board
    rules instead of a copy of them. With ``command_name`` it answers "if I send this now" (a command the model would
    refuse changes nothing, and ``command_accepted`` says so).

    Where the satellite is on its orbit decides whether the next minutes are sunlit, so ``eclipse_transition`` says what
    telemetry showed last: ``(True, s)`` = the eclipse began ``s`` seconds ago, ``(False, s)`` = sunlight did. Without it
    (or when it contradicts ``in_eclipse``) the estimate assumes the worst case: an eclipse is just starting.
    The model's solar wobble (a made-up 8-minute cycle) cannot be aligned from telemetry, so the number is approximate.
    """
    needed = (MODE, SOC, HEATER)
    if not all(k in latest_values for k in needed):
        return TimeToSafe(False, False, None, horizon_s, None, None, False, ("no telemetry received yet",))
    orbit = orbit or Orbit()
    assumptions = ["the power model of the satellite (model.py) is a good description of the real battery",
                   "the solar-array wobble cannot be seen from telemetry, so its phase is not aligned"]
    eclipsed = latest_values.get(ECLIPSE)
    consistent = eclipse_transition is not None and (eclipsed is None or bool(eclipsed) == eclipse_transition[0])
    if consistent:
        entering, elapsed = eclipse_transition
        t_start = _eclipse_transition_time(orbit, entering) + max(0.0, elapsed)
    else:
        t_start = _eclipse_transition_time(orbit, True)
        assumptions.append("no eclipse transition was seen in the telemetry, so the worst case is assumed: "
                           "an eclipse is just starting")
    try:
        twin = Spacecraft(orbit=orbit, soc=latest_values[SOC] / 100.0, mode=int(latest_values[MODE]),
                          heater=bool(latest_values[HEATER]), t=t_start)
    except KeyError:
        return TimeToSafe(False, False, None, horizon_s, None, None, consistent,
                          (f"unknown mode {latest_values[MODE]!r} in telemetry",))
    accepted = None
    if command_name is not None:
        accepted, reason = twin.handle_command(spec.command_by_name(command_name), dict(args or {}))
        if not accepted:
            assumptions.append(f"the command would be refused ({reason}), so the estimate is for the state as it is now")
    if twin.mode == MODE_SAFE or twin.soc < SOC_FDIR:
        return TimeToSafe(True, True, 0.0, horizon_s, round(twin.soc * 100.0, 2), accepted, consistent, tuple(assumptions))

    lowest, elapsed_s = twin.soc, 0.0
    while elapsed_s < horizon_s:
        twin.step(step_s)
        elapsed_s += step_s
        lowest = min(lowest, twin.soc)
        if twin.mode == MODE_SAFE:
            return TimeToSafe(True, True, elapsed_s, horizon_s, round(lowest * 100.0, 2), accepted, consistent,
                              tuple(assumptions))
    return TimeToSafe(True, False, None, horizon_s, round(lowest * 100.0, 2), accepted, consistent, tuple(assumptions))


# ------------------------------------------------------------------------------------------------ verification

def expected_effect(spec: Spec, command_name: str, args: Mapping) -> List[dict]:
    """What telemetry must show once the command has taken effect, as ``{"parameter", "op", "value"}`` checks.

    Commands whose only visible effect is the acceptance counter (Noop, SetTmRate) have none.
    """
    if command_name == "SetMode":
        return [{"parameter": MODE, "op": "eq", "value": args["mode"]}]
    if command_name == "SetHeater":
        return [{"parameter": HEATER, "op": "eq", "value": args["state"]}]
    if command_name == "Reboot":
        return [{"parameter": UPTIME, "op": "decreases"}, {"parameter": MODE, "op": "eq", "value": 0}]
    return []


def effects_met(effects: List[dict], baseline: Mapping, current: Mapping) -> bool:
    """Do the ``current`` values satisfy every check? A missing value counts as not met."""
    for e in effects:
        name = e["parameter"]
        if name not in current:
            return False
        if e["op"] == "eq" and current[name] != e["value"]:
            return False
        if e["op"] == "decreases" and not (name in baseline and current[name] < baseline[name]):
            return False
        if e["op"] == "increases" and not (name in baseline and current[name] > baseline[name]):
            return False
    return True


def command_signal(spec: Spec, command_name: str, baseline: Mapping, current: Mapping) -> Optional[str]:
    """What the counters say happened to a command sent when telemetry looked like ``baseline``:
    ``"ACCEPTED"``, ``"REJECTED"`` or ``None`` (nothing yet).

    The satellite only reports counters and the id of its latest command, so this is sound only while one command is
    in flight at a time (the runner enforces that). A reboot wipes the counters, so it is recognised by the uptime.
    """
    if command_name == "Reboot":
        return "ACCEPTED" if current.get(UPTIME, math.inf) < baseline.get(UPTIME, -math.inf) else None
    cmd_id = spec.command_by_name(command_name).id
    if current.get(LAST_CMD_ID) != cmd_id:
        return None
    if current.get(CMD_REJECTED, 0) > baseline.get(CMD_REJECTED, 0):
        return "REJECTED"
    if current.get(CMD_ACCEPTED, 0) > baseline.get(CMD_ACCEPTED, 0):
        return "ACCEPTED"
    return None


# ------------------------------------------------------------------------------------------------ events

@dataclass(frozen=True)
class DerivedEvent:
    event_type: str
    details: dict = field(default_factory=dict)
    unplanned_safe: bool = False            # the spacecraft protected itself: nobody commanded SAFE mode
    command_id: Optional[int] = None        # the command a COMMAND_ACCEPTED / COMMAND_REJECTED event is about


def derive_events(spec: Spec, previous: Mapping, new: Mapping) -> List[DerivedEvent]:
    """What changed between two states of the spacecraft. Nothing is derived without a previous state."""
    if not previous:
        return []

    def rose(name):
        return name in previous and name in new and new[name] > previous[name]

    events: List[DerivedEvent] = []
    rebooted = UPTIME in previous and UPTIME in new and new[UPTIME] < previous[UPTIME]
    if rebooted:
        events.append(DerivedEvent("REBOOT", {"uptime_before_s": previous[UPTIME]}))
    elif MODE in previous and MODE in new and previous[MODE] != new[MODE]:
        events.append(DerivedEvent("MODE_CHANGE", {"from": mode_label(spec, previous[MODE]),
                                                   "to": mode_label(spec, new[MODE])}))
        # SAFE mode that no accepted SetMode explains is the on-board protection (FDIR) acting
        commanded = rose(CMD_ACCEPTED) and new.get(LAST_CMD_ID) == spec.command_by_name("SetMode").id
        if mode_label(spec, new[MODE]) == "SAFE" and not commanded:
            events.append(DerivedEvent("FDIR", {"battery_soc_pct": new.get(SOC)}, unplanned_safe=True))
    if not rebooted:
        if rose(CMD_ACCEPTED):
            events.append(DerivedEvent("COMMAND_ACCEPTED", {"last_cmd_id": new.get(LAST_CMD_ID),
                                                            "count": new[CMD_ACCEPTED] - previous[CMD_ACCEPTED]},
                                       command_id=new.get(LAST_CMD_ID)))
        if rose(CMD_REJECTED):
            events.append(DerivedEvent("COMMAND_REJECTED", {"last_cmd_id": new.get(LAST_CMD_ID),
                                                            "count": new[CMD_REJECTED] - previous[CMD_REJECTED]},
                                       command_id=new.get(LAST_CMD_ID)))
    if ECLIPSE in previous and ECLIPSE in new and previous[ECLIPSE] != new[ECLIPSE]:
        events.append(DerivedEvent("ECLIPSE_ENTRY" if new[ECLIPSE] else "ECLIPSE_EXIT"))
    return events


# ------------------------------------------------------------------------------------------------ health

def health_status(spec: Spec, mode_value, open_alarm_severities) -> str:
    """NOMINAL, WARNING, CRITICAL or SAFE_MODE. A spacecraft in SAFE mode is reported as such even when alarms are open:
    it is the more specific fact (the satellite is protecting itself)."""
    if mode_value is not None and mode_label(spec, mode_value) == "SAFE":
        return "SAFE_MODE"
    severities = set(open_alarm_severities)
    if "CRITICAL" in severities:
        return "CRITICAL"
    if "WARNING" in severities:
        return "WARNING"
    return "NOMINAL"


# ------------------------------------------------------------------------------------------------ link quality

class SequenceTracker:
    """Counts lost packets from the 14-bit CCSDS sequence counter, per APID (roadmap M3)."""

    MODULUS = 1 << 14

    def __init__(self):
        self._last: Dict[int, int] = {}

    def update(self, apid: int, seq_count: int) -> int:
        """How many packets are missing between the previous packet of this APID and this one.

        A duplicate or a late packet (the counter appears to go back) counts as zero lost, not as 16383.
        """
        last = self._last.get(apid)
        if last is None:
            self._last[apid] = seq_count
            return 0
        gap = (seq_count - last - 1) % self.MODULUS
        if gap >= self.MODULUS // 2:               # not newer than what we have: keep waiting for the real next packet
            return 0
        self._last[apid] = seq_count
        return gap
