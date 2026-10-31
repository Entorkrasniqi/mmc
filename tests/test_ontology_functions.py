"""The ontology's pure functions (src/minisat/ontology/functions.py). No database; expected values are worked out by hand."""
from datetime import datetime, timedelta, timezone

import pytest

from minisat.ontology.functions import (SequenceTracker, command_signal, derive_events, effects_met, expected_effect,
                                        health_status, preflight_command)

NOW = datetime(2026, 10, 31, 12, 0, 0, tzinfo=timezone.utc)
STATE = {"mode": 1, "battery_soc_pct": 80.0, "heater": 0}


def pre(spec, command, args, state=STATE, age=1.0, **kw):
    return preflight_command(spec, state, command, args, last_contact_at=NOW - timedelta(seconds=age), now=NOW, **kw)


# ------------------------------------------------------------------------------------------------ preflight

@pytest.mark.parametrize("soc, accepted", [(29.9, False), (30.0, True), (80.0, True), (0.0, False)])
def test_payload_mode_is_refused_below_30_percent(spec, soc, accepted):
    result = pre(spec, "SetMode", {"mode": 2}, {**STATE, "battery_soc_pct": soc})
    assert result.known and result.accepted is accepted
    assert result.predicts_rejection is (not accepted)
    assert (result.reason is None) == accepted
    if not accepted:
        assert "battery too low for PAYLOAD" in result.reason


def test_only_payload_mode_depends_on_the_battery(spec):
    low = {**STATE, "battery_soc_pct": 5.0}
    assert pre(spec, "SetMode", {"mode": 1}, low).accepted and pre(spec, "SetMode", {"mode": 0}, low).accepted
    assert pre(spec, "Reboot", {}, low).accepted and pre(spec, "Noop", {}, low).accepted


def test_preflight_applies_the_range_check_of_set_tm_rate(spec):
    assert pre(spec, "SetTmRate", {"period_s": 30.0}).accepted is True
    refused = pre(spec, "SetTmRate", {"period_s": 500.0})
    assert refused.accepted is False and "outside [0.1, 60]" in refused.reason
    assert pre(spec, "SetTmRate", {"period_s": float("nan")}).accepted is False        # NaN fails every comparison


def test_preflight_does_not_change_anything_it_was_given(spec):
    state = dict(STATE)
    pre(spec, "SetMode", {"mode": 2}, state)
    assert state == STATE


def test_preflight_without_usable_telemetry_says_it_does_not_know(spec):
    for state in ({}, {"mode": 1}, {"mode": 9, "battery_soc_pct": 50.0, "heater": 0}):
        result = pre(spec, "Noop", {}, state)
        assert (result.known, result.accepted, result.stale) == (False, None, True) and result.reason
        assert not result.predicts_rejection


def test_state_is_stale_after_three_housekeeping_periods(spec):
    assert pre(spec, "Noop", {}, age=3.0).stale is False
    assert pre(spec, "Noop", {}, age=3.001).stale is True
    assert pre(spec, "Noop", {}, age=3.001, stale_factor=10).stale is False
    assert preflight_command(spec, STATE, "Noop", {}, last_contact_at=None, now=NOW).stale is True
    assert pre(spec, "Noop", {}, age=2.0).state_age_s == 2.0


# ------------------------------------------------------------------------------------------------ verification

def test_expected_effects_per_command(spec):
    assert expected_effect(spec, "SetMode", {"mode": 2}) == [{"parameter": "mode", "op": "eq", "value": 2}]
    assert expected_effect(spec, "SetHeater", {"state": 1}) == [{"parameter": "heater", "op": "eq", "value": 1}]
    assert expected_effect(spec, "Reboot", {}) == [{"parameter": "uptime_s", "op": "decreases"},
                                                   {"parameter": "mode", "op": "eq", "value": 0}]
    assert expected_effect(spec, "Noop", {}) == [] and expected_effect(spec, "SetTmRate", {"period_s": 5.0}) == []


def test_effects_are_checked_against_the_baseline_where_they_are_relative():
    eq = [{"parameter": "mode", "op": "eq", "value": 2}]
    assert effects_met(eq, {}, {"mode": 2}) and not effects_met(eq, {}, {"mode": 1})
    assert not effects_met(eq, {}, {})                                          # a missing value is not "met"
    down = [{"parameter": "uptime_s", "op": "decreases"}]
    assert effects_met(down, {"uptime_s": 40}, {"uptime_s": 5})
    assert not effects_met(down, {"uptime_s": 40}, {"uptime_s": 40})
    assert not effects_met(down, {}, {"uptime_s": 5})                           # no baseline to compare with
    up = [{"parameter": "load_current_a", "op": "increases"}]
    assert effects_met(up, {"load_current_a": 0.45}, {"load_current_a": 1.10})
    assert effects_met([], {}, {}) is True                                      # nothing to wait for


def test_the_counters_tell_whether_a_command_was_accepted_or_rejected(spec):
    base = {"cmd_accepted": 2, "cmd_rejected": 1, "last_cmd_id": 3}
    set_mode = 2                                                                # SetMode's command id
    assert command_signal(spec, "SetMode", base, {**base, "cmd_accepted": 3, "last_cmd_id": set_mode}) == "ACCEPTED"
    assert command_signal(spec, "SetMode", base, {**base, "cmd_rejected": 2, "last_cmd_id": set_mode}) == "REJECTED"
    assert command_signal(spec, "SetMode", base, base) is None
    # the counter rose but the satellite says its latest command was another one: not ours
    assert command_signal(spec, "SetMode", base, {**base, "cmd_accepted": 3, "last_cmd_id": 3}) is None
    assert command_signal(spec, "SetMode", base, {"cmd_accepted": 3}) is None


