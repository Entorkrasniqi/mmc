"""Telemetry from the in-process simulator flows through the ingestor and the automations into the database (no network).

The simulator is the source of truth for what telemetry looks like; expected alarm limits, thresholds and counters are
worked out from the specification and the satellite's rules (35 % / 20 % battery limits, SAFE below 15 %, PAYLOAD refused
below 30 %).
"""
import math

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic")

from psycopg.types.json import Jsonb  # noqa: E402
from minisat.ccsds import PacketError  # noqa: E402
from minisat.codec import encode_tm  # noqa: E402
from minisat.model import Spacecraft  # noqa: E402
from minisat.ontology.automation import AutomationConfig, AutomationEngine  # noqa: E402
from minisat.ontology.ingest import Ingestor, UnknownSpacecraft  # noqa: E402
from minisat.ontology.worker import OutboxWorker  # noqa: E402
from minisat.simulator import Simulator  # noqa: E402

EPOCH_MS = 1_792_800_000_000
MODE = {"SAFE": 0, "NOMINAL": 1, "PAYLOAD": 2}


class Rig:
    """A simulated satellite wired to the ingestor and the automations, all driven by hand and a fake clock."""

    def __init__(self, world, soc=0.9, mode=None, sink=None, start_t=0.0):
        self.world, self.spec = world, world.spec
        model = Spacecraft(soc=soc, t=start_t, **({"mode": MODE[mode]} if mode else {}))
        self.packets = []
        self.sim = Simulator(self.spec, model, self.packets.append, epoch_ms=EPOCH_MS)
        self.ingestor = Ingestor(self.spec, world.db.connect_factory("ingest"), "MINISAT-1", clock=world.clock)
        self.engine = AutomationEngine(self.spec, world.runner, world.db.connect_factory("runner"), clock=world.clock,
                                       config=AutomationConfig(), log=(sink.append if sink is not None else None))
        self.results = []

    def feed(self, packets):
        for data in packets:
            result = self.ingestor.ingest(data)
            self.results.append(result)
            self.engine.on_telemetry(result)

    def run(self, seconds):
        """Advance the satellite; every second of simulated time is also a second on the fake clock."""
        for _ in range(int(seconds)):
            self.packets.clear()
            self.sim.advance(1.0)
            self.world.clock.advance(1.0)
            self.feed(list(self.packets))

    def set_soc(self, fraction):
        """Put the battery at a given charge, instead of simulating hours of draining."""
        self.sim.model.soc = fraction

    def alarms(self, where="true"):
        return self.world.rows(f"SELECT * FROM ops.alarm WHERE {where} ORDER BY raised_at, alarm_id")

    def events(self, kind=None):
        sql = "SELECT * FROM ops.spacecraft_event" + (" WHERE event_type = %s" if kind else "") + " ORDER BY occurred_at"
        return self.world.rows(sql, *([kind] if kind else []))

    def close(self):
        self.ingestor.close()
        self.engine.close()


@pytest.fixture()
def rig(world):
    made = []

    def make(**kw):
        made.append(Rig(world, **kw))
        return made[-1]
    yield make
    for r in made:
        r.close()


# ------------------------------------------------------------------------------------------------ ingestion

def test_every_value_becomes_a_sample_and_the_newest_values_are_kept(rig, world):
    r = rig()
    r.run(3)
    hk = world.rows("SELECT count(*) AS n FROM ops.telemetry_samples WHERE parameter_name = 'battery_soc_pct'")[0]["n"]
    pos = world.rows("SELECT count(*) AS n FROM ops.telemetry_samples WHERE parameter_name = 'latitude_deg'")[0]["n"]
    assert hk == 4 and pos == 1                       # Housekeeping at t = 0, 1, 2, 3 s; Position only at t = 0 (every 5 s)
    sc = world.row("SELECT * FROM ops.spacecraft")
    assert sc["last_contact_at"] == world.clock.now
    assert set(sc["latest_values"]) == {f.name for p in world.spec.tm_packets for f in p.fields}
    assert sc["latest_values"]["mode"] == 1 and sc["latest_values"]["uptime_s"] == 3
    # 3 s of charging at about 0.6 A is 0.6 * 3 / (3600 * 4 Ah) = 0.0125 % on top of the 90 % start
    assert math.isclose(sc["latest_values"]["battery_soc_pct"], 90.0125, abs_tol=0.005)


