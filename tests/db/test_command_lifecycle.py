"""The command lifecycle (protocols/command-safety-protocol.md), driven through the action runner.

Expected values are worked out by hand (bytes, boundaries, who may do what), not copied from the implementation.
"""
from datetime import timedelta

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic")

from dbfixtures import World  # noqa: E402
from minisat.codec import decode_tm  # noqa: E402
from minisat.model import Spacecraft  # noqa: E402
from minisat.ontology.functions import command_signal, effects_met  # noqa: E402
from minisat.ontology.runner import InvalidAction, PermissionDenied, RunnerConfig  # noqa: E402
from minisat.simulator import Simulator  # noqa: E402

ALL_STATUSES = ["PROPOSED", "APPROVED", "RELEASED", "SENT", "ACCEPTED", "REJECTED_ONBOARD", "VERIFIED", "FAILED",
                "CANCELLED"]


def propose(world, command="Noop", arguments=None, who="alice", reason="link test", **extra):
    return world.run(who, "Propose Command", spacecraft_id="MINISAT-1", command=command, arguments=arguments or {},
                     reason=reason, **extra)


def release_with_override(world, eid, who="sam"):
    return world.run(who, "Release Command", execution_id=eid, override_reason="test without a contact window")


def send(world, eid):
    """What the outbox worker does: mark the command as sent."""
    outbox = world.row("SELECT outbox_id FROM ops.outbox WHERE payload->>'execution_id' = %s", eid)
    return world.run("automation", "Record Command Sent", execution_id=eid, outbox_id=outbox["outbox_id"])


def outcome(world, eid, kind, reason=None):
    return world.run("automation", "Record Command Outcome", execution_id=eid, outcome=kind, reason=reason)


def drive(world, status):
    """A Noop execution brought to ``status`` through the real actions."""
    eid = propose(world).result["execution_id"]
    if status == "CANCELLED":
        world.run("alice", "Cancel Command", execution_id=eid, reason="not needed")
        return eid
    steps = {"PROPOSED": [], "APPROVED": ["approve"], "RELEASED": ["approve", "release"],
             "SENT": ["approve", "release", "send"], "ACCEPTED": ["approve", "release", "send", "ACCEPTED"],
             "REJECTED_ONBOARD": ["approve", "release", "send", "REJECTED_ONBOARD"],
             "FAILED": ["approve", "release", "send", "FAILED"],
             "VERIFIED": ["approve", "release", "send", "ACCEPTED", "VERIFIED"]}[status]
    for step in steps:
        if step == "approve":
            world.run("bob", "Approve Command", execution_id=eid)
        elif step == "release":
            release_with_override(world, eid)
        elif step == "send":
            send(world, eid)
        else:
            outcome(world, eid, step, reason="because")
    assert world.execution(eid)["status"] == status
    return eid


# ------------------------------------------------------------------------------------------------ propose

def test_a_proposal_stores_the_exact_bytes_the_approver_will_be_approving(world):
    result = propose(world, "SetMode", {"mode": "PAYLOAD"}, reason="payload pass over Helsinki")
    row = world.execution(result.result["execution_id"])
    # CCSDS header 10 0a c0 00 | length 00 02 | command id 00 02 | mode 02   (as in the README, section 2.5)
    assert row["raw_bytes_hex"] == "100ac0000002000202" == result.result["raw_bytes_hex"]
    assert (row["status"], row["command_id"], row["command_name"], row["arguments"]) == ("PROPOSED", 2, "SetMode",
                                                                                         {"mode": 2})
    assert row["proposed_by"] == "alice" and row["reason"] == "payload pass over Helsinki"
    assert row["expected_effect"] == [{"parameter": "mode", "op": "eq", "value": 2}]
    assert row["expires_at"] - row["proposed_at"] == timedelta(minutes=15)


def test_numeric_and_label_arguments_give_the_same_command(world):
    by_label = propose(world, "SetHeater", {"state": "ON"})
    world.run("alice", "Cancel Command", execution_id=by_label.result["execution_id"], reason="x")
    by_number = propose(world, "SetHeater", {"state": 1})
    assert world.execution(by_number.result["execution_id"])["raw_bytes_hex"] == \
        world.execution(by_label.result["execution_id"])["raw_bytes_hex"]


