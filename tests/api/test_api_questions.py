"""PLAN.md phase 4, "done when": the six questions of ontology.md section 9 can be answered through the API.

Each test builds the situation with the real parts (the satellite model, UDP-format packets, the ingestor, the automations, the
outbox worker, the action runner behind HTTP) and then asks the question the way a client would: by navigating from one
object to the next. The expected answers come from the scenario each test sets up and, for question 5, from running the real
satellite model forward, not from the API code.
"""
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("psycopg")

from minisat.model import MODE_SAFE, Orbit, Spacecraft  # noqa: E402

SC = "/api/spacecraft/MINISAT-1"


def open_contact(api, before_min=5, after_min=120):
    """A contact window around now, planned by a supervisor (releasing a command needs one)."""
    now = api.world.clock.now
    return api.result("sam", "Plan Contact", spacecraft_id="MINISAT-1", station_id="HEL",
                      start_at=(now - timedelta(minutes=before_min)).isoformat(),
                      end_at=(now + timedelta(minutes=after_min)).isoformat())["contact_id"]


def propose(api, who, command, arguments=None, reason="scripted", **extra):
    return api.result(who, "Propose Command", spacecraft_id="MINISAT-1", command=command, arguments=arguments or {},
                      reason=reason, **extra)["execution_id"]


def get_command(api, eid):
    return api.ok(api.get("vera", f"/api/command-executions/{eid}"))


def fly(api, ground, who, command, arguments=None, approver="bob", seconds=3, **extra):
    """Propose, approve, release, send, and let the satellite answer; returns the execution id."""
    eid = propose(api, who, command, arguments, **extra)
    api.result(approver, "Approve Command", execution_id=eid)
    api.result(approver, "Release Command", execution_id=eid)
    assert ground.send_released() == 1
    ground.run(seconds)
    return eid


# ------------------------------------------------------------------------------------------------ 1

def test_q1_which_alarms_are_active_and_what_commands_were_sent_in_response(api, ground):
    g = ground(soc=0.30)                                                        # below the 35 % warning limit
    g.run(2)
    open_contact(api)

    active = api.items("vera", f"{SC}/alarms", state="ACTIVE")
    assert [(a["parameter_name"], a["severity"]) for a in active] == [("battery_soc_pct", "WARNING")]
    alarm = active[0]["alarm_id"]

    eid = fly(api, g, "alice", "SetHeater", {"state": "ON"}, reason="keep the battery warm", responds_to_alarm_id=alarm)
    other = fly(api, g, "alice", "Noop", reason="link check")                   # not a response to anything

    # The heater draws 0.35 A more. The terminal voltage was 6.0 + 2.4 * 0.30 + 0.15 * (1.06 - 0.45) = 6.81 V, just above its
    # 6.8 V warning limit; with the heater it is 6.72 + 0.15 * (1.06 - 0.80) = 6.76 V. So the command that answers one alarm
    # raises another, and "which alarms are active" now has two answers.
    still_active = {a["parameter_name"]: a for a in api.items("vera", f"{SC}/alarms", state="ACTIVE")}
    assert set(still_active) == {"battery_soc_pct", "battery_voltage"} and still_active["battery_soc_pct"]["alarm_id"] == alarm

    # navigating from each active alarm to the commands sent because of it
    responses = api.ok(api.get("vera", f"/api/alarms/{alarm}"))["responding_commands"]
    assert [(c["execution_id"], c["command_name"], c["status"]) for c in responses] == [(eid, "SetHeater", "VERIFIED")]
    voltage = still_active["battery_voltage"]["alarm_id"]
    assert api.ok(api.get("vera", f"/api/alarms/{voltage}"))["responding_commands"] == []
    assert other not in [c["execution_id"] for c in responses]
    # the same answer from the command side
    assert [c["execution_id"] for c in api.items("vera", f"{SC}/commands", responds_to_alarm_id=alarm)] == [eid]


# ------------------------------------------------------------------------------------------------ 2