def test_the_samples_carry_the_spacecraft_time_and_the_sequence_count(rig, world):
    r = rig()
    r.run(2)
    rows = world.rows("SELECT sc_time_ms, packet_seq_count FROM ops.telemetry_samples WHERE parameter_name = 'mode' "
                      "ORDER BY sc_time_ms")
    assert [(x["sc_time_ms"] - EPOCH_MS, x["packet_seq_count"]) for x in rows] == [(0, 0), (1000, 1), (2000, 2)]


def test_a_damaged_packet_is_refused_and_stores_nothing(rig, world):
    r = rig()
    r.run(1)
    good = r.packets[0]
    for bad in (good[:-1], good[:6] + bytes(3), b"", b"\xff" * 12):
        with pytest.raises(PacketError):
            r.ingestor.ingest(bad)
    assert world.row("SELECT count(*) AS n FROM ops.telemetry_samples WHERE parameter_name = 'mode'")["n"] == 2


def test_the_same_packet_twice_is_stored_once_and_triggers_nothing(rig, world):
    r = rig(soc=0.30)
    r.run(1)
    again = r.ingestor.ingest(r.packets[0])
    assert again.duplicate and again.current == again.previous
    assert r.engine.on_telemetry(again) == []
    assert world.row("SELECT count(*) AS n FROM ops.telemetry_samples WHERE parameter_name = 'mode'")["n"] == 2


def test_an_older_packet_is_kept_as_a_sample_but_does_not_overwrite_the_newest_values(rig, world):
    r = rig()
    r.run(3)
    old = encode_tm(world.spec, "Housekeeping", {**r.sim.model.housekeeping(), "uptime_s": 1, "mode": 0},
                    EPOCH_MS + 500, 2)                           # claims to be from before the newest packet
    result = r.ingestor.ingest(old)
    assert result.out_of_order and not result.duplicate
    r.engine.on_telemetry(result)
    sc = world.row("SELECT * FROM ops.spacecraft")
    assert sc["latest_values"]["mode"] == 1 and sc["latest_values"]["uptime_s"] == 3
    assert world.row("SELECT count(*) AS n FROM ops.spacecraft_event WHERE event_type = 'MODE_CHANGE'")["n"] == 0


def test_non_finite_values_stay_out_of_the_newest_values_but_are_stored_as_samples(rig, world):
    r = rig()
    r.run(1)
    values = {**r.sim.model.housekeeping(), "battery_temp_c": float("nan")}
    result = r.ingestor.ingest(encode_tm(world.spec, "Housekeeping", values, EPOCH_MS + 2000, 2))
    r.engine.on_telemetry(result)
    sc = world.row("SELECT * FROM ops.spacecraft")
    assert math.isfinite(sc["latest_values"]["battery_temp_c"])           # still the previous, valid reading
    nan = world.row("SELECT value FROM ops.telemetry_samples WHERE parameter_name = 'battery_temp_c' AND sc_time_ms = %s",
                    EPOCH_MS + 2000)
    assert math.isnan(nan["value"])
    assert r.alarms("parameter_name = 'battery_temp_c'") == []            # NaN is not a limit violation


def test_telemetry_for_an_unknown_spacecraft_is_refused_with_a_hint(world):
    ingestor = Ingestor(world.spec, world.db.connect_factory("ingest"), "NOPE", clock=world.clock)
    packets = []
    Simulator(world.spec, Spacecraft(), packets.append, epoch_ms=EPOCH_MS).advance(0.0)
    with pytest.raises(UnknownSpacecraft, match="db-seed"):
        ingestor.ingest(packets[0])
    ingestor.close()


def test_the_ingest_role_is_all_the_ingestor_uses(rig, world):
    """Its connection is the ingest role: it could not have written an alarm even if it tried."""
    r = rig()
    with r.ingestor._db as conn:
        assert conn.execute("SELECT current_user AS u").fetchone()["u"] == "ingest"