@pytest.mark.parametrize("override, message", [
    ({"command": "Explode"}, "unknown command"),
    ({"spacecraft_id": "NOPE"}, "unknown spacecraft"),
    ({"command": "SetMode", "arguments": {"mode": "TURBO"}}, "TURBO"),
    ({"command": "SetMode", "arguments": {}}, "missing argument"),
    ({"command": "SetMode", "arguments": {"mode": 1, "extra": 2}}, "unknown argument"),
    ({"command": "SetTmRate", "arguments": {"period_s": 500}}, r"outside the allowed range \[0.1, 60\]"),
    ({"command": "SetTmRate", "arguments": {"period_s": "fast"}}, "."),
    ({"reason": "   "}, "reason"),
    ({"responds_to_alarm_id": "5b1ac9f1-0000-4000-8000-000000000000"}, "does not exist"),
])
def test_invalid_proposals_are_refused_with_the_reason(world, override, message):
    params = dict(spacecraft_id="MINISAT-1", command="Noop", arguments={}, reason="link test")
    params.update(override)
    with pytest.raises(InvalidAction, match=message):
        world.run("alice", "Propose Command", **params)
    assert world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 0


def test_only_one_open_execution_per_command_and_spacecraft(world):
    first = propose(world, "SetHeater", {"state": "ON"})
    with pytest.raises(InvalidAction, match="already has an open execution"):
        propose(world, "SetHeater", {"state": "OFF"})
    propose(world, "Noop")                                              # a different command is fine
    world.run("alice", "Cancel Command", execution_id=first.result["execution_id"], reason="changed my mind")
    propose(world, "SetHeater", {"state": "OFF"})                       # the slot is free again


def test_a_vital_command_is_marked_and_the_proposer_is_told(world):
    result = propose(world, "Reboot", who="sam")
    assert result.result["vital"] is True and world.execution(result.result["execution_id"])["vital"] is True
    assert any("VITAL" in w for w in result.warnings)
    assert propose(world, "Noop").result["vital"] is False


def test_preflight_predicts_the_onboard_rejection_at_the_30_percent_boundary(world):
    world.set_state(mode=1, battery_soc_pct=29.9, heater=0)
    low = propose(world, "SetMode", {"mode": "PAYLOAD"})
    assert low.result["preflight"]["accepted"] is False
    assert "battery too low" in low.result["preflight"]["reason"]
    assert any("REJECT" in w for w in low.warnings)
    world.run("alice", "Cancel Command", execution_id=low.result["execution_id"], reason="x")

    world.set_state(battery_soc_pct=30.0)                                # exactly 30 %: the satellite accepts
    ok = propose(world, "SetMode", {"mode": "PAYLOAD"})
    assert ok.result["preflight"]["accepted"] is True and not any("REJECT" in w for w in ok.warnings)
    assert world.execution(ok.result["execution_id"])["state_snapshot"]["battery_soc_pct"] == 30.0


def test_without_telemetry_the_proposal_works_but_carries_a_warning(world):
    result = propose(world, "SetMode", {"mode": "PAYLOAD"})
    assert result.result["preflight"]["known"] is False
    assert any("no telemetry" in w for w in result.warnings)


def test_old_telemetry_is_flagged_as_stale(world):
    world.set_state(mode=1, battery_soc_pct=80.0, heater=0)
    world.clock.advance(10)                                              # three Housekeeping periods are 3 s
    result = propose(world, "Noop")
    assert result.result["preflight"]["stale"] is True and any("10 s old" in w for w in result.warnings)


# ------------------------------------------------------------------------------------------------ approve

def test_an_operator_approves_a_normal_command(world):
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid, note="looks fine")
    row = world.execution(eid)
    assert (row["status"], row["approved_by"], row["approval_note"]) == ("APPROVED", "bob", "looks fine")
    assert row["approved_at"] == world.clock.now