def test_q2_why_is_the_spacecraft_in_safe_mode(api, ground):
    """events -> anomaly -> alarms, the last PAYLOAD command, and the charge before it."""
    g = ground(soc=0.50, start_t=1830.0)                                        # the eclipse begins at t = 1833 s
    g.run(5)
    open_contact(api)
    payload = fly(api, g, "alice", "SetMode", {"mode": "PAYLOAD"}, reason="payload pass")
    assert get_command(api, payload)["status"] == "VERIFIED"
    sent_at = get_command(api, payload)["sent_at"]
    g.sim.model.soc = 0.1503                                                    # hours of drain later, a few seconds from 15 %
    g.run(12)

    assert api.ok(api.get("vera", SC))["health_status"] == "SAFE_MODE"
    assert api.ok(api.get("vera", SC))["mode"] == "SAFE"

    (fdir,) = api.items("vera", f"{SC}/events", type="FDIR")
    assert fdir["anomaly_id"] is not None and fdir["details"]["battery_soc_pct"] < 15.0
    anomaly = api.ok(api.get("vera", f"/api/anomalies/{fdir['anomaly_id']}"))
    assert (anomaly["title"], anomaly["severity"], anomaly["status"]) == ("Unplanned SAFE mode", "HIGH", "OPEN")
    assert fdir["event_id"] in [e["event_id"] for e in anomaly["events"]]
    linked = {a["parameter_name"]: a["severity"] for a in anomaly["alarms"]}
    assert linked["battery_soc_pct"] == "CRITICAL"                              # 15 % is below the 20 % critical limit

    # the last command that put the satellite in PAYLOAD mode, and that it went through
    mode_commands = api.items("vera", f"{SC}/commands", command="SetMode")
    last_payload = next(c for c in mode_commands if c["arguments_text"] == {"mode": "PAYLOAD"})
    assert last_payload["execution_id"] == payload and last_payload["proposed_by"] == "alice"

    # the charge from the command to the fault: falling, and below 15 % at the end
    series = api.ok(api.get("vera", f"{SC}/series/battery_soc_pct", **{"from": sent_at, "to": fdir["occurred_at"], "max_points": 200}))
    values = [p["v"] for p in series["points"]]
    after_drop = values[values.index(next(v for v in values if v < 16.0)):]
    assert len(values) > 5 and after_drop == sorted(after_drop, reverse=True), "in eclipse under PAYLOAD load the charge only falls"
    assert values[-1] < 15.0 and series["parameter"]["critical"] == [20, None]
    assert fdir["occurred_at"] > sent_at


# ------------------------------------------------------------------------------------------------ 3

def test_q3_did_the_payload_command_take_effect_and_if_not_why(api, ground):
    g = ground(soc=0.60)
    g.run(3)
    open_contact(api)
    worked = fly(api, g, "alice", "SetMode", {"mode": "PAYLOAD"}, reason="first payload pass")
    fly(api, g, "alice", "SetMode", {"mode": "NOMINAL"}, reason="back to nominal")
    g.sim.model.soc = 0.25                                                      # PAYLOAD needs 30 %
    g.run(3)
    api.world.clock.advance(120)                                                # two minutes pass
    moment = api.world.clock.now

    refused_by_preflight = propose(api, "alice", "SetMode", {"mode": "PAYLOAD"}, reason="second payload pass")
    proposed = get_command(api, refused_by_preflight)
    assert proposed["preflight"]["accepted"] is False                           # the proposal already carries the warning
    attempt = api.act("alice", "Approve Command", execution_id=refused_by_preflight)
    assert attempt.status_code == 422 and "only a supervisor may approve it anyway" in attempt.json()["detail"]
    api.result("sam", "Approve Command", execution_id=refused_by_preflight, note="payload data is worth the risk")
    api.result("sam", "Release Command", execution_id=refused_by_preflight)
    assert g.send_released() == 1
    g.run(3)

    # "the SetMode PAYLOAD I sent around then": found by time, command name and argument
    window = {"since": (moment - timedelta(seconds=30)).isoformat(), "until": (moment + timedelta(seconds=30)).isoformat()}
    found = [c for c in api.items("vera", f"{SC}/commands", command="SetMode", **window) if c["arguments_text"] == {"mode": "PAYLOAD"}]
    assert [c["execution_id"] for c in found] == [refused_by_preflight]
    answer = found[0]
    assert answer["status"] == "REJECTED_ONBOARD"                               # it did not take effect
    assert "rejected on board" in answer["rejection_reason"]                    # what the ground can say about why
    assert answer["preflight"]["accepted"] is False and "battery too low for PAYLOAD mode (25 % < 30 %)" in answer["preflight"]["reason"]
    assert answer["approval_note"] == "payload data is worth the risk" and answer["approved_by"] == "sam"
    assert answer["state_snapshot"]["battery_soc_pct"] == pytest.approx(25.0, abs=0.1)
    assert api.ok(api.get("vera", SC))["values"]["mode"] == 1                   # still NOMINAL
    assert get_command(api, worked)["status"] == "VERIFIED"                     # and the earlier one did take effect


