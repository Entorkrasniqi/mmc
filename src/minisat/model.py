"""A deliberately simple physical model of the satellite - just enough to make telemetry behave believably.

Nothing here is a real spacecraft design. The point is to have numbers that *move for understandable reasons*, so
that when you watch them in the mission control system you can ask "why did that happen?" and find the answer in
20 lines of code:

* the satellite circles the Earth every ~96 minutes and spends about a third of each lap in the Earth's shadow (eclipse);
* in sunlight the solar panels produce current, in eclipse they produce none;
* the satellite consumes current depending on its mode (PAYLOAD uses the most) and on the heater;
* the battery charges when production exceeds consumption and drains otherwise;
* temperature drifts toward a target that depends on sun, load and heater;
* an on-board protection ("FDIR": fault detection, isolation and recovery) puts the satellite into SAFE mode when
  the battery gets too empty.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Tuple

from .spec import CommandSpec

__all__ = ["MU_EARTH", "R_EARTH", "Orbit", "Spacecraft"]

MU_EARTH = 398600.4418          # km^3/s^2, Earth's gravitational parameter
R_EARTH = 6378.137              # km, equatorial radius
OMEGA_EARTH = 7.2921159e-5      # rad/s, rotation rate of the Earth


@dataclass(frozen=True)
class Orbit:
    """A circular orbit and everything we derive from it.

    ``beta_deg`` is the angle between the orbit plane and the direction to the Sun. For a sun-synchronous orbit it
    stays roughly constant, which is why the eclipse pattern repeats lap after lap.
    """
    altitude_km: float = 560.0
    inclination_deg: float = 97.6          # > 90 degrees: the satellite travels "backwards" relative to the Earth's spin
    beta_deg: float = 20.0
    ascending_node_lon_deg: float = 10.0   # longitude where the satellite crosses the equator northward at t = 0
    sun_phase_deg: float = 0.0             # where along the orbit (from the node) the Sun is "overhead"

    @property
    def radius_km(self) -> float:
        return R_EARTH + self.altitude_km

    @property
    def period_s(self) -> float:
        """Kepler's third law: T = 2 pi sqrt(a^3 / mu)."""
        return 2.0 * math.pi * math.sqrt(self.radius_km ** 3 / MU_EARTH)

    def argument_of_latitude(self, t: float) -> float:
        """Angle travelled along the orbit since the ascending node, in radians."""
        return 2.0 * math.pi * t / self.period_s

    def ground_point(self, t: float) -> Tuple[float, float]:
        """Latitude and longitude (degrees) of the point on the ground directly below the satellite."""
        u = self.argument_of_latitude(t)
        i = math.radians(self.inclination_deg)
        lat = math.asin(math.sin(i) * math.sin(u))
        # right ascension of the satellite relative to the node, then subtract how far the Earth has turned
        lon = (math.radians(self.ascending_node_lon_deg) + math.atan2(math.cos(i) * math.sin(u), math.cos(u))
               - OMEGA_EARTH * t)
        lon = (math.degrees(lon) + 180.0) % 360.0 - 180.0
        return math.degrees(lat), lon

    def in_eclipse(self, t: float) -> bool:
        """Is the satellite inside the Earth's (cylindrical) shadow?

        With theta the angle between the satellite and the sub-solar direction, measured in the orbit plane, the
        satellite is hidden when it is on the night side (cos theta < 0) and closer to the Earth-Sun axis than one Earth
        radius. Working that out gives cos(theta) < -sqrt(1 - (R/a)^2) / cos(beta).
        """
        theta = self.argument_of_latitude(t) - math.radians(self.sun_phase_deg)
        threshold = -math.sqrt(1.0 - (R_EARTH / self.radius_km) ** 2) / math.cos(math.radians(self.beta_deg))
        return math.cos(theta) < threshold

    def eclipse_fraction(self, samples: int = 3600) -> float:
        """Fraction of one lap spent in shadow (numerical, for documentation and tests)."""
        return sum(self.in_eclipse(k * self.period_s / samples) for k in range(samples)) / samples


# ----------------------------------------------------------------------------------------- spacecraft

MODE_SAFE, MODE_NOMINAL, MODE_PAYLOAD = 0, 1, 2
_LOAD_A = {MODE_SAFE: 0.25, MODE_NOMINAL: 0.45, MODE_PAYLOAD: 1.10}   # current drawn per mode, amperes
HEATER_LOAD_A = 0.35
BATTERY_AH = 4.0                       # capacity: 4 Ah at ~7.4 V = ~30 Wh, typical of a small satellite
SOC_FDIR = 0.15                        # below this the satellite protects itself
SOC_PAYLOAD_MIN = 0.30                 # below this a PAYLOAD command is refused
THERMAL_TAU_S = 1500.0                 # how fast temperature follows its target