# ------------------------------------------------------------------------------------------------ alarms

def test_the_battery_walks_through_warning_critical_and_back_to_normal(rig, world):
    r = rig()
    r.run(1)
    assert r.alarms() == []

    def by_parameter():
        return {a["parameter_name"]: a for a in r.alarms()}

    r.set_soc(0.34)                                    # just below the 35 % warning limit; the voltage (6.8 V) is still fine
    r.run(1)
    assert set(by_parameter()) == {"battery_soc_pct"}
    soc = by_parameter()["battery_soc_pct"]
    assert (soc["severity"], soc["state"], soc["limit_violated"]) == ("WARNING", "ACTIVE", "below warning minimum 35")
    assert 33.9 < soc["trigger_value"] < 34.1
    assert world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "WARNING"

    r.set_soc(0.19)                                    # below the 20 % critical limit; 6.0 V + 2.4 V x 0.19 = 6.46 V < 6.8 V
    r.run(1)
    alarms = by_parameter()
    assert set(alarms) == {"battery_soc_pct", "battery_voltage"} and len(r.alarms()) == 2     # escalated, not duplicated
    assert (alarms["battery_soc_pct"]["severity"], alarms["battery_soc_pct"]["limit_violated"]) == (
        "CRITICAL", "below critical minimum 20")
    assert alarms["battery_voltage"]["severity"] == "WARNING"
    assert world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "CRITICAL"

    r.set_soc(0.60)
    r.run(1)
    assert {a["state"] for a in r.alarms()} == {"CLEARED"}
    assert world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "NOMINAL"
    from collections import Counter
    done = Counter((a["action"], a["operator_id"]) for a in world.audit(outcome="OK")
                   if a["action"] in ("Raise Alarm", "Update Alarm", "Clear Alarm"))
    assert done == {("Raise Alarm", "automation"): 2, ("Update Alarm", "automation"): 1, ("Clear Alarm", "automation"): 2}


def test_the_voltage_and_temperature_have_limits_too(rig, world):
    r = rig()
    r.set_soc(0.05)                                    # 5 % charge is about 6.12 V: below the 6.4 V critical limit
    r.run(1)
    names = {a["parameter_name"]: a["severity"] for a in r.alarms()}
    assert names == {"battery_soc_pct": "CRITICAL", "battery_voltage": "CRITICAL"}


def test_no_alarm_while_everything_is_inside_its_limits(rig, world):
    r = rig()
    r.run(120)
    assert r.alarms() == [] and world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "NOMINAL"
    assert world.audit(action="Raise Alarm") == []


def test_a_person_acknowledgement_survives_while_the_alarm_stays(rig, world):
    r = rig(soc=0.30)
    r.run(1)
    (alarm,) = r.alarms()
    world.run("alice", "Acknowledge Alarm", alarm_id=str(alarm["alarm_id"]))
    r.run(5)                                           # more violating packets must not undo or duplicate it
    (alarm,) = r.alarms()
    assert alarm["state"] == "ACKNOWLEDGED" and alarm["acknowledged_by"] == "alice"


# ------------------------------------------------------------------------------------------------ events and anomalies

def test_commanded_mode_changes_are_events_but_not_anomalies(rig, world):
    r = rig()
    r.run(2)
    r.sim.handle_telecommand(bytes.fromhex("100ac0000002000200"))          # SetMode SAFE, hand-built from the README
    r.run(2)
    kinds = [e["event_type"] for e in r.events()]
    assert "MODE_CHANGE" in kinds and "COMMAND_ACCEPTED" in kinds and "FDIR" not in kinds
    (change,) = r.events("MODE_CHANGE")
    assert change["details"] == {"from": "NOMINAL", "to": "SAFE"}
    assert world.row("SELECT count(*) AS n FROM ops.anomaly")["n"] == 0
    assert world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "SAFE_MODE"


