"""The read routes: objects, links, filters, paging, and what each role may see. Expected values are worked out from the
specification (limits, packet sizes) and from the scenario each test builds, not from the code under test."""
from datetime import timedelta

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("psycopg")


def propose(api, who="alice", command="Noop", arguments=None, reason="link check", **extra):
    return api.result(who, "Propose Command", spacecraft_id="MINISAT-1", command=command, arguments=arguments or {},
                      reason=reason, **extra)["execution_id"]


# ------------------------------------------------------------------------------------------------ definitions

def test_definitions_come_from_the_specification(api):
    document = api.ok(api.get("vera", "/api/definitions"))
    assert document["mission_name"] == "MiniSat"
    sizes = {p["apid"]: p["size_bytes"] for p in document["packet_types"]}
    assert sizes == {100: 47, 101: 26}                                  # hand-counted, as in the README
    assert [c["name"] for c in document["commands"]] == ["Noop", "SetMode", "SetHeater", "Reboot", "SetTmRate"]
    assert {c["name"]: c["significance"] for c in document["commands"]}["Reboot"] == "VITAL"
    housekeeping = next(p for p in document["packet_types"] if p["apid"] == 100)
    assert [x["name"] for x in housekeeping["parameters"]][:3] == ["mode", "cmd_accepted", "cmd_rejected"]      # wire order


def test_a_parameter_carries_its_limits_and_enum_labels(api):
    soc = api.ok(api.get("vera", "/api/definitions/parameters/battery_soc_pct"))
    assert (soc["unit"], soc["warning"], soc["critical"]) == ("%", [35, None], [20, None])
    mode = api.ok(api.get("vera", "/api/definitions/parameters/mode"))
    assert mode["enum_labels"] == [{"label": "SAFE", "value": 0}, {"label": "NOMINAL", "value": 1}, {"label": "PAYLOAD", "value": 2}]
    assert mode["warning"] is None
    set_mode = api.ok(api.get("vera", "/api/definitions/commands/SetMode"))
    assert set_mode["arguments"][0]["name"] == "mode" and set_mode["command_id"] == 2


@pytest.mark.parametrize("path", ["/api/definitions/parameters/nope", "/api/definitions/commands/Explode",
                                  "/api/definitions/packet-types/999"])
def test_unknown_definitions_are_404(api, path):
    assert api.get("vera", path).status_code == 404


def test_reads_run_in_a_read_only_transaction_with_a_time_limit(api):
    """Defence in depth: the reader role cannot write anyway, and no query may run for more than five seconds."""
    with api.app.state.ctx.store.session() as conn:
        assert conn.execute("SHOW transaction_read_only").fetchone()["transaction_read_only"] == "on"
        assert conn.execute("SHOW statement_timeout").fetchone()["statement_timeout"] == "5s"


# ------------------------------------------------------------------------------------------------ spacecraft

def test_a_spacecraft_without_telemetry_says_so(api):
    sc = api.ok(api.get("vera", "/api/spacecraft/MINISAT-1"))
    assert (sc["health_status"], sc["mode"], sc["last_contact_at"], sc["telemetry_stale"]) == ("NOMINAL", None, None, True)
    assert sc["values"] == {} and sc["parameters"] == []


def test_a_spacecraft_shows_its_newest_values_read_against_their_limits(api, ground):
    g = ground(soc=0.30)
    g.run(3)
    sc = api.ok(api.get("vera", "/api/spacecraft/MINISAT-1"))
    assert sc["mode"] == "NOMINAL" and sc["telemetry_stale"] is False and sc["telemetry_age_s"] == 0.0
    parameters = {p["name"]: p for p in sc["parameters"]}
    assert parameters["battery_soc_pct"]["severity"] == "WARNING"            # 30 % is below the 35 % warning, above the 20 % critical
    assert parameters["battery_soc_pct"]["warning"] == [35, None] and parameters["battery_soc_pct"]["unit"] == "%"
    assert parameters["mode"]["label"] == "NOMINAL" and parameters["mode"]["severity"] is None
    assert parameters["in_eclipse"]["label"] == "NO"
    assert sc["health_status"] == "WARNING"                                  # the automation set it
    assert sc["values"]["uptime_s"] == 3
    assert [p["name"] for p in sc["parameters"]][:2] == ["mode", "cmd_accepted"]      # in wire order


def test_telemetry_is_stale_after_three_housekeeping_periods(api, ground):
    g = ground()
    g.run(2)
    assert api.ok(api.get("vera", "/api/spacecraft/MINISAT-1"))["telemetry_stale"] is False
    api.world.clock.advance(3.0)
    fresh = api.ok(api.get("vera", "/api/spacecraft/MINISAT-1"))
    assert fresh["telemetry_age_s"] == 3.0 and fresh["telemetry_stale"] is False         # 3 periods is still fine
    api.world.clock.advance(0.5)
    assert api.ok(api.get("vera", "/api/spacecraft/MINISAT-1"))["telemetry_stale"] is True


