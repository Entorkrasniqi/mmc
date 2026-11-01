"""estimate_time_to_safe (ontology.md section 4): when would FDIR put the spacecraft into SAFE mode?

Two kinds of expected value, neither taken from the function under test: numbers worked out on paper from the model's
constants (4 Ah battery, load per mode, FDIR at 15 %), and the *real* satellite model run forward second by second
from the same state, which is what the estimate is a prediction of. No database.
"""
import pytest

from minisat.model import MODE_SAFE, Orbit, Spacecraft
from minisat.ontology.functions import estimate_time_to_safe

ORBIT = Orbit()
PERIOD = ORBIT.period_s                      # 5751.4 s; the eclipse lasts 2084.5 s (130.5 degrees of the lap)
AMPERE_SECONDS_PER_PERCENT = 4.0 * 3600.0 / 100.0         # 4 Ah battery: 144 A.s move the charge by one percent

NOMINAL, PAYLOAD = 1, 2


def state(soc_pct, mode=NOMINAL, heater=0, in_eclipse=1):
    return {"mode": mode, "battery_soc_pct": soc_pct, "heater": heater, "in_eclipse": in_eclipse}


def tts(spec, values, transition=(True, 0.0), **kw):
    return estimate_time_to_safe(spec, values, eclipse_transition=transition, **kw)


# ------------------------------------------------------------------------------------------------ worked out on paper

@pytest.mark.parametrize("values, amps, from_pct", [
    (state(20.0), 0.45, 20.0),                                    # NOMINAL load
    (state(30.0, mode=PAYLOAD), 1.10, 30.0),                      # PAYLOAD load
    (state(20.0, heater=1), 0.45 + 0.35, 20.0),                   # NOMINAL plus the heater
])
def test_a_drain_that_fits_inside_the_eclipse_is_charge_over_current(spec, values, amps, from_pct):
    """No sunlight to help: seconds = (charge above 15 %) * 144 A.s per percent / load. 1600 s, 1963.6 s and 900 s."""
    expected = (from_pct - 15.0) * AMPERE_SECONDS_PER_PERCENT / amps
    result = tts(spec, values)
    assert result.known and result.reaches_safe and result.phase_known
    assert result.seconds == pytest.approx(expected, abs=6.0)         # steps of 5 s, and the eclipse starts within 1 s
    assert result.min_soc_pct < 15.0 + 0.1


def test_the_hand_computed_values_are_what_the_comments_say():
    assert (20.0 - 15.0) * AMPERE_SECONDS_PER_PERCENT / 0.45 == pytest.approx(1600.0)
    assert (30.0 - 15.0) * AMPERE_SECONDS_PER_PERCENT / 1.10 == pytest.approx(1963.64, abs=0.01)
    assert (20.0 - 15.0) * AMPERE_SECONDS_PER_PERCENT / 0.80 == pytest.approx(900.0)


def test_an_eclipse_that_ends_before_the_battery_does_means_no_safe_mode(spec):
    """Eclipse began 1900 s ago, 184.5 s left at 0.45 A: the charge only falls by 184.5 * 0.45 / 144 = 0.58 points."""
    result = tts(spec, state(20.0), transition=(True, 1900.0))
    assert result.known and not result.reaches_safe and result.seconds is None
    assert result.min_soc_pct == pytest.approx(20.0 - (2084.5 - 1900.0) * 0.45 / AMPERE_SECONDS_PER_PERCENT, abs=0.1)


def test_a_charging_spacecraft_in_sunlight_never_gets_there(spec):
    result = tts(spec, state(90.0, in_eclipse=0), transition=(False, 100.0))
    assert result.known and not result.reaches_safe and result.seconds is None
    assert result.min_soc_pct > 80.0


def test_the_horizon_limits_how_far_ahead_it_looks(spec):
    assert tts(spec, state(20.0), horizon_s=1000.0).reaches_safe is False          # would need 1600 s
    assert tts(spec, state(20.0), horizon_s=1700.0).reaches_safe is True
    assert tts(spec, state(20.0), horizon_s=1000.0).horizon_s == 1000.0


# ------------------------------------------------------------------------------------------------ against the real model

def run_the_real_satellite(t0, soc, mode, heater, limit_s=6 * 3600):
    """Seconds until the real model's own FDIR puts it into SAFE mode (None: not within the limit), stepping 1 s."""
    satellite = Spacecraft(orbit=ORBIT, soc=soc, mode=mode, heater=bool(heater), t=t0)
    for second in range(1, limit_s + 1):
        satellite.step(1.0)
        if satellite.mode == MODE_SAFE:
            return second
    return None


def what_telemetry_shows(t0):
    """What the ground would have seen at model time t0: the eclipse flag, and how long ago it last changed."""
    eclipsed, ago = ORBIT.in_eclipse(t0), 1
    while ORBIT.in_eclipse(t0 - ago) == eclipsed:
        ago += 1
    return eclipsed, float(ago)


LAPS = [0, 1, 3, 20]                  # later laps do not line up with the model's 8-minute solar wobble: the realistic case
STARTS = [200.0, 1900.0, 2500.0, 3900.0, 4500.0, 5600.0]
CASES = [(0.20, NOMINAL, 0), (0.30, PAYLOAD, 0), (0.50, PAYLOAD, 1), (0.18, NOMINAL, 1), (0.45, PAYLOAD, 0)]