def test_an_unplanned_safe_mode_opens_an_anomaly_with_the_alarms_and_notifies(rig, world):
    r = rig(soc=0.14, mode="PAYLOAD")                  # 14 % is below the 15 % at which the satellite protects itself
    r.run(3)
    (fdir,) = r.events("FDIR")
    assert fdir["details"]["battery_soc_pct"] < 15.0
    (anomaly,) = world.rows("SELECT * FROM ops.anomaly")
    assert (anomaly["title"], anomaly["severity"], anomaly["status"], anomaly["opened_by"]) == (
        "Unplanned SAFE mode", "HIGH", "OPEN", "automation")
    assert fdir["anomaly_id"] == anomaly["anomaly_id"]
    linked = {a["parameter_name"]: a["severity"] for a in
              world.rows("SELECT parameter_name, severity FROM ops.alarm WHERE anomaly_id = %s", anomaly["anomaly_id"])}
    assert set(linked) == {"battery_soc_pct", "battery_voltage"} and linked["battery_soc_pct"] == "CRITICAL"
    (message,) = world.rows("SELECT * FROM ops.outbox WHERE topic = 'notify_supervisors'")
    assert message["payload"]["title"] == "Unplanned SAFE mode"
    assert world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "SAFE_MODE"


def test_a_reboot_is_one_event(rig, world):
    r = rig()
    r.run(5)
    r.sim.handle_telecommand(bytes.fromhex("100ac00000010004"))          # Reboot: header, length 1, command id 4
    r.run(2)
    assert [e["event_type"] for e in r.events() if e["event_type"] in ("REBOOT", "MODE_CHANGE", "FDIR")] == ["REBOOT"]
    assert world.row("SELECT count(*) AS n FROM ops.anomaly")["n"] == 0


def test_eclipse_entries_and_exits_are_events(rig, world):
    r = rig(start_t=1825.0)                           # the shadow starts at about 114.8 degrees of the orbit, ~1833 s
    r.run(10)
    (entry,) = r.events("ECLIPSE_ENTRY")
    assert 1830 <= (entry["occurred_at"].timestamp() - EPOCH_MS / 1000.0) <= 1836
    assert world.row("SELECT latest_values->>'in_eclipse' AS e FROM ops.spacecraft")["e"] == "1"
    assert r.events("ECLIPSE_EXIT") == []


def test_lost_packets_are_recorded_from_the_sequence_counter(rig, world):
    r = rig()
    r.run(2)
    r.packets.clear()
    r.sim.advance(1.0)
    r.sim.advance(1.0)
    r.sim.advance(1.0)                                 # three more Housekeeping packets...
    hk = [p for p in r.packets if p[0] == 0x08 and p[1] == 0x64]
    assert len(hk) == 3
    r.world.clock.advance(3)
    r.feed([hk[2]])                                    # ...of which only the last one arrives: two are lost
    (event,) = r.events("PACKET_LOSS")
    assert event["details"] == {"apid": 100, "lost": 2, "seq_count": 5}


# ------------------------------------------------------------------------------------------------ the link

def test_a_silent_link_is_reported_once_and_its_return_too(rig, world):
    r = rig()
    r.run(2)
    world.clock.advance(2.5)
    assert r.engine.tick("MINISAT-1") == []            # 2.5 s of silence: within 3 periods
    world.clock.advance(1.0)
    r.engine.tick("MINISAT-1")
    r.engine.tick("MINISAT-1")                         # a second tick must not repeat it
    assert len(r.events("LINK_LOST")) == 1
    assert r.events("LINK_LOST")[0]["details"]["silent_for_s"] == 3.5
    r.run(1)
    assert len(r.events("LINK_RESTORED")) == 1
    world.clock.advance(10)
    r.engine.tick("MINISAT-1")
    assert len(r.events("LINK_LOST")) == 2             # and it can be lost again


# ------------------------------------------------------------------------------------------------ commands, end to end

class SimLink:
    """The worker's link, wired straight to the in-process satellite."""

    def __init__(self, rig):
        self.rig = rig

    def send(self, data):
        self.rig.sim.handle_telecommand(data)


def worker_for(world, rig, notified=None):
    return OutboxWorker(world.db.connect_factory("runner"), world.runner, SimLink(rig), clock=world.clock,
                        notify=(notified.append if notified is not None else None))