def test_a_reboot_is_recognised_by_the_uptime_because_it_wipes_the_counters(spec):
    base = {"uptime_s": 40, "cmd_accepted": 5}
    assert command_signal(spec, "Reboot", base, {"uptime_s": 1, "cmd_accepted": 0}) == "ACCEPTED"
    assert command_signal(spec, "Reboot", base, {"uptime_s": 41, "cmd_accepted": 5}) is None
    assert command_signal(spec, "Reboot", base, {}) is None


# ------------------------------------------------------------------------------------------------ events

PREV = {"mode": 1, "cmd_accepted": 2, "cmd_rejected": 0, "last_cmd_id": 3, "uptime_s": 100, "battery_soc_pct": 40.0,
        "in_eclipse": 0, "heater": 0}


def kinds(events):
    return [e.event_type for e in events]


def test_nothing_is_derived_without_a_previous_state_or_a_change(spec):
    assert derive_events(spec, {}, PREV) == []
    assert derive_events(spec, PREV, dict(PREV)) == []
    assert derive_events(spec, PREV, {"latitude_deg": 1.0, "longitude_deg": 2.0}) == []      # a Position packet


def test_an_unexplained_switch_to_safe_mode_is_the_onboard_protection(spec):
    events = derive_events(spec, PREV, {**PREV, "mode": 0, "battery_soc_pct": 14.9})
    assert kinds(events) == ["MODE_CHANGE", "FDIR"]
    assert events[0].details == {"from": "NOMINAL", "to": "SAFE"}
    assert events[1].unplanned_safe and events[1].details == {"battery_soc_pct": 14.9}
    assert not events[0].unplanned_safe


def test_safe_mode_after_an_accepted_set_mode_is_not_an_fdir_event(spec):
    new = {**PREV, "mode": 0, "cmd_accepted": 3, "last_cmd_id": 2}              # id 2 = SetMode
    events = derive_events(spec, PREV, new)
    assert kinds(events) == ["MODE_CHANGE", "COMMAND_ACCEPTED"]
    assert events[1].command_id == 2 and events[1].details == {"last_cmd_id": 2, "count": 1}
    assert not any(e.unplanned_safe for e in events)


def test_an_accepted_command_that_is_not_set_mode_does_not_explain_safe_mode(spec):
    new = {**PREV, "mode": 0, "cmd_accepted": 3, "last_cmd_id": 3}              # id 3 = SetHeater
    assert "FDIR" in kinds(derive_events(spec, PREV, new))


def test_other_mode_changes_are_plain_mode_changes(spec):
    events = derive_events(spec, PREV, {**PREV, "mode": 2})
    assert kinds(events) == ["MODE_CHANGE"] and events[0].details == {"from": "NOMINAL", "to": "PAYLOAD"}


def test_a_reboot_is_one_event_not_a_mode_change_plus_command_counters(spec):
    new = {**PREV, "uptime_s": 2, "mode": 0, "cmd_accepted": 0, "cmd_rejected": 0, "last_cmd_id": 0}
    events = derive_events(spec, PREV, new)
    assert kinds(events) == ["REBOOT"] and events[0].details == {"uptime_before_s": 100}


def test_rejected_commands_and_eclipses(spec):
    events = derive_events(spec, PREV, {**PREV, "cmd_rejected": 1, "last_cmd_id": 2})
    assert kinds(events) == ["COMMAND_REJECTED"] and events[0].command_id == 2
    assert kinds(derive_events(spec, PREV, {**PREV, "in_eclipse": 1})) == ["ECLIPSE_ENTRY"]
    assert kinds(derive_events(spec, {**PREV, "in_eclipse": 1}, PREV)) == ["ECLIPSE_EXIT"]


# ------------------------------------------------------------------------------------------------ health

@pytest.mark.parametrize("mode, severities, expected", [
    (1, [], "NOMINAL"), (1, ["WARNING"], "WARNING"), (2, ["WARNING", "CRITICAL"], "CRITICAL"),
    (0, [], "SAFE_MODE"), (0, ["CRITICAL"], "SAFE_MODE"), (None, ["WARNING"], "WARNING"), (None, [], "NOMINAL"),
])
def test_health_status(spec, mode, severities, expected):
    assert health_status(spec, mode, severities) == expected


# ------------------------------------------------------------------------------------------------ packet loss

def test_sequence_tracker_counts_missing_packets_per_apid():
    t = SequenceTracker()
    assert t.update(100, 5) == 0                         # the first packet has nothing to compare with
    assert t.update(100, 6) == 0
    assert t.update(100, 10) == 3                        # 7, 8 and 9 are missing
    assert t.update(101, 40) == 0                        # another APID has its own counter
    assert t.update(101, 41) == 0


def test_sequence_tracker_handles_the_14_bit_wrap():
    t = SequenceTracker()
    t.update(100, 16382)
    assert t.update(100, 16383) == 0
    assert t.update(100, 0) == 0                         # 16383 -> 0 is the next packet
    assert t.update(100, 3) == 2                         # 1 and 2 missing
    t2 = SequenceTracker()
    t2.update(100, 16382)
    assert t2.update(100, 1) == 2                        # 16383 and 0 missing, across the wrap


def test_a_duplicate_or_late_packet_is_not_a_huge_loss_and_does_not_confuse_the_count():
    t = SequenceTracker()
    for seq in (10, 11, 12):
        t.update(100, seq)
    assert t.update(100, 12) == 0                        # duplicate
    assert t.update(100, 9) == 0                         # late
    assert t.update(100, 13) == 0                        # the real next packet: nothing was lost
    assert t.update(100, 15) == 1