# ------------------------------------------------------------------------------------------------ 4

def test_q4_who_approved_the_last_reboot_and_during_which_contact(api, ground):
    g = ground()
    g.run(3)
    first_contact = open_contact(api, before_min=1, after_min=1)
    first = fly(api, g, "alice", "Reboot", approver="sam", reason="clear a fault")            # alice proposes, sam approves
    g.run(3)
    api.world.clock.advance(3600)                                                # an hour later, another pass
    second_contact = open_contact(api, before_min=1, after_min=10)
    assert first_contact != second_contact
    second = fly(api, g, "sam", "Reboot", approver="tina", reason="second reboot")            # sam proposes, tina approves
    g.run(3)

    last = api.items("vera", f"{SC}/commands", command="Reboot", limit=1)[0]
    assert last["execution_id"] == second and last["status"] == "VERIFIED"
    assert (last["proposed_by"], last["approved_by"]) == ("sam", "tina")
    assert last["contact"]["contact_id"] == second_contact and last["contact"]["station_id"] == "HEL"
    people = {o["operator_id"]: o["display_name"] for o in api.items("vera", "/api/operators")}
    assert people[last["approved_by"]] == "Tina"
    contact = api.ok(api.get("vera", f"/api/contacts/{last['contact']['contact_id']}"))
    assert [c["execution_id"] for c in contact["commands"]] == [second]
    # the earlier reboot belongs to the earlier contact and another approver
    older = get_command(api, first)
    assert (older["approved_by"], older["contact"]["contact_id"]) == ("sam", first_contact)


# ------------------------------------------------------------------------------------------------ 5

def test_q5_if_i_switch_to_payload_now_when_would_the_battery_reach_the_fdir_limit(api, ground):
    g = ground(soc=0.35, start_t=1800.0)                                         # sunlit; the eclipse starts at 1833.5 s
    g.run(100)                                                                   # now at 1900 s: 66 s into the eclipse
    body = {"spacecraft_id": "MINISAT-1", "command": "SetMode", "arguments": {"mode": "PAYLOAD"}}
    answer = api.ok(api.post("vera", "/api/functions/estimate-time-to-safe", body))

    # the truth: the real satellite model, in exactly this state, with PAYLOAD switched on, run second by second
    model = g.sim.model
    real = Spacecraft(orbit=Orbit(), soc=model.soc, mode=2, heater=model.heater, t=model.t)
    seconds = 0
    while real.mode != MODE_SAFE and seconds < 6 * 3600:
        real.step(1.0)
        seconds += 1
    assert 0 < seconds < 6 * 3600, "this scenario is supposed to reach FDIR within the horizon"

    assert answer["preflight"]["accepted"] is True                               # 35 % >= the 30 % PAYLOAD needs
    estimate = answer["time_to_safe"]
    assert estimate["known"] and estimate["reaches_safe"] and estimate["phase_known"] and estimate["command_accepted"] is True
    assert estimate["seconds"] == pytest.approx(seconds, abs=10.0 + 0.01 * seconds)
    assert estimate["min_soc_pct"] < 15.0 + 0.1 and estimate["assumptions"]
    # and without the command, from the same state, the charge is not going anywhere near the limit
    plain = api.ok(api.post("vera", "/api/functions/estimate-time-to-safe", {"spacecraft_id": "MINISAT-1"}))
    assert plain["preflight"] is None and plain["time_to_safe"]["reaches_safe"] is False