def push_through(world, r, worker, command, arguments, seconds=3, approver="bob", supervisor=False):
    """Propose, approve and release a command, let the worker send it, and run the satellite."""
    who = "sam" if supervisor else "alice"
    eid = world.run(who, "Propose Command", spacecraft_id="MINISAT-1", command=command, arguments=arguments,
                    reason="scripted test").result["execution_id"]
    world.run("tina" if supervisor else approver, "Approve Command", execution_id=eid, note="ok")
    world.run("sam", "Release Command", execution_id=eid, override_reason="simulator is always in contact")
    assert worker.run_once() == 1
    r.run(seconds)
    return eid


def test_a_command_goes_all_the_way_to_verified_by_itself(rig, world):
    r = rig()
    worker = worker_for(world, r)
    r.run(2)
    eid = push_through(world, r, worker, "SetMode", {"mode": "PAYLOAD"})
    row = world.execution(eid)
    assert row["status"] == "VERIFIED" and row["verified_at"] is not None and r.sim.model.mode == 2
    assert world.row("SELECT processed_at FROM ops.outbox WHERE topic = 'send_telecommand'")["processed_at"] is not None
    statuses = [a["after"][f"command_execution:{eid}"]["status"] for a in world.audit(outcome="OK")
                if f"command_execution:{eid}" in (a["after"] or {})]
    assert statuses == ["PROPOSED", "APPROVED", "RELEASED", "SENT", "ACCEPTED", "VERIFIED"]
    caused = world.rows("SELECT event_type FROM ops.spacecraft_event WHERE caused_by_execution_id = %s", row["execution_id"])
    assert {c["event_type"] for c in caused} == {"COMMAND_ACCEPTED"}


@pytest.mark.parametrize("command, arguments, check", [
    ("Noop", {}, lambda m: m.cmd_accepted == 1),
    ("SetHeater", {"state": "ON"}, lambda m: m.heater is True),
    ("SetTmRate", {"period_s": 2.0}, lambda m: m.hk_period_s == 2.0),
])
def test_other_commands_are_verified_too(rig, world, command, arguments, check):
    r = rig()
    worker = worker_for(world, r)
    r.run(2)
    eid = push_through(world, r, worker, command, arguments, seconds=3)
    assert world.execution(eid)["status"] == "VERIFIED" and check(r.sim.model)


def test_a_command_the_satellite_refuses_ends_rejected_onboard(rig, world):
    r = rig(soc=0.25)                                  # 25 %: PAYLOAD is refused
    worker = worker_for(world, r)
    r.run(2)
    eid = push_through(world, r, worker, "SetMode", {"mode": "PAYLOAD"}, supervisor=True)
    row = world.execution(eid)
    assert row["status"] == "REJECTED_ONBOARD" and "rejected on board" in row["rejection_reason"]
    assert r.sim.model.cmd_rejected == 1 and r.sim.model.mode == 1
    assert [e["event_type"] for e in r.events() if e["event_type"] == "COMMAND_REJECTED"] == ["COMMAND_REJECTED"]


def test_a_reboot_is_verified_by_the_uptime_reset(rig, world):
    r = rig()
    worker = worker_for(world, r)
    r.run(10)
    eid = push_through(world, r, worker, "Reboot", {}, seconds=3, supervisor=True)
    assert world.execution(eid)["status"] == "VERIFIED"
    assert r.sim.model.mode == 0 and world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "SAFE_MODE"
    assert world.row("SELECT count(*) AS n FROM ops.anomaly")["n"] == 0        # a commanded reboot is not an anomaly


def test_a_command_that_never_arrives_fails_after_the_window_and_is_not_resent(rig, world):
    r = rig()

    class DeadLink:                                    # the satellite never hears anything
        def send(self, data):
            pass
    worker = OutboxWorker(world.db.connect_factory("runner"), world.runner, DeadLink(), clock=world.clock)
    r.run(2)
    eid = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x").result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    world.run("sam", "Release Command", execution_id=eid, override_reason="sim")
    worker.run_once()
    r.run(4)
    assert world.execution(eid)["status"] == "SENT"                      # 4 s: still within the 5 s window
    r.run(2)
    r.engine.tick("MINISAT-1")
    row = world.execution(eid)
    assert row["status"] == "FAILED" and "no sign of the command" in row["rejection_reason"]
    assert worker.run_once() == 0                                        # nothing is sent a second time