@pytest.mark.parametrize("who", ["vera", "helper", "automation"])
def test_viewers_agents_and_the_system_cannot_approve(world, who):
    eid = propose(world).result["execution_id"]
    with pytest.raises(PermissionDenied):
        world.run(who, "Approve Command", execution_id=eid)
    assert world.execution(eid)["status"] == "PROPOSED"


def test_an_agent_proposal_needs_a_person_to_approve_it(world):
    eid = propose(world, "Noop", who="helper").result["execution_id"]
    assert world.execution(eid)["proposed_by"] == "helper"
    world.run("alice", "Approve Command", execution_id=eid)
    assert world.execution(eid)["approved_by"] == "alice"


def test_two_person_rule_for_a_vital_command(world):
    eid = propose(world, "Reboot", who="sam").result["execution_id"]
    with pytest.raises(PermissionDenied, match="two-person"):
        world.run("sam", "Approve Command", execution_id=eid)              # the proposer cannot approve it
    with pytest.raises(PermissionDenied, match="supervisor"):
        world.run("alice", "Approve Command", execution_id=eid)            # an operator cannot approve a vital command
    world.run("tina", "Approve Command", execution_id=eid)                 # a different supervisor can
    assert world.execution(eid)["approved_by"] == "tina"


def test_a_vital_command_proposed_by_an_agent_is_approved_by_a_supervisor(world):
    eid = propose(world, "Reboot", who="helper").result["execution_id"]
    with pytest.raises(PermissionDenied):
        world.run("alice", "Approve Command", execution_id=eid)
    world.run("sam", "Approve Command", execution_id=eid)


def test_an_expired_proposal_cannot_be_approved(world):
    eid = propose(world).result["execution_id"]
    world.clock.advance(15 * 60 - 1)
    world.run("bob", "Approve Command", execution_id=eid)                  # one second before it expires
    eid2 = propose(world, "SetHeater", {"state": "ON"}).result["execution_id"]
    world.clock.advance(15 * 60)
    with pytest.raises(InvalidAction, match="expired"):
        world.run("bob", "Approve Command", execution_id=eid2)


def test_only_a_proposed_command_can_be_approved(world):
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    with pytest.raises(InvalidAction, match="only a PROPOSED"):
        world.run("alice", "Approve Command", execution_id=eid)
    with pytest.raises(InvalidAction, match="no such command execution"):
        world.run("alice", "Approve Command", execution_id="5b1ac9f1-0000-4000-8000-000000000000")


def test_a_command_the_satellite_is_predicted_to_reject_needs_a_supervisor_and_a_note(world):
    world.set_state(mode=1, battery_soc_pct=25.0, heater=0)
    eid = propose(world, "SetMode", {"mode": "PAYLOAD"}).result["execution_id"]
    with pytest.raises(InvalidAction, match="predicted to REJECT"):
        world.run("alice", "Approve Command", execution_id=eid)             # an operator cannot override
    with pytest.raises(InvalidAction, match="written note"):
        world.run("sam", "Approve Command", execution_id=eid)               # a supervisor needs a note
    result = world.run("sam", "Approve Command", execution_id=eid, note="deliberate: testing the on-board refusal")
    assert any("REJECT" in w for w in result.warnings)
    row = world.execution(eid)
    assert row["status"] == "APPROVED" and row["preflight"]["accepted"] is False
    assert row["approval_note"].startswith("deliberate")


def test_approval_looks_at_the_state_now_not_at_proposal_time(world):
    world.set_state(mode=1, battery_soc_pct=40.0, heater=0)
    eid = propose(world, "SetMode", {"mode": "PAYLOAD"}).result["execution_id"]
    assert world.execution(eid)["preflight"]["accepted"] is True
    world.clock.advance(60)
    world.set_state(battery_soc_pct=20.0)                                  # the battery drained meanwhile
    with pytest.raises(InvalidAction, match="predicted to REJECT"):
        world.run("alice", "Approve Command", execution_id=eid)


# ------------------------------------------------------------------------------------------------ release

