import math

import pytest

from minisat.codec import decode_tc, encode_tc
from minisat.model import (MODE_NOMINAL, MODE_PAYLOAD, MODE_SAFE, R_EARTH, SOC_FDIR, SOC_PAYLOAD_MIN, Orbit,
                           Spacecraft)


def command(spec, sc, name, args=None, validate=True):
    """Encode a command exactly like the ground would, decode it like the satellite does, and execute it."""
    cmd, decoded, _ = decode_tc(spec, encode_tc(spec, name, args, validate=validate))
    return sc.handle_command(cmd, decoded)


# ------------------------------------------------------------------------------------------------ orbit

def test_orbital_period_is_about_96_minutes():
    # Kepler: 560 km altitude -> T = 2*pi*sqrt(a^3/mu); 95.9 minutes
    assert Orbit().period_s / 60 == pytest.approx(95.86, abs=0.05)


def test_period_grows_with_altitude():
    assert Orbit(altitude_km=800).period_s > Orbit(altitude_km=400).period_s


def test_ground_track_starts_at_the_ascending_node():
    lat, lon = Orbit().ground_point(0)
    assert lat == pytest.approx(0, abs=1e-9) and lon == pytest.approx(10.0)


def test_latitude_never_exceeds_the_supplement_of_the_inclination():
    orbit = Orbit()
    lats = [orbit.ground_point(k * 30.0)[0] for k in range(int(orbit.period_s / 30) + 1)]
    assert max(lats) == pytest.approx(180 - orbit.inclination_deg, abs=0.1)     # 82.4 degrees for a 97.6 degree orbit
    assert min(lats) == pytest.approx(-(180 - orbit.inclination_deg), abs=0.1)


def test_longitude_drifts_west_by_the_earth_rotation_each_lap():
    orbit = Orbit()
    lat, lon = orbit.ground_point(orbit.period_s)
    assert lat == pytest.approx(0, abs=1e-6)                       # back at the node latitude...
    shift = lon - 10.0                                             # ...but the Earth turned underneath
    assert shift == pytest.approx(-math.degrees(7.2921159e-5 * orbit.period_s), abs=0.01)   # about -24 degrees


def test_longitude_stays_in_range():
    orbit = Orbit()
    for k in range(0, 40000, 97):
        assert -180.0 <= orbit.ground_point(k)[1] < 180.0


def test_retrograde_orbit_moves_east_to_west_then_back_over_the_pole():
    # inclination > 90: right after the node the satellite heads north and WEST of its start longitude
    orbit = Orbit()
    assert orbit.ground_point(120)[0] > 0 and orbit.ground_point(120)[1] < 10.0


def test_eclipse_lasts_about_a_third_of_the_lap_and_flips_correctly():
    orbit = Orbit()
    assert 0.30 < orbit.eclipse_fraction() < 0.42
    assert not orbit.in_eclipse(0)                                              # sun phase 0 -> start in full sun
    assert orbit.in_eclipse(orbit.period_s / 2)                                 # opposite side of the Earth: night


def test_eclipse_gets_shorter_when_the_orbit_turns_toward_the_sun():
    # higher beta angle = orbit plane closer to the terminator = shorter eclipse; beyond a critical angle: none at all
    short = Orbit(beta_deg=60).eclipse_fraction()
    assert short < Orbit(beta_deg=0).eclipse_fraction()
    critical = math.degrees(math.asin(R_EARTH / Orbit().radius_km))             # ~67 degrees at this altitude
    assert Orbit(beta_deg=critical + 3).eclipse_fraction() == 0.0


# ------------------------------------------------------------------------------------------------ power balance

def run(sc, seconds, dt=1.0):
    for _ in range(int(seconds / dt)):
        sc.step(dt)


def test_battery_charges_in_sunlight_and_drains_in_eclipse():
    sc = Spacecraft(soc=0.5)
    run(sc, 600)                                              # first 10 minutes: sunlit
    assert not sc.orbit.in_eclipse(sc.t) and sc.soc > 0.5
    sc = Spacecraft(soc=0.5, t=Orbit().period_s / 2)         # start in the middle of the night
    run(sc, 600)
    assert sc.orbit.in_eclipse(sc.t) and sc.soc < 0.5


def test_battery_is_clamped_between_empty_and_full():
    full = Spacecraft(soc=1.0)
    run(full, 300)
    assert full.soc == 1.0
    empty = Spacecraft(soc=0.0, mode=MODE_PAYLOAD)
    empty.step(1.0)
    assert 0.0 <= empty.soc <= 1.0


def test_payload_mode_costs_more_power_than_nominal():
    a, b = Spacecraft(soc=0.8, mode=MODE_NOMINAL), Spacecraft(soc=0.8, mode=MODE_PAYLOAD)
    run(a, 3600), run(b, 3600)
    assert b.soc < a.soc and b.housekeeping()["load_current_a"] > a.housekeeping()["load_current_a"]


def test_heater_draws_current_and_warms_the_battery():
    cold, warm = Spacecraft(soc=0.8), Spacecraft(soc=0.8, heater=True)
    run(cold, 3000), run(warm, 3000)
    assert warm.temp_c > cold.temp_c + 5
    assert warm.housekeeping()["load_current_a"] > cold.housekeeping()["load_current_a"]


