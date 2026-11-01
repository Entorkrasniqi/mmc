"""Alarms, anomalies, spacecraft events, health status and contact windows, through the action runner."""
import uuid

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic")

from minisat.ontology.runner import InvalidAction, PermissionDenied  # noqa: E402

NO_SUCH = "5b1ac9f1-0000-4000-8000-000000000000"


def raise_alarm(world, parameter="battery_soc_pct", severity="WARNING", value=34.0, **extra):
    return world.run("automation", "Raise Alarm", spacecraft_id="MINISAT-1", parameter_name=parameter, severity=severity,
                     trigger_value=value, limit_violated="below warning minimum 35", **extra)


def event(world, kind="FDIR", **extra):
    return world.run("automation", "Record Spacecraft Event", spacecraft_id="MINISAT-1", event_type=kind,
                     occurred_at=world.clock.now.isoformat(), **extra)


# ------------------------------------------------------------------------------------------------ alarms

def test_an_alarm_is_raised_updated_and_cleared_by_the_system(world):
    aid = raise_alarm(world).result["alarm_id"]
    row = world.row("SELECT * FROM ops.alarm WHERE alarm_id = %s", aid)
    assert (row["state"], row["severity"], row["trigger_value"]) == ("ACTIVE", "WARNING", 34.0)
    assert row["raised_at"] == world.clock.now
    world.run("automation", "Update Alarm", alarm_id=aid, severity="CRITICAL", trigger_value=19.0,
              limit_violated="below critical minimum 20")
    row = world.row("SELECT * FROM ops.alarm WHERE alarm_id = %s", aid)
    assert (row["severity"], row["trigger_value"], row["state"]) == ("CRITICAL", 19.0, "ACTIVE")
    world.clock.advance(60)
    world.run("automation", "Clear Alarm", alarm_id=aid)
    row = world.row("SELECT * FROM ops.alarm WHERE alarm_id = %s", aid)
    assert row["state"] == "CLEARED" and row["cleared_at"] == world.clock.now


def test_raising_an_alarm_is_checked_against_the_specification(world):
    with pytest.raises(InvalidAction, match="unknown telemetry parameter"):
        raise_alarm(world, "warp_core_temp")
    with pytest.raises(InvalidAction, match="no alarm limits"):
        raise_alarm(world, "solar_current_a")                                 # the spec gives it no limits
    with pytest.raises(InvalidAction, match="unknown spacecraft"):
        world.run("automation", "Raise Alarm", spacecraft_id="NOPE", parameter_name="battery_soc_pct",
                  severity="WARNING", trigger_value=1, limit_violated="x")


def test_a_parameter_has_one_open_alarm_until_it_is_cleared(world):
    aid = raise_alarm(world).result["alarm_id"]
    with pytest.raises(InvalidAction, match="already has an open alarm"):
        raise_alarm(world, severity="CRITICAL")
    world.run("automation", "Clear Alarm", alarm_id=aid)
    raise_alarm(world)                                                        # a new episode
    assert world.row("SELECT count(*) AS n FROM ops.alarm")["n"] == 2


def test_a_cleared_alarm_cannot_be_updated_or_cleared_again(world):
    aid = raise_alarm(world).result["alarm_id"]
    world.run("automation", "Clear Alarm", alarm_id=aid)
    with pytest.raises(InvalidAction, match="already cleared"):
        world.run("automation", "Clear Alarm", alarm_id=aid)
    with pytest.raises(InvalidAction, match="cleared alarm"):
        world.run("automation", "Update Alarm", alarm_id=aid, severity="WARNING", trigger_value=1, limit_violated="x")


def test_a_person_acknowledges_an_alarm_and_it_stays_acknowledged_when_cleared(world):
    aid = raise_alarm(world).result["alarm_id"]
    world.run("alice", "Acknowledge Alarm", alarm_id=aid, note="battery is charging again soon")
    row = world.row("SELECT * FROM ops.alarm WHERE alarm_id = %s", aid)
    assert (row["state"], row["acknowledged_by"], row["acknowledge_note"]) == (
        "ACKNOWLEDGED", "alice", "battery is charging again soon")
    with pytest.raises(InvalidAction, match="only an ACTIVE"):
        world.run("bob", "Acknowledge Alarm", alarm_id=aid)
    world.run("automation", "Clear Alarm", alarm_id=aid)
    row = world.row("SELECT * FROM ops.alarm WHERE alarm_id = %s", aid)
    assert (row["state"], row["acknowledged_by"]) == ("CLEARED", "alice")


@pytest.mark.parametrize("who", ["vera", "helper", "automation"])
def test_viewers_agents_and_the_system_cannot_acknowledge(world, who):
    aid = raise_alarm(world).result["alarm_id"]
    with pytest.raises(PermissionDenied):
        world.run(who, "Acknowledge Alarm", alarm_id=aid)
    assert world.row("SELECT state FROM ops.alarm")["state"] == "ACTIVE"