def test_release_needs_a_contact_window_and_queues_the_bytes(world):
    eid = propose(world, "SetHeater", {"state": "ON"}).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    with pytest.raises(InvalidAction, match="no contact window"):
        world.run("bob", "Release Command", execution_id=eid)
    contact = world.contact_window().result["contact_id"]
    result = world.run("bob", "Release Command", execution_id=eid)
    row = world.execution(eid)
    assert (row["status"], str(row["contact_id"]), row["override_reason"]) == ("RELEASED", contact, None)
    assert row["released_at"] == world.clock.now and result.warnings == ()
    (message,) = world.rows("SELECT * FROM ops.outbox")
    assert message["topic"] == "send_telecommand" and message["processed_at"] is None
    assert message["payload"] == {"execution_id": eid, "spacecraft_id": "MINISAT-1", "command": "SetHeater",
                                  "raw_bytes_hex": row["raw_bytes_hex"]}


def test_a_contact_window_in_the_past_or_future_does_not_count(world):
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    for start, end in ((-120, -60), (60, 120)):                              # minutes from now
        world.run("sam", "Plan Contact", spacecraft_id="MINISAT-1", station_id="HEL",
                  start_at=(world.clock.now + timedelta(minutes=start)).isoformat(),
                  end_at=(world.clock.now + timedelta(minutes=end)).isoformat())
    with pytest.raises(InvalidAction, match="no contact window"):
        world.run("bob", "Release Command", execution_id=eid)


def test_only_a_supervisor_can_release_without_a_contact_window_and_it_is_recorded(world):
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    with pytest.raises(PermissionDenied, match="supervisor"):
        release_with_override(world, eid, who="alice")
    with pytest.raises(InvalidAction, match="override_reason"):
        world.run("sam", "Release Command", execution_id=eid)
    result = release_with_override(world, eid, who="sam")
    assert any("without a contact window" in w for w in result.warnings)
    assert world.execution(eid)["override_reason"] == "test without a contact window"


def test_the_contact_requirement_can_be_switched_off_for_a_simulation(fresh_db, spec, clock):
    world = World(fresh_db, spec, clock, config=RunnerConfig(require_contact=False))
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    world.run("bob", "Release Command", execution_id=eid)
    assert world.execution(eid)["status"] == "RELEASED"


def test_only_an_approved_command_can_be_released(world):
    eid = propose(world).result["execution_id"]
    with pytest.raises(InvalidAction, match="only an APPROVED"):
        release_with_override(world, eid)


def test_an_approval_that_waited_too_long_cannot_be_released(world):
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    world.clock.advance(15 * 60)
    with pytest.raises(InvalidAction, match="expired"):
        release_with_override(world, eid)


def test_one_command_in_flight_at_a_time(world):
    first = propose(world, "SetHeater", {"state": "ON"}).result["execution_id"]
    second = propose(world, "Noop").result["execution_id"]
    for eid in (first, second):
        world.run("bob", "Approve Command", execution_id=eid)
    release_with_override(world, first)
    with pytest.raises(InvalidAction, match="still in flight"):
        release_with_override(world, second)
    send(world, first)
    with pytest.raises(InvalidAction, match="still in flight"):                  # SENT is still in flight
        release_with_override(world, second)
    outcome(world, first, "FAILED", reason="no response")
    release_with_override(world, second)                                         # the way is free again


def test_a_vital_command_waits_for_everything_else_to_finish(world):
    normal = propose(world, "Noop").result["execution_id"]
    vital = propose(world, "Reboot", who="sam").result["execution_id"]
    world.run("bob", "Approve Command", execution_id=normal)
    world.run("tina", "Approve Command", execution_id=vital)
    release_with_override(world, normal)
    with pytest.raises(InvalidAction, match="still in flight"):
        release_with_override(world, vital)


# ------------------------------------------------------------------------------------------------ cancel

def test_the_proposer_or_an_operator_can_cancel_and_it_is_recorded(world):
    a = propose(world).result["execution_id"]
    world.run("alice", "Cancel Command", execution_id=a, reason="not needed any more")
    row = world.execution(a)
    assert (row["status"], row["cancelled_by"], row["cancel_reason"]) == ("CANCELLED", "alice", "not needed any more")
    b = propose(world, who="alice").result["execution_id"]
    world.run("bob", "Cancel Command", execution_id=b, reason="wrong spacecraft state")          # another operator
    assert world.execution(b)["cancelled_by"] == "bob"


