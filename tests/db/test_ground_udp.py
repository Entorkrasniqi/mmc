"""The whole chain over real UDP sockets and the real clock: UdpSimulator -> GroundStation -> PostgreSQL, and a command back.

This is the "done when" of PLAN.md phase 3: start the simulator with a low battery and an alarm appears, and the spacecraft
record updates, without anyone touching the database.
"""
import threading
import time

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic")

from minisat.model import Spacecraft  # noqa: E402
from minisat.ontology.actions import default_registry  # noqa: E402
from minisat.ontology.ground import build_ground_station  # noqa: E402
from minisat.ontology.runner import ActionRunner  # noqa: E402
from minisat.simulator import UdpSimulator  # noqa: E402


def wait_for(condition, timeout=15.0, step=0.05):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = condition()
        if value:
            return value
        time.sleep(step)
    return None


def latest(world):
    return world.row("SELECT latest_values FROM ops.spacecraft")["latest_values"]


class Chain:
    """A simulator and a ground station on loopback UDP ports, both running in background threads."""

    def __init__(self, world, soc=0.9, speedup=1.0, log=None):
        self.world = world
        self.sim = UdpSimulator(world.spec, Spacecraft(soc=soc), tm_addr=("127.0.0.1", 9), tc_bind=("127.0.0.1", 0),
                                speedup=speedup)
        self.logs = [] if log is None else log
        self.station = build_ground_station(
            world.spec, "MINISAT-1", lambda role: world.db.connect_factory(role)(), tc_addr=self.sim.tc_address,
            tm_bind=("127.0.0.1", 0), log=self.logs.append)
        self.sim._tm_addr = self.station.tm_address        # now that the station has a port, point the satellite at it
        self.runner = ActionRunner(world.db.connect_factory("runner"), world.spec, default_registry())
        self.thread = threading.Thread(target=self.sim.run, kwargs={"duration_s": 60}, daemon=True)

    def __enter__(self):
        self.station.start()
        self.thread.start()
        return self

    def __exit__(self, *exc):
        self.sim.stop()
        self.thread.join(timeout=5)
        self.station.stop()

    def run(self, operator, action, **params):
        return self.runner.run(operator, action, params)


def test_a_low_battery_in_the_simulator_becomes_an_alarm_in_the_database_by_itself(world):
    with Chain(world, soc=0.30):
        alarm = wait_for(lambda: world.row("SELECT * FROM ops.alarm WHERE parameter_name = 'battery_soc_pct'"))
        assert alarm is not None, "no alarm appeared within 15 s"
        assert (alarm["severity"], alarm["state"], alarm["limit_violated"]) == ("WARNING", "ACTIVE",
                                                                                "below warning minimum 35")
        sc = wait_for(lambda: (lambda r: r if r["health_status"] == "WARNING" else None)(
            world.row("SELECT * FROM ops.spacecraft")))
        assert sc is not None
        assert sc["latest_values"]["mode"] == 1 and sc["last_contact_at"] is not None
        assert sc["latest_values"]["uptime_s"] >= 0
    assert world.row("SELECT count(*) AS n FROM ops.telemetry_samples")["n"] >= 12
    assert world.audit(action="Raise Alarm")[0]["operator_id"] == "automation"        # through the runner, as the system


def test_a_healthy_satellite_produces_samples_but_no_alarms(world):
    with Chain(world, soc=0.9):
        assert wait_for(lambda: world.row("SELECT count(*) AS n FROM ops.telemetry_samples")["n"] >= 24)
    assert world.rows("SELECT * FROM ops.alarm") == []
    assert world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "NOMINAL"


def test_a_command_travels_to_the_satellite_over_udp_and_is_verified_from_its_telemetry(world):
    with Chain(world) as chain:
        assert wait_for(lambda: latest(world).get("mode") is not None)
        eid = chain.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="SetHeater",
                        arguments={"state": "ON"}, reason="warm the battery").result["execution_id"]
        chain.run("bob", "Approve Command", execution_id=eid)
        chain.run("sam", "Release Command", execution_id=eid, override_reason="simulator is always in contact")
        row = wait_for(lambda: (lambda r: r if r["status"] in ("VERIFIED", "FAILED", "REJECTED_ONBOARD") else None)(
            world.execution(eid)))
        assert row is not None, "the command did not finish within 15 s"
        assert row["status"] == "VERIFIED", row
        assert chain.sim.sim.model.heater is True
    assert world.row("SELECT latest_values->>'heater' AS h FROM ops.spacecraft")["h"] == "1"


def test_a_vital_reboot_needs_two_supervisors_and_ends_verified(world):
    with Chain(world) as chain:
        assert wait_for(lambda: latest(world).get("uptime_s", -1) >= 2)
        eid = chain.run("sam", "Propose Command", spacecraft_id="MINISAT-1", command="Reboot",
                        reason="clear a suspected fault").result["execution_id"]
        chain.run("tina", "Approve Command", execution_id=eid)
        chain.run("sam", "Release Command", execution_id=eid, override_reason="simulator is always in contact")
        row = wait_for(lambda: (lambda r: r if r["status"] in ("VERIFIED", "FAILED", "REJECTED_ONBOARD") else None)(
            world.execution(eid)))
        assert row is not None and row["status"] == "VERIFIED", row
        assert wait_for(lambda: world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "SAFE_MODE")
    assert world.rows("SELECT * FROM ops.anomaly") == []             # a commanded reboot is not an anomaly


def test_garbage_on_the_telemetry_port_is_logged_and_does_not_stop_the_station(world):
    import socket
    logs = []
    with Chain(world, log=logs) as chain:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for junk in (b"", b"\x00" * 3, b"\xff" * 50, b"hello"):
            sock.sendto(junk, chain.station.tm_address)
        sock.close()
        assert wait_for(lambda: sum("bad packet" in line for line in logs) >= 4)
        before = world.row("SELECT count(*) AS n FROM ops.telemetry_samples")["n"]
        assert wait_for(lambda: world.row("SELECT count(*) AS n FROM ops.telemetry_samples")["n"] > before)   # still working
    assert chain.station.packets > 0