def test_a_cleared_alarm_cannot_be_acknowledged(world):
    aid = raise_alarm(world).result["alarm_id"]
    world.run("automation", "Clear Alarm", alarm_id=aid)
    with pytest.raises(InvalidAction, match="only an ACTIVE"):
        world.run("alice", "Acknowledge Alarm", alarm_id=aid)


def test_a_command_can_say_which_alarm_it_responds_to(world):
    aid = raise_alarm(world).result["alarm_id"]
    result = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="SetMode",
                       arguments={"mode": "NOMINAL"}, reason="battery low", responds_to_alarm_id=aid)
    row = world.execution(result.result["execution_id"])
    assert str(row["responds_to_alarm_id"]) == aid


# ------------------------------------------------------------------------------------------------ events and health

def test_spacecraft_events_are_recorded_with_their_cause(world):
    proposal = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")
    eid = proposal.result["execution_id"]
    result = event(world, "COMMAND_ACCEPTED", details={"last_cmd_id": 1}, caused_by_execution_id=eid)
    row = world.row("SELECT * FROM ops.spacecraft_event WHERE event_id = %s", result.result["event_id"])
    assert (row["event_type"], row["details"], str(row["caused_by_execution_id"])) == (
        "COMMAND_ACCEPTED", {"last_cmd_id": 1}, eid)
    assert row["occurred_at"] == world.clock.now


def test_event_input_is_validated(world):
    with pytest.raises(InvalidAction):
        event(world, "UFO_SIGHTING")
    with pytest.raises(InvalidAction, match="time zone"):
        world.run("automation", "Record Spacecraft Event", spacecraft_id="MINISAT-1", event_type="REBOOT",
                  occurred_at="2026-10-31T12:00:00")
    with pytest.raises(InvalidAction, match="unknown spacecraft"):
        world.run("automation", "Record Spacecraft Event", spacecraft_id="NOPE", event_type="REBOOT",
                  occurred_at=world.clock.now.isoformat())


def test_health_status_is_set_by_the_system(world):
    world.run("automation", "Set Health Status", spacecraft_id="MINISAT-1", health_status="CRITICAL")
    assert world.row("SELECT health_status FROM ops.spacecraft")["health_status"] == "CRITICAL"
    with pytest.raises(InvalidAction):
        world.run("automation", "Set Health Status", spacecraft_id="MINISAT-1", health_status="FINE")


# ------------------------------------------------------------------------------------------------ anomalies

def anomaly(world, who="alice", severity="MEDIUM", **extra):
    return world.run(who, "Open Anomaly", spacecraft_id="MINISAT-1", title="Unplanned SAFE mode", severity=severity,
                     **extra)


def test_an_anomaly_gathers_the_alarms_events_and_commands_involved(world):
    alarm = raise_alarm(world).result["alarm_id"]
    fdir = event(world).result["event_id"]
    command = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")
    eid = command.result["execution_id"]
    result = anomaly(world, alarm_ids=[alarm], event_ids=[fdir], execution_ids=[eid])
    aid = result.result["anomaly_id"]
    row = world.row("SELECT * FROM ops.anomaly WHERE anomaly_id = %s", aid)
    assert (row["status"], row["severity"], row["opened_by"], row["detected_at"]) == ("OPEN", "MEDIUM", "alice",
                                                                                      world.clock.now)
    assert str(world.row("SELECT anomaly_id FROM ops.alarm")["anomaly_id"]) == aid
    assert str(world.row("SELECT anomaly_id FROM ops.spacecraft_event")["anomaly_id"]) == aid
    assert world.row("SELECT execution_id FROM ops.anomaly_command_execution")["execution_id"] == uuid.UUID(eid)


def test_an_alarm_belongs_to_one_anomaly_only(world):
    alarm = raise_alarm(world).result["alarm_id"]
    anomaly(world, alarm_ids=[alarm])
    with pytest.raises(InvalidAction, match="already part of anomaly"):
        anomaly(world, alarm_ids=[alarm])
    assert world.row("SELECT count(*) AS n FROM ops.anomaly")["n"] == 1        # the failed attempt left nothing behind


@pytest.mark.parametrize("extra, message", [
    ({"alarm_ids": [NO_SUCH]}, "no such alarm"),
    ({"event_ids": [NO_SUCH]}, "no such spacecraft event"),
    ({"execution_ids": [NO_SUCH]}, "does not exist"),
    ({"title": "  "}, "title"),
])
def test_anomaly_references_must_exist(world, extra, message):
    params = dict(spacecraft_id="MINISAT-1", title="Strange", severity="LOW")
    params.update(extra)
    with pytest.raises(InvalidAction, match=message):
        world.run("alice", "Open Anomaly", **params)
    assert world.row("SELECT count(*) AS n FROM ops.anomaly")["n"] == 0