def test_q5_a_command_the_satellite_would_refuse_is_flagged_and_changes_nothing(api, ground):
    g = ground(soc=0.25, start_t=1800.0)
    g.run(100)
    body = {"spacecraft_id": "MINISAT-1", "command": "SetMode", "arguments": {"mode": "PAYLOAD"}}
    answer = api.ok(api.post("vera", "/api/functions/estimate-time-to-safe", body))
    assert answer["preflight"]["accepted"] is False
    assert answer["time_to_safe"]["command_accepted"] is False
    baseline = api.ok(api.post("vera", "/api/functions/estimate-time-to-safe", {"spacecraft_id": "MINISAT-1"}))
    assert answer["time_to_safe"]["seconds"] == baseline["time_to_safe"]["seconds"]


def test_q5_without_telemetry_it_says_it_does_not_know(api):
    answer = api.ok(api.post("vera", "/api/functions/estimate-time-to-safe", {"spacecraft_id": "MINISAT-1"}))
    assert answer["time_to_safe"]["known"] is False and answer["time_to_safe"]["seconds"] is None


# ------------------------------------------------------------------------------------------------ 6

def test_q6_how_many_packets_did_we_lose_in_the_third_pass(api, ground):
    """Three passes of 20 s each. Housekeeping packets that never reach the ground are chosen by hand: two single losses
    in the first pass, none in the second, three in a row in the third, and one between the second and the third."""
    g = ground()
    g.run(1)                                                                     # spacecraft time now equals the clock
    t0 = api.world.clock.now
    passes = [(0, 20), (30, 50), (60, 80)]
    for start, end in passes:
        api.result("sam", "Plan Contact", spacecraft_id="MINISAT-1", station_id="HEL",
                   start_at=(t0 + timedelta(seconds=start)).isoformat(), end_at=(t0 + timedelta(seconds=end)).isoformat())
    lost_at = {5, 12, 25, 65, 66, 67}                                            # seconds after t0 whose packet is lost
    g.run(90, lose={s - 1 for s in lost_at})                                     # the packet of second s is index s - 1

    window = {"since": (t0 - timedelta(hours=1)).isoformat(), "until": (t0 + timedelta(hours=1)).isoformat()}
    contacts = api.items("vera", f"{SC}/contacts", **window)
    assert [c["start_at"] for c in contacts] == sorted(c["start_at"] for c in contacts) and len(contacts) == 3
    third = contacts[2]
    assert third["start_at"].startswith((t0 + timedelta(seconds=60)).isoformat()[:19])
    assert (third["packets_lost_observed"], third["packet_loss_events"]) == (3, 1)           # 65, 66, 67 are one gap of three
    assert [(c["packets_lost_observed"], c["packet_loss_events"]) for c in contacts] == [(2, 2), (0, 0), (3, 1)]

    # the same number straight from the window, and from the contact object
    start, end = (t0 + timedelta(seconds=60)).isoformat(), (t0 + timedelta(seconds=80)).isoformat()
    loss = api.ok(api.get("vera", f"{SC}/packet-loss", **{"from": start, "to": end}))
    assert (loss["lost"], loss["events"]) == (3, 1)
    assert api.ok(api.get("vera", f"/api/contacts/{third['contact_id']}"))["packets_lost_observed"] == 3
    everything = api.ok(api.get("vera", f"{SC}/packet-loss", **{"from": window["since"], "to": window["until"]}))
    assert everything["lost"] == len(lost_at) == 6                                # the loss between passes counts only in total
    empty = api.ok(api.get("vera", f"{SC}/packet-loss", **{"from": (t0 + timedelta(hours=5)).isoformat(),
                                                           "to": (t0 + timedelta(hours=6)).isoformat()}))
    assert (empty["lost"], empty["events"]) == (0, 0)


def test_q6_a_window_that_ends_before_it_starts_is_refused(api):
    response = api.get("vera", f"{SC}/packet-loss", **{"from": "2026-01-02T00:00:00Z", "to": "2026-01-01T00:00:00Z"})
    assert response.status_code == 422