@dataclass
class Spacecraft:
    """The mutable state of the satellite plus the rules that change it."""
    orbit: Orbit = field(default_factory=Orbit)
    seed: int = 1
    soc: float = 0.90                  # battery state of charge, 0..1
    temp_c: float = 12.0
    mode: int = MODE_NOMINAL
    heater: bool = False
    uptime_s: float = 0.0
    cmd_accepted: int = 0
    cmd_rejected: int = 0
    last_cmd_id: int = 0
    hk_period_s: float = 1.0
    t: float = 0.0                     # simulated seconds since the start

    def __post_init__(self):
        self._rng = random.Random(self.seed)
        self._solar_a = 0.0
        self._load_a = _LOAD_A[self.mode]
        self._battery_a = 0.0          # current into (+) / out of (-) the battery
        self.fdir_events = 0           # how many times protection forced SAFE mode (not telemetered; for tests/demo)
        self._update_currents()

    # ---------------------------------------------------------------- time stepping

    def _update_currents(self) -> None:
        sunlit = not self.orbit.in_eclipse(self.t)
        # panels: 1.3 A at best, with a slow wobble as the satellite rotates; zero in the dark
        self._solar_a = 1.3 * (0.8 + 0.2 * math.sin(2.0 * math.pi * self.t / 480.0)) if sunlit else 0.0
        self._load_a = _LOAD_A[self.mode] + (HEATER_LOAD_A if self.heater else 0.0)
        net = self._solar_a - self._load_a
        # a full battery cannot absorb more: the excess is simply not used (shunted)
        self._battery_a = 0.0 if (self.soc >= 1.0 and net > 0) else net

    def step(self, dt: float) -> None:
        """Advance the simulation by ``dt`` seconds (use steps of about a second or less)."""
        if dt <= 0:
            return
        self._update_currents()
        self.soc = min(1.0, max(0.0, self.soc + self._battery_a * dt / (3600.0 * BATTERY_AH)))
        sunlit = not self.orbit.in_eclipse(self.t)
        target = (16.0 if sunlit else -6.0) + 5.0 * self._load_a + (10.0 if self.heater else 0.0)
        self.temp_c += (target - self.temp_c) * min(1.0, dt / THERMAL_TAU_S)
        self.uptime_s += dt
        self.t += dt
        if self.soc < SOC_FDIR and self.mode != MODE_SAFE:        # on-board protection
            self.mode = MODE_SAFE
            self.fdir_events += 1

    # ---------------------------------------------------------------- telemetry values

    def battery_voltage(self) -> float:
        open_circuit = 6.0 + 2.4 * self.soc                      # 6.0 V empty ... 8.4 V full
        return min(8.45, open_circuit + 0.15 * self._battery_a)  # a little more when charging, less when discharging

    def housekeeping(self) -> dict:
        """Current values of every Housekeeping field (keys match spec/minisat.yaml)."""
        noise = lambda scale: self._rng.uniform(-scale, scale)   # noqa: E731 - tiny local helper
        return {
            "mode": self.mode,
            "cmd_accepted": self.cmd_accepted,
            "cmd_rejected": self.cmd_rejected,
            "last_cmd_id": self.last_cmd_id,
            "uptime_s": int(self.uptime_s),
            "battery_voltage": self.battery_voltage() + noise(0.004),
            "battery_soc_pct": self.soc * 100.0,
            "battery_temp_c": self.temp_c + noise(0.05),
            "solar_current_a": max(0.0, self._solar_a + noise(0.005)),
            "load_current_a": self._load_a + noise(0.005),
            "in_eclipse": 1 if self.orbit.in_eclipse(self.t) else 0,
            "heater": 1 if self.heater else 0,
        }

    def position(self) -> dict:
        lat, lon = self.orbit.ground_point(self.t)
        return {"latitude_deg": lat, "longitude_deg": lon, "altitude_km": self.orbit.altitude_km}

    # ---------------------------------------------------------------- telecommands

    def reject(self) -> None:
        """Count a rejected command that could not even be identified (malformed packet, unknown id...)."""
        self.cmd_rejected = min(0xFFFF, self.cmd_rejected + 1)

    def handle_command(self, cmd: CommandSpec, args: dict) -> Tuple[bool, str]:
        """Execute one command. Returns (accepted, reason); counters are updated like a real flight computer would."""
        accepted, reason = self._execute(cmd, args)
        if cmd.name == "Reboot" and accepted:
            # the counters live in RAM that a reboot wipes: the next telemetry shows zeros and a fresh uptime
            self.cmd_accepted = self.cmd_rejected = self.last_cmd_id = 0
            self.uptime_s = 0.0
            self.mode = MODE_SAFE
            self.hk_period_s = 1.0
            return True, reason
        self.last_cmd_id = cmd.id
        if accepted:
            self.cmd_accepted = min(0xFFFF, self.cmd_accepted + 1)
        else:
            self.cmd_rejected = min(0xFFFF, self.cmd_rejected + 1)
        return accepted, reason

    def _execute(self, cmd: CommandSpec, args: dict) -> Tuple[bool, str]:
        name = cmd.name
        if name == "Noop":
            return True, "ok"
        if name == "SetMode":
            new_mode = args["mode"]
            if new_mode not in (MODE_SAFE, MODE_NOMINAL, MODE_PAYLOAD):
                return False, f"unknown mode {new_mode}"
            if new_mode == MODE_PAYLOAD and self.soc < SOC_PAYLOAD_MIN:
                return False, f"battery too low for PAYLOAD mode ({self.soc * 100:.0f} % < {SOC_PAYLOAD_MIN * 100:.0f} %)"
            self.mode = new_mode
            return True, "ok"
        if name == "SetHeater":
            if args["state"] not in (0, 1):
                return False, "state must be 0 (OFF) or 1 (ON)"
            self.heater = bool(args["state"])
            return True, "ok"
        if name == "Reboot":
            return True, "rebooting"
        if name == "SetTmRate":
            period = args["period_s"]
            low, high = next(a.range for a in cmd.args if a.name == "period_s")
            if not (low <= period <= high):                  # also False for NaN
                return False, f"period {period} outside [{low}, {high}]"
            self.hk_period_s = period
            return True, "ok"
        return False, f"command {name} is not implemented by the simulator"