def test_an_unknown_spacecraft_is_404_on_every_route_that_names_one(api):
    for path in ("", "/alarms", "/commands", "/events", "/anomalies", "/contacts", "/series/mode"):
        assert api.get("alice", f"/api/spacecraft/NOPE{path}").status_code == 404, path
    assert api.get("alice", "/api/spacecraft/NOPE/packet-loss", **{"from": "2026-01-01T00:00:00Z",
                                                                    "to": "2026-01-02T00:00:00Z"}).status_code == 404
    assert api.post("alice", "/api/functions/preflight-command",
                    {"spacecraft_id": "NOPE", "command": "Noop"}).status_code == 404


# ------------------------------------------------------------------------------------------------ operators

def test_only_a_supervisor_sees_roles_the_others_see_display_names(api):
    others = api.items("alice", "/api/operators")
    assert {o["operator_id"] for o in others} == {"alice", "bob", "sam", "tina", "vera", "helper", "automation"}
    assert all(set(o) == {"operator_id", "display_name"} for o in others)
    full = {o["operator_id"]: o for o in api.items("sam", "/api/operators")}
    assert (full["vera"]["role"], full["helper"]["kind"], full["automation"]["role"]) == ("VIEWER", "AGENT", "SYSTEM")
    assert api.ok(api.get("alice", "/api/me")) == {"operator_id": "alice", "display_name": "Alice", "kind": "HUMAN", "role": "OPERATOR"}


# ------------------------------------------------------------------------------------------------ commands and their links

def test_a_command_execution_shows_what_an_approver_needs(api, ground):
    ground(soc=0.8).run(2)
    eid = propose(api, command="SetMode", arguments={"mode": "PAYLOAD"}, reason="payload pass")
    command = api.ok(api.get("alice", f"/api/command-executions/{eid}"))
    assert (command["status"], command["command_name"], command["vital"], command["proposed_by"]) == (
        "PROPOSED", "SetMode", False, "alice")
    assert command["arguments"] == {"mode": 2} and command["arguments_text"] == {"mode": "PAYLOAD"}
    assert command["raw_bytes_hex"] == "100ac0000002000202"                  # the bytes the approver is approving
    assert command["preflight"]["accepted"] is True and command["state_snapshot"]["battery_soc_pct"] > 79
    assert command["expected_effect"] == [{"parameter": "mode", "op": "eq", "value": 2}]
    assert command["contact"] is None and command["approved_by"] is None
    assert api.get("alice", "/api/command-executions/00000000-0000-0000-0000-000000000000").status_code == 404


def test_command_lists_filter_by_status_command_and_time_and_are_newest_first(api):
    first = propose(api, command="Noop")
    api.world.clock.advance(60)
    second = propose(api, command="SetHeater", arguments={"state": "ON"}, reason="warm")
    api.world.clock.advance(60)
    third = propose(api, who="bob", command="SetTmRate", arguments={"period_s": 2.0}, reason="slow down")
    api.result("sam", "Cancel Command", execution_id=second, reason="not needed")

    def ids(**params):
        return [c["execution_id"] for c in api.items("vera", "/api/spacecraft/MINISAT-1/commands", **params)]
    assert ids() == [third, second, first]
    assert ids(status="CANCELLED") == [second]
    assert ids(status="PROPOSED,CANCELLED") == [third, second, first]
    assert ids(command="Noop") == [first]
    cut = (api.world.clock.now - timedelta(seconds=90)).isoformat()
    assert ids(since=cut) == [third, second]
    assert ids(until=cut) == [first]
    assert ids(limit=1) == [third] and ids(limit=1, offset=1) == [second] and ids(limit=1, offset=3) == []


def test_filters_with_nonsense_values_are_refused_not_ignored(api):
    for params in ({"status": "FLYING"}, {"status": "PROPOSED,NOPE"}, {"since": "2026-01-01T00:00:00"},
                   {"limit": 0}, {"limit": 501}, {"offset": -1}, {"responds_to_alarm_id": "not-a-uuid"}):
        assert api.get("alice", "/api/spacecraft/MINISAT-1/commands", **params).status_code == 422, params
    assert api.get("alice", "/api/spacecraft/MINISAT-1/alarms", state="OPEN").status_code == 422
    assert api.get("alice", "/api/spacecraft/MINISAT-1/events", type="EXPLOSION").status_code == 422
    assert api.get("alice", "/api/spacecraft/MINISAT-1/anomalies", status="CLOSED").status_code == 422