def test_voltage_follows_charge_and_stays_in_a_plausible_band():
    low, high = Spacecraft(soc=0.05), Spacecraft(soc=0.95)
    assert low.battery_voltage() < 6.8 < 8.0 < high.battery_voltage() <= 8.45
    sc = Spacecraft(soc=0.5)
    for _ in range(20000):
        sc.step(1.0)
        assert 5.5 < sc.battery_voltage() <= 8.45


def test_step_ignores_nonpositive_time():
    sc = Spacecraft()
    sc.step(0), sc.step(-5)
    assert sc.t == 0 and sc.uptime_s == 0


def test_model_is_deterministic_for_a_given_seed():
    a, b, c = Spacecraft(seed=3), Spacecraft(seed=3), Spacecraft(seed=4)
    for sc in (a, b, c):
        run(sc, 100)
    assert a.housekeeping() == b.housekeeping() != c.housekeeping()


def test_housekeeping_has_exactly_the_fields_of_the_specification(spec):
    assert set(Spacecraft().housekeeping()) == {f.name for f in spec.tm_by_name("Housekeeping").fields}
    assert set(Spacecraft().position()) == {f.name for f in spec.tm_by_name("Position").fields}


# ------------------------------------------------------------------------------------------------ FDIR

def test_protection_switches_to_safe_mode_when_the_battery_gets_too_empty():
    night = Orbit().period_s / 2
    sc = Spacecraft(soc=SOC_FDIR + 0.0001, mode=MODE_PAYLOAD, t=night)       # in the dark, PAYLOAD drains the battery
    assert sc.mode == MODE_PAYLOAD
    run(sc, 30)
    assert sc.soc < SOC_FDIR and sc.mode == MODE_SAFE and sc.fdir_events == 1
    run(sc, 30)
    assert sc.fdir_events == 1                                                # fires once, not on every step


def test_protection_acts_on_the_step_that_crosses_the_threshold():
    sc = Spacecraft(soc=SOC_FDIR - 0.01, mode=MODE_PAYLOAD)
    sc.step(1.0)
    assert sc.mode == MODE_SAFE


def test_protection_does_not_touch_a_healthy_satellite():
    sc = Spacecraft(soc=0.9, mode=MODE_PAYLOAD)
    run(sc, 120)
    assert sc.mode == MODE_PAYLOAD and sc.fdir_events == 0


# ------------------------------------------------------------------------------------------------ commands

def test_noop_counts_as_accepted(spec):
    sc = Spacecraft()
    assert command(spec, sc, "Noop") == (True, "ok")
    assert (sc.cmd_accepted, sc.cmd_rejected, sc.last_cmd_id) == (1, 0, 1)


def test_set_mode_changes_mode(spec):
    sc = Spacecraft(soc=0.9)
    assert command(spec, sc, "SetMode", {"mode": "PAYLOAD"})[0] and sc.mode == MODE_PAYLOAD
    assert command(spec, sc, "SetMode", {"mode": "SAFE"})[0] and sc.mode == MODE_SAFE


def test_payload_mode_is_refused_when_the_battery_is_low(spec):
    sc = Spacecraft(soc=SOC_PAYLOAD_MIN - 0.01)
    accepted, reason = command(spec, sc, "SetMode", {"mode": "PAYLOAD"})
    assert not accepted and "battery too low" in reason
    assert sc.mode == MODE_NOMINAL and (sc.cmd_accepted, sc.cmd_rejected, sc.last_cmd_id) == (0, 1, 2)
    sc.soc = SOC_PAYLOAD_MIN                                                  # exactly at the limit: allowed
    assert command(spec, sc, "SetMode", {"mode": "PAYLOAD"})[0]


def test_set_heater(spec):
    sc = Spacecraft()
    command(spec, sc, "SetHeater", {"state": "ON"})
    assert sc.heater and sc.housekeeping()["heater"] == 1
    command(spec, sc, "SetHeater", {"state": 0})
    assert not sc.heater


def test_set_tm_rate_accepts_valid_and_defends_itself_against_invalid_values(spec):
    sc = Spacecraft()
    assert command(spec, sc, "SetTmRate", {"period_s": 5.0})[0] and sc.hk_period_s == 5.0
    for bad in (0.05, 61.0, float("nan"), -1.0):
        # the ground tool would refuse these, so craft them on purpose: the satellite must not trust its input
        accepted, reason = command(spec, sc, "SetTmRate", {"period_s": bad}, validate=False)
        assert not accepted and "outside" in reason, bad
    assert sc.hk_period_s == 5.0 and sc.cmd_rejected == 4


def test_reboot_resets_counters_uptime_and_mode(spec):
    sc = Spacecraft(soc=0.9, mode=MODE_PAYLOAD)
    run(sc, 100)
    command(spec, sc, "Noop"), command(spec, sc, "SetTmRate", {"period_s": 9.0})
    assert command(spec, sc, "Reboot") == (True, "rebooting")
    assert (sc.cmd_accepted, sc.cmd_rejected, sc.last_cmd_id, sc.uptime_s, sc.mode, sc.hk_period_s) == \
        (0, 0, 0, 0.0, MODE_SAFE, 1.0)


def test_counters_saturate_instead_of_wrapping(spec):
    sc = Spacecraft()
    sc.cmd_accepted = 0xFFFF
    command(spec, sc, "Noop")
    assert sc.cmd_accepted == 0xFFFF
    sc.cmd_rejected = 0xFFFF
    sc.reject()
    assert sc.cmd_rejected == 0xFFFF