# Measured over exactly these 120 starts (not guessed): lap 0, where the estimate's solar wobble happens to line up with the
# satellite's, is within 12 s; the worst of all laps is 142 s on a 7092 s prediction (2.0 %) and 2.7 % at its worst relative
# point. The wobble is the whole difference (see the test below), so the bound for the other laps is 15 s plus 3 %.
TIGHT = {0: (10.0, 0.01), 1: (10.0, 0.01), 3: (15.0, 0.03), 20: (15.0, 0.03)}


@pytest.mark.parametrize("lap", LAPS)
def test_the_estimate_follows_the_real_satellite_from_any_point_of_the_orbit(spec, lap):
    """Whether SAFE mode is reached at all must always agree; when it is, the time must be close."""
    absolute, relative = TIGHT[lap]
    for start in STARTS:
        t0 = start + lap * PERIOD
        eclipsed, ago = what_telemetry_shows(t0)
        for soc, mode, heater in CASES:
            truth = run_the_real_satellite(t0, soc, mode, heater)
            values = state(soc * 100.0, mode, heater, in_eclipse=int(eclipsed))
            result = tts(spec, values, transition=(eclipsed, ago))
            where = f"t0={t0:.0f} soc={soc} mode={mode} heater={heater}"
            assert result.reaches_safe == (truth is not None), where
            if truth is not None:
                assert result.seconds == pytest.approx(truth, abs=absolute + relative * truth), where


def test_the_real_satellite_itself_answers_differently_on_different_laps_so_the_estimate_cannot_be_exact():
    """Same orbit phase, same charge, same mode: only the solar wobble (period 480 s, which does not divide the 5751 s lap)
    differs, and the real model reaches SAFE mode 154 s apart. That is the floor under any estimate made from telemetry."""
    first = run_the_real_satellite(200.0, 0.50, PAYLOAD, 1)
    later = run_the_real_satellite(200.0 + 20 * PERIOD, 0.50, PAYLOAD, 1)
    assert (first, later) == (6938, 7092)


# ------------------------------------------------------------------------------------------------ a command that has not been sent

def test_with_a_command_the_estimate_answers_if_i_send_this_now(spec):
    """From 40 % in sunlight: NOMINAL never gets there; PAYLOAD (1.10 A against about 1.04 A of sun) eventually does."""
    sunlit = state(40.0, in_eclipse=0)
    now = tts(spec, sunlit, transition=(False, 600.0))
    payload = tts(spec, sunlit, transition=(False, 600.0), command_name="SetMode", args={"mode": PAYLOAD})
    assert not now.reaches_safe and now.command_accepted is None
    assert payload.command_accepted is True and payload.reaches_safe and payload.seconds > 3600.0


def test_a_command_the_satellite_would_refuse_changes_nothing(spec):
    low = state(20.0)
    plain = tts(spec, low)
    refused = tts(spec, low, command_name="SetMode", args={"mode": PAYLOAD})          # PAYLOAD needs 30 %
    assert refused.command_accepted is False
    assert refused.seconds == plain.seconds
    assert any("battery too low for PAYLOAD" in a for a in refused.assumptions)


def test_a_command_that_reboots_into_safe_mode_means_zero_seconds(spec):
    result = tts(spec, state(80.0), command_name="Reboot", args={})
    assert result.reaches_safe and result.seconds == 0.0 and result.command_accepted is True


def test_turning_the_heater_on_shortens_the_time(spec):
    plain = tts(spec, state(20.0))
    warm = tts(spec, state(20.0), command_name="SetHeater", args={"state": 1})
    assert warm.command_accepted is True and warm.seconds == pytest.approx(900.0, abs=6.0)
    assert warm.seconds < plain.seconds


# ------------------------------------------------------------------------------------------------ what it does not know

def test_already_in_safe_mode_or_already_below_the_limit_is_zero_seconds(spec):
    assert tts(spec, state(50.0, mode=0)).seconds == 0.0
    assert tts(spec, state(14.9)).seconds == 0.0
    assert tts(spec, state(15.0)).seconds > 0.0                      # FDIR acts below 15 %, not at it


def test_without_a_seen_eclipse_transition_it_assumes_the_worst_case_and_says_so(spec):
    unknown = estimate_time_to_safe(spec, state(20.0))
    worst = tts(spec, state(20.0), transition=(True, 0.0))
    assert not unknown.phase_known and worst.phase_known
    assert unknown.seconds == worst.seconds == pytest.approx(1600.0, abs=6.0)
    assert any("worst case" in a for a in unknown.assumptions) and not any("worst case" in a for a in worst.assumptions)


def test_a_transition_that_contradicts_the_eclipse_flag_is_not_trusted(spec):
    result = tts(spec, state(20.0, in_eclipse=0), transition=(True, 50.0))
    assert not result.phase_known and any("worst case" in a for a in result.assumptions)


def test_without_usable_telemetry_it_says_it_does_not_know(spec):
    for values in ({}, {"mode": 1}, {"mode": 1, "battery_soc_pct": 50.0}):
        result = estimate_time_to_safe(spec, values)
        assert (result.known, result.reaches_safe, result.seconds) == (False, False, None) and result.assumptions
    unknown_mode = estimate_time_to_safe(spec, state(50.0, mode=9))
    assert (unknown_mode.known, unknown_mode.seconds) == (False, None) and "unknown mode" in unknown_mode.assumptions[0]


def test_it_does_not_change_what_it_was_given_and_its_dict_is_json_ready(spec):
    import json
    values = state(20.0)
    snapshot = dict(values)
    result = tts(spec, values, command_name="SetHeater", args={"state": 1})
    assert values == snapshot
    assert json.loads(json.dumps(result.to_dict()))["assumptions"] == list(result.assumptions)