def test_an_approved_command_can_still_be_cancelled(world):
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    world.run("alice", "Cancel Command", execution_id=eid, reason="situation changed")
    assert world.execution(eid)["status"] == "CANCELLED"


def test_an_agent_cancels_only_its_own_proposals(world):
    mine = propose(world, who="helper").result["execution_id"]
    theirs = propose(world, "SetHeater", {"state": "ON"}, who="alice").result["execution_id"]
    with pytest.raises(PermissionDenied, match="only its own"):
        world.run("helper", "Cancel Command", execution_id=theirs, reason="x")
    world.run("helper", "Cancel Command", execution_id=mine, reason="superseded")
    assert world.execution(mine)["status"] == "CANCELLED"
    assert world.execution(theirs)["status"] == "PROPOSED"


def test_the_system_cancels_only_expired_proposals_of_others(world):
    eid = propose(world).result["execution_id"]
    with pytest.raises(PermissionDenied):
        world.run("automation", "Cancel Command", execution_id=eid, reason="expired")
    world.clock.advance(15 * 60)
    world.run("automation", "Cancel Command", execution_id=eid, reason="expired")
    assert world.execution(eid)["cancelled_by"] == "automation"


@pytest.mark.parametrize("status", ["RELEASED", "SENT", "VERIFIED", "CANCELLED"])
def test_a_command_cannot_be_cancelled_once_it_is_released(world, status):
    eid = drive(world, status)
    with pytest.raises(InvalidAction, match="before it is released"):
        world.run("alice", "Cancel Command", execution_id=eid, reason="too late")


def test_cancelling_needs_a_reason(world):
    eid = propose(world).result["execution_id"]
    with pytest.raises(InvalidAction):
        world.run("alice", "Cancel Command", execution_id=eid, reason="  ")


# ------------------------------------------------------------------------------------------------ transitions

# for each status, the actions the lifecycle allows (all others must be refused): written by hand from the state diagram
LEGAL = {
    "PROPOSED": {"approve", "cancel"}, "APPROVED": {"release", "cancel"}, "RELEASED": {"sent"},
    "SENT": {"ACCEPTED", "REJECTED_ONBOARD", "FAILED"}, "ACCEPTED": {"VERIFIED", "FAILED"},
    "REJECTED_ONBOARD": set(), "VERIFIED": set(), "FAILED": set(), "CANCELLED": set(),
}


@pytest.mark.parametrize("status", ALL_STATUSES)
def test_every_transition_the_lifecycle_does_not_allow_is_refused(world, status):
    eid = drive(world, status)
    attempts = {
        "approve": lambda: world.run("bob", "Approve Command", execution_id=eid),
        "release": lambda: release_with_override(world, eid),
        "cancel": lambda: world.run("alice", "Cancel Command", execution_id=eid, reason="r"),
        "sent": lambda: world.run("automation", "Record Command Sent", execution_id=eid),
        **{o: (lambda o=o: outcome(world, eid, o, reason="r"))
           for o in ("ACCEPTED", "REJECTED_ONBOARD", "VERIFIED", "FAILED")},
    }
    for name, attempt in attempts.items():
        if name in LEGAL[status]:
            continue                                                         # the legal ones are exercised elsewhere
        with pytest.raises(InvalidAction):
            attempt()
    assert world.execution(eid)["status"] == status


def test_rejection_and_failure_need_a_reason(world):
    eid = drive(world, "SENT")
    for kind in ("REJECTED_ONBOARD", "FAILED"):
        with pytest.raises(InvalidAction, match="needs a reason"):
            outcome(world, eid, kind)


def test_the_baseline_is_the_telemetry_at_the_moment_of_sending(world):
    world.set_state(mode=1, battery_soc_pct=77.0, heater=0, cmd_accepted=3)
    eid = propose(world).result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    release_with_override(world, eid)
    world.set_state(cmd_accepted=4)                                          # telemetry moves on before it is sent
    send(world, eid)
    world.set_state(cmd_accepted=5)                                          # ... and after
    row = world.execution(eid)
    assert row["send_baseline"]["cmd_accepted"] == 4 and row["sent_at"] == world.clock.now
    assert world.row("SELECT processed_at FROM ops.outbox")["processed_at"] is not None