def test_an_agent_and_the_system_may_open_an_anomaly_but_a_viewer_may_not(world):
    anomaly(world, who="helper", severity="LOW")
    anomaly_2 = world.run("automation", "Open Anomaly", spacecraft_id="MINISAT-1", title="Second", severity="LOW")
    assert anomaly_2.result["status"] == "OPEN"
    with pytest.raises(PermissionDenied):
        anomaly(world, who="vera")


def test_only_a_high_severity_anomaly_notifies_supervisors(world):
    anomaly(world, severity="LOW")
    assert world.rows("SELECT * FROM ops.outbox") == []
    result = anomaly(world, severity="HIGH")
    (message,) = world.rows("SELECT * FROM ops.outbox")
    assert message["topic"] == "notify_supervisors" and message["payload"]["anomaly_id"] == result.result["anomaly_id"]


def test_an_anomaly_is_worked_to_resolution_in_order(world):
    aid = anomaly(world).result["anomaly_id"]
    with pytest.raises(InvalidAction, match="can move only to: INVESTIGATING"):
        world.run("alice", "Update Anomaly", anomaly_id=aid, status="RESOLVED", root_cause="skipped a step")
    world.run("alice", "Update Anomaly", anomaly_id=aid, status="INVESTIGATING")
    with pytest.raises(InvalidAction, match="root cause"):
        world.run("alice", "Update Anomaly", anomaly_id=aid, status="RESOLVED")
    with pytest.raises(InvalidAction, match="root cause"):
        world.run("alice", "Update Anomaly", anomaly_id=aid, status="RESOLVED", root_cause="   ")
    command = world.run("bob", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="recover")
    world.clock.advance(120)
    world.run("alice", "Update Anomaly", anomaly_id=aid, status="RESOLVED",
              root_cause="payload left on across two eclipses", resolution_note="back to NOMINAL",
              execution_ids=[command.result["execution_id"]])
    row = world.row("SELECT * FROM ops.anomaly WHERE anomaly_id = %s", aid)
    assert (row["status"], row["root_cause"], row["resolution_note"]) == ("RESOLVED",
                                                                          "payload left on across two eclipses",
                                                                          "back to NOMINAL")
    assert row["resolved_at"] == world.clock.now
    assert world.row("SELECT count(*) AS n FROM ops.anomaly_command_execution")["n"] == 1
    with pytest.raises(InvalidAction, match="resolved for good"):
        world.run("alice", "Update Anomaly", anomaly_id=aid, status="INVESTIGATING")


@pytest.mark.parametrize("who", ["vera", "helper", "automation"])
def test_viewers_agents_and_the_system_cannot_work_an_anomaly(world, who):
    aid = anomaly(world).result["anomaly_id"]
    with pytest.raises(PermissionDenied):
        world.run(who, "Update Anomaly", anomaly_id=aid, status="INVESTIGATING")


# ------------------------------------------------------------------------------------------------ contacts

def plan(world, start_min, end_min, who="sam", station="HEL"):
    from datetime import timedelta
    return world.run(who, "Plan Contact", spacecraft_id="MINISAT-1", station_id=station,
                     start_at=(world.clock.now + timedelta(minutes=start_min)).isoformat(),
                     end_at=(world.clock.now + timedelta(minutes=end_min)).isoformat(), max_elevation_deg=62.5)


def test_a_supervisor_plans_contacts_that_do_not_overlap(world):
    result = plan(world, 10, 20)
    row = world.row("SELECT * FROM ops.contact_window WHERE contact_id = %s", result.result["contact_id"])
    assert (row["status"], row["created_by"], row["max_elevation_deg"]) == ("PLANNED", "sam", 62.5)
    plan(world, 20, 30)                                                        # back to back
    with pytest.raises(InvalidAction, match="overlaps"):
        plan(world, 15, 25)
    assert world.row("SELECT count(*) AS n FROM ops.contact_window")["n"] == 2


@pytest.mark.parametrize("override, message", [
    ({"station_id": "MARS"}, "unknown ground station"),
    ({"end_at": "2020-01-01T00:00:00+00:00", "start_at": "2020-01-02T00:00:00+00:00"}, "end after it starts"),
    ({"start_at": "2026-10-31T12:00:00", "end_at": "2026-10-31T13:00:00"}, "time zone"),
])
def test_contact_input_is_validated(world, override, message):
    params = dict(spacecraft_id="MINISAT-1", station_id="HEL", start_at="2026-10-31T12:00:00+00:00",
                  end_at="2026-10-31T13:00:00+00:00")
    params.update(override)
    with pytest.raises(InvalidAction, match=message):
        world.run("sam", "Plan Contact", **params)


def test_an_operator_cannot_plan_a_contact(world):
    with pytest.raises(PermissionDenied):
        plan(world, 10, 20, who="alice")