def test_a_command_that_is_accepted_but_has_no_effect_fails_after_the_effect_window(rig, world):
    r = rig()
    worker = worker_for(world, r)
    r.run(2)
    eid = push_through(world, r, worker, "SetHeater", {"state": "ON"}, seconds=2)
    assert world.execution(eid)["status"] == "VERIFIED"
    # now one that is accepted but whose effect never appears: the expected effect is edited to something impossible
    proposal = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")
    eid2 = proposal.result["execution_id"]
    world.db.commit_params("migrator", "UPDATE ops.command_execution SET expected_effect = %s WHERE execution_id = %s",
                           (Jsonb([{"parameter": "mode", "op": "eq", "value": 99}]), eid2))
    world.run("bob", "Approve Command", execution_id=eid2)
    world.run("sam", "Release Command", execution_id=eid2, override_reason="sim")
    worker.run_once()
    r.run(3)
    assert world.execution(eid2)["status"] == "ACCEPTED"
    r.run(9)
    r.engine.tick("MINISAT-1")
    row = world.execution(eid2)
    assert row["status"] == "FAILED" and "expected effect did not show" in row["rejection_reason"]


def test_a_proposal_nobody_approved_is_cancelled_when_it_expires(rig, world):
    r = rig()
    r.run(1)
    eid = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x").result["execution_id"]
    world.clock.advance(14 * 60)
    r.engine.tick("MINISAT-1")
    assert world.execution(eid)["status"] == "PROPOSED"
    world.clock.advance(2 * 60)
    r.engine.tick("MINISAT-1")
    row = world.execution(eid)
    assert (row["status"], row["cancelled_by"], row["cancel_reason"]) == (
        "CANCELLED", "automation", "expired without being released")


def test_the_worker_does_not_send_a_command_that_is_no_longer_released(rig, world):
    r = rig()
    sent = []

    class Link:
        def send(self, data):
            sent.append(data)
    worker = OutboxWorker(world.db.connect_factory("runner"), world.runner, Link(), clock=world.clock)
    r.run(1)
    eid = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x").result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    world.run("sam", "Release Command", execution_id=eid, override_reason="sim")
    world.db.commit_params("migrator", "UPDATE ops.command_execution SET status = 'FAILED', rejection_reason = 'x', "
                           "send_baseline = '{}' WHERE execution_id = %s", (eid,))
    assert worker.run_once() == 1 and sent == []
    assert "RELEASED" in world.row("SELECT last_error FROM ops.outbox")["last_error"]


def test_a_claimed_message_is_not_handed_out_twice(rig, world):
    r = rig()
    r.run(1)
    notified = []
    w1, w2 = worker_for(world, r, notified), worker_for(world, r, notified)
    world.run("alice", "Open Anomaly", spacecraft_id="MINISAT-1", title="Strange", severity="HIGH")
    assert w1._claim() is not None
    assert w2._claim() is None                          # leased to the first worker for a minute
    world.clock.advance(61)
    assert w2._claim() is not None                      # the lease ran out: someone else may take over
    w1.close()
    w2.close()


def test_notifications_reach_the_notifier_and_a_broken_notifier_is_harmless(rig, world):
    r = rig()
    r.run(1)
    notified = []
    worker = worker_for(world, r, notified)
    world.run("alice", "Open Anomaly", spacecraft_id="MINISAT-1", title="Strange", severity="HIGH")
    assert worker.run_once() == 1 and notified[0]["title"] == "Strange"

    def broken(payload):
        raise RuntimeError("mail server down")
    world.run("alice", "Open Anomaly", spacecraft_id="MINISAT-1", title="Another", severity="HIGH")
    OutboxWorker(world.db.connect_factory("runner"), world.runner, SimLink(r), clock=world.clock, notify=broken).run_once()
    failed = world.row("SELECT last_error FROM ops.outbox WHERE payload->>'title' = 'Another'")
    assert "mail server down" in failed["last_error"]