# ------------------------------------------------------------------------------------------------ scripted walks (simulator)

class Walk:
    """A satellite simulated in-process, and the steps the outbox worker and the automations will do, done by hand."""

    def __init__(self, world, spec, soc=0.9):
        self.world, self.spec = world, spec
        self.packets = []
        self.sim = Simulator(spec, Spacecraft(soc=soc), self.packets.append, epoch_ms=1_792_800_000_000)
        self.telemetry()

    def telemetry(self, seconds=1.0):
        self.packets.clear()
        self.sim.advance(seconds)
        hk = [decode_tm(self.spec, p) for p in self.packets if decode_tm(self.spec, p).packet == "Housekeeping"][-1]
        self.world.set_state(**hk.values)
        return hk.values

    def deliver(self, eid):
        """Release has queued the bytes: mark them sent, give them to the satellite, then read telemetry again."""
        send(self.world, eid)
        accepted = self.sim.handle_telecommand(bytes.fromhex(self.world.execution(eid)["raw_bytes_hex"]))
        return accepted, self.telemetry()


def test_scripted_walk_set_mode_payload_ends_verified(world, spec):
    walk = Walk(world, spec)
    eid = propose(world, "SetMode", {"mode": "PAYLOAD"}, reason="payload pass").result["execution_id"]
    world.run("bob", "Approve Command", execution_id=eid)
    release_with_override(world, eid)
    accepted, current = walk.deliver(eid)
    row = world.execution(eid)
    assert accepted and row["status"] == "SENT"
    assert command_signal(spec, "SetMode", row["send_baseline"], current) == "ACCEPTED"
    outcome(world, eid, "ACCEPTED")
    assert effects_met(row["expected_effect"], row["send_baseline"], current)
    outcome(world, eid, "VERIFIED")
    done = world.execution(eid)
    assert done["status"] == "VERIFIED" and done["verified_at"] is not None
    assert walk.sim.model.mode == 2 and current["mode"] == 2
    statuses = [a["after"][f"command_execution:{eid}"]["status"] for a in world.audit(outcome="OK")
                if f"command_execution:{eid}" in (a["after"] or {})]
    assert statuses == ["PROPOSED", "APPROVED", "RELEASED", "SENT", "ACCEPTED", "VERIFIED"]


def test_scripted_walk_the_satellite_refuses_and_the_counters_show_it(world, spec):
    walk = Walk(world, spec, soc=0.25)                                       # 25 %: PAYLOAD will be refused
    proposal = propose(world, "SetMode", {"mode": "PAYLOAD"})
    assert proposal.result["preflight"]["accepted"] is False                 # predicted before sending
    eid = proposal.result["execution_id"]
    world.run("sam", "Approve Command", execution_id=eid, note="testing the on-board refusal")
    release_with_override(world, eid)
    accepted, current = walk.deliver(eid)
    row = world.execution(eid)
    assert not accepted and walk.sim.model.cmd_rejected == 1
    assert command_signal(spec, "SetMode", row["send_baseline"], current) == "REJECTED"
    outcome(world, eid, "REJECTED_ONBOARD", reason="rejected on board: counter rose")
    assert world.execution(eid)["status"] == "REJECTED_ONBOARD"
    assert current["mode"] == 1                                              # nothing changed


def test_scripted_walk_a_reboot_is_recognised_by_the_uptime_not_the_counters(world, spec):
    walk = Walk(world, spec)
    walk.telemetry(30.0)
    eid = propose(world, "Reboot", who="sam", reason="clear a fault").result["execution_id"]
    world.run("tina", "Approve Command", execution_id=eid)
    release_with_override(world, eid, who="tina")
    accepted, current = walk.deliver(eid)
    row = world.execution(eid)
    assert accepted and current["uptime_s"] < row["send_baseline"]["uptime_s"] and current["cmd_accepted"] == 0
    assert command_signal(spec, "Reboot", row["send_baseline"], current) == "ACCEPTED"
    assert effects_met(row["expected_effect"], row["send_baseline"], current) and current["mode"] == 0