def test_a_released_command_names_the_contact_and_the_station(api):
    window = api.result("sam", "Plan Contact", spacecraft_id="MINISAT-1", station_id="HEL",
                        start_at=(api.world.clock.now - timedelta(minutes=1)).isoformat(),
                        end_at=(api.world.clock.now + timedelta(minutes=9)).isoformat(), max_elevation_deg=62.5)
    eid = propose(api)
    api.result("bob", "Approve Command", execution_id=eid)
    api.result("bob", "Release Command", execution_id=eid)
    command = api.ok(api.get("vera", f"/api/command-executions/{eid}"))
    assert command["status"] == "RELEASED" and command["approved_by"] == "bob"
    assert command["contact"]["contact_id"] == window["contact_id"] and command["contact"]["station_id"] == "HEL"
    contact = api.ok(api.get("vera", f"/api/contacts/{window['contact_id']}"))
    assert contact["max_elevation_deg"] == 62.5 and [c["execution_id"] for c in contact["commands"]] == [eid]


# ------------------------------------------------------------------------------------------------ alarms and anomalies

def test_alarms_events_and_anomalies_link_to_each_other(api, ground):
    g = ground(soc=0.30)
    g.run(2)
    alarms = api.items("vera", "/api/spacecraft/MINISAT-1/alarms", state="ACTIVE")
    assert [(a["parameter_name"], a["severity"], a["state"]) for a in alarms] == [("battery_soc_pct", "WARNING", "ACTIVE")]
    assert alarms[0]["limit_violated"] == "below warning minimum 35"
    api.result("alice", "Acknowledge Alarm", alarm_id=alarms[0]["alarm_id"], note="seen")
    assert api.items("vera", "/api/spacecraft/MINISAT-1/alarms", state="ACTIVE") == []
    acknowledged = api.items("vera", "/api/spacecraft/MINISAT-1/alarms", state="ACKNOWLEDGED")[0]
    assert (acknowledged["acknowledged_by"], acknowledged["acknowledge_note"]) == ("alice", "seen")

    anomaly = api.result("alice", "Open Anomaly", spacecraft_id="MINISAT-1", title="Battery low", severity="MEDIUM",
                         alarm_ids=[acknowledged["alarm_id"]])["anomaly_id"]
    one = api.ok(api.get("vera", f"/api/anomalies/{anomaly}"))
    assert one["status"] == "OPEN" and [a["alarm_id"] for a in one["alarms"]] == [acknowledged["alarm_id"]]
    assert one["events"] == [] and one["commands"] == []
    assert [a["anomaly_id"] for a in api.items("vera", "/api/spacecraft/MINISAT-1/anomalies", status="OPEN")] == [anomaly]
    assert api.items("vera", "/api/spacecraft/MINISAT-1/anomalies", status="RESOLVED") == []


def test_a_single_alarm_lists_the_commands_sent_in_response(api, ground):
    ground(soc=0.30).run(2)
    alarm = api.items("vera", "/api/spacecraft/MINISAT-1/alarms")[0]["alarm_id"]
    eid = propose(api, command="SetHeater", arguments={"state": "ON"}, reason="warm the battery", responds_to_alarm_id=alarm)
    other = propose(api, who="bob", command="Noop")
    one = api.ok(api.get("vera", f"/api/alarms/{alarm}"))
    assert [c["execution_id"] for c in one["responding_commands"]] == [eid] and other not in str(one)
    filtered = api.items("vera", "/api/spacecraft/MINISAT-1/commands", responds_to_alarm_id=alarm)
    assert [c["execution_id"] for c in filtered] == [eid]


def test_ground_stations_are_listed(api):
    (station,) = api.items("vera", "/api/ground-stations")
    assert (station["station_id"], station["name"], station["latitude_deg"]) == ("HEL", "Helsinki", 60.2)


# ------------------------------------------------------------------------------------------------ functions

def test_preflight_judges_the_command_the_proposal_would_carry(api, ground):
    ground(soc=0.25).run(2)                                           # 25 %: below the 30 % PAYLOAD needs
    audited = len(api.world.audit())                                  # the automations have already written their rows
    body = {"spacecraft_id": "MINISAT-1", "command": "SetMode", "arguments": {"mode": "PAYLOAD"}}
    refused = api.ok(api.post("vera", "/api/functions/preflight-command", body))
    assert (refused["known"], refused["accepted"], refused["arguments"]) == (True, False, {"mode": 2})
    assert "battery too low for PAYLOAD" in refused["reason"] and refused["stale"] is False
    fine = api.ok(api.post("vera", "/api/functions/preflight-command", {**body, "arguments": {"mode": "NOMINAL"}}))
    assert fine["accepted"] is True and fine["reason"] is None
    assert len(api.world.audit()) == audited, "a preflight changes nothing and is not an action"


@pytest.mark.parametrize("body", [{"spacecraft_id": "MINISAT-1", "command": "Explode"},
                                  {"spacecraft_id": "MINISAT-1", "command": "SetMode", "arguments": {"mode": "WARP"}},
                                  {"spacecraft_id": "MINISAT-1", "command": "SetTmRate", "arguments": {"period_s": 500}},
                                  {"spacecraft_id": "MINISAT-1", "command": "Noop", "extra": 1}, {"command": "Noop"}])
def test_preflight_refuses_what_a_proposal_would_refuse(api, body):
    assert api.post("vera", "/api/functions/preflight-command", body).status_code == 422
