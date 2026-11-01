"""The action runner's own guarantees (protocols/action-runner-and-audit.md): who may run what, that every attempt leaves
exactly one audit row, that a failed action leaves no trace except that row, and that retries are harmless.
"""
import threading
import uuid

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic")

from pydantic import BaseModel  # noqa: E402

from minisat.ontology.actions import default_registry  # noqa: E402
from minisat.ontology.runner import (Action, ActionFailed, ActionRegistry, ActionRunner, InvalidAction,  # noqa: E402
                                     PermissionDenied)

OPERATORS = {"VIEWER": "vera", "OPERATOR": "alice", "SUPERVISOR": "sam", "AGENT": "helper", "SYSTEM": "automation"}
ALL_ROLES = set(OPERATORS)

# the roles allowed to run each action AT ALL (written out by hand from ontology.md sections 3 and 7)
ROLE_MATRIX = {
    "Propose Command": {"OPERATOR", "SUPERVISOR", "AGENT", "SYSTEM"},
    "Approve Command": {"OPERATOR", "SUPERVISOR"},
    "Release Command": {"OPERATOR", "SUPERVISOR"},
    "Cancel Command": {"OPERATOR", "SUPERVISOR", "AGENT", "SYSTEM"},
    "Record Command Sent": {"SYSTEM"},
    "Record Command Outcome": {"SYSTEM"},
    "Acknowledge Alarm": {"OPERATOR", "SUPERVISOR"},
    "Raise Alarm": {"SYSTEM"},
    "Update Alarm": {"SYSTEM"},
    "Clear Alarm": {"SYSTEM"},
    "Open Anomaly": {"OPERATOR", "SUPERVISOR", "AGENT", "SYSTEM"},
    "Update Anomaly": {"OPERATOR", "SUPERVISOR"},
    "Record Spacecraft Event": {"SYSTEM"},
    "Set Health Status": {"SYSTEM"},
    "Plan Contact": {"SUPERVISOR", "SYSTEM"},
}
AGENT_CALLABLE = {"Propose Command", "Cancel Command", "Open Anomaly"}


def test_the_matrix_covers_every_registered_action():
    assert {a.name for a in default_registry()} == set(ROLE_MATRIX), "an action was added: decide who may run it"


def test_registry_flags_and_schemas():
    for action in default_registry():
        assert action.json_schema()["type"] == "object"
        assert action.agent_callable == (action.name in AGENT_CALLABLE), action.name
        assert not (action.agent_callable and action.roles == {"SYSTEM"})
        assert "VIEWER" not in action.roles, "a viewer must never be able to change anything"


def test_registering_the_same_action_twice_is_a_mistake():
    registry = default_registry()
    with pytest.raises(ValueError, match="twice"):
        registry.add(next(iter(registry)))


@pytest.mark.parametrize("action", sorted(ROLE_MATRIX))
def test_exact_role_matrix(world, action):
    """Empty parameters: a role that is not allowed is DENIED first; an allowed role gets as far as validation."""
    for role, operator in OPERATORS.items():
        if role in ROLE_MATRIX[action]:
            with pytest.raises(InvalidAction):
                world.run(operator, action)
        else:
            with pytest.raises(PermissionDenied, match="may not run"):
                world.run(operator, action)


# ------------------------------------------------------------------------------------------------ audit

def test_an_unknown_operator_is_refused_and_the_attempt_is_recorded(world):
    with pytest.raises(PermissionDenied, match="unknown operator") as info:
        world.run("mallory", "Propose Command")
    (row,) = world.audit(operator_id="mallory")
    assert (row["outcome"], row["operator_kind"], row["audit_id"]) == ("DENIED", None, info.value.audit_id)


def test_an_unknown_action_is_refused_and_recorded(world):
    with pytest.raises(InvalidAction, match="unknown action"):
        world.run("alice", "Launch Missiles")
    assert world.audit(action="Launch Missiles")[0]["outcome"] == "INVALID"


def test_every_attempt_leaves_exactly_one_audit_row_with_the_right_outcome(world):
    def attempt(operator, action, **params):
        try:
            world.run(operator, action, **params)
        except (PermissionDenied, InvalidAction):
            pass

    before = len(world.audit())
    attempt("vera", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")          # denied
    attempt("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Explode", reason="x")      # invalid
    attempt("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="link test")  # ok
    rows = world.audit()[before:]
    assert [r["outcome"] for r in rows] == ["DENIED", "INVALID", "OK"]
    assert [r["operator_id"] for r in rows] == ["vera", "alice", "alice"]
    assert [r["operator_kind"] for r in rows] == ["HUMAN", "HUMAN", "HUMAN"]


def test_the_audit_row_of_a_success_holds_parameters_before_after_and_result(world):
    result = world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="SetHeater",
                       arguments={"state": "ON"}, reason="warm the battery")
    (row,) = world.audit(audit_id=result.audit_id)
    eid = result.result["execution_id"]
    assert row["outcome"] == "OK" and row["action"] == "Propose Command"
    assert row["parameters"]["command"] == "SetHeater" and row["parameters"]["reason"] == "warm the battery"
    assert row["before"] == {}
    assert row["after"][f"command_execution:{eid}"]["status"] == "PROPOSED"
    assert row["after"]["_result"]["execution_id"] == eid

    approve = world.run("bob", "Approve Command", execution_id=eid)
    (row,) = world.audit(audit_id=approve.audit_id)
    assert row["before"][f"command_execution:{eid}"]["status"] == "PROPOSED"
    assert row["after"][f"command_execution:{eid}"]["status"] == "APPROVED"
    assert row["after"][f"command_execution:{eid}"]["approved_by"] == "bob"


def test_validation_errors_are_reported_per_field_and_audited(world):
    with pytest.raises(InvalidAction, match="spacecraft_id"):
        world.run("alice", "Propose Command", command="Noop", reason="x")                      # missing field
    with pytest.raises(InvalidAction, match="surprise"):
        world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x", surprise=1)
    with pytest.raises(InvalidAction, match="execution_id"):
        world.run("alice", "Approve Command", execution_id="not-a-uuid")
    assert [r["outcome"] for r in world.audit(action="Propose Command")] == ["INVALID", "INVALID"]
    assert world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 0


def test_the_correlation_id_ties_audit_rows_and_outbox_messages_together(world):
    world.contact_window()
    cid = uuid.uuid4()
    proposed = world.run("alice", "Propose Command", correlation_id=cid, spacecraft_id="MINISAT-1", command="Noop",
                         reason="link test")
    eid = proposed.result["execution_id"]
    world.run("bob", "Approve Command", correlation_id=cid, execution_id=eid)
    world.run("bob", "Release Command", correlation_id=cid, execution_id=eid)
    assert {r["correlation_id"] for r in world.audit()} >= {cid}
    assert len(world.audit(correlation_id=cid)) == 3
    assert world.row("SELECT correlation_id FROM ops.outbox")["correlation_id"] == cid


# ------------------------------------------------------------------------------------------------ atomicity

def test_a_failing_handler_leaves_no_partial_changes(world):
    """OpenAnomaly inserts the anomaly first and only then notices the second alarm id is unknown."""
    with pytest.raises(InvalidAction, match="no such alarm"):
        world.run("alice", "Open Anomaly", spacecraft_id="MINISAT-1", title="Strange", severity="LOW",
                  alarm_ids=[str(uuid.uuid4())])
    assert world.row("SELECT count(*) AS n FROM ops.anomaly")["n"] == 0
    assert world.audit(action="Open Anomaly")[0]["outcome"] == "INVALID"


def test_if_the_audit_row_cannot_be_written_the_change_is_rolled_back(world, monkeypatch):
    original = ActionRunner._audit

    def audit(conn, operator, operator_id, action, outcome, *rest):
        if outcome == "OK":
            raise RuntimeError("audit table unavailable")
        return original(conn, operator, operator_id, action, outcome, *rest)

    monkeypatch.setattr(ActionRunner, "_audit", staticmethod(audit))
    with pytest.raises(RuntimeError, match="audit table unavailable"):
        world.run("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="link test")
    assert world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 0
    assert [r["outcome"] for r in world.audit()] == ["ERROR"]


def test_a_change_the_database_refuses_becomes_an_audited_error(world):
    class Params(BaseModel):
        pass

    def reckless(ctx, p):                         # a buggy handler: writes a status the database does not allow
        ctx.insert("alarm", spacecraft_id="MINISAT-1", parameter_name="mode", severity="FATAL", trigger_value=1,
                   limit_violated="x")

    registry = ActionRegistry([Action("Reckless", Params, frozenset({"OPERATOR"}), reckless)])
    runner = ActionRunner(world.db.connect_factory("runner"), world.spec, registry, clock=world.clock)
    with pytest.raises(ActionFailed, match="database refused"):
        runner.run("alice", "Reckless", {})
    assert world.audit(action="Reckless")[0]["outcome"] == "ERROR"
    assert world.row("SELECT count(*) AS n FROM ops.alarm")["n"] == 0


# ------------------------------------------------------------------------------------------------ idempotency

PROPOSAL = dict(spacecraft_id="MINISAT-1", command="Noop", reason="link test")


def test_a_retry_with_the_same_key_returns_the_first_result_and_changes_nothing(world):
    first = world.run("alice", "Propose Command", idempotency_key="req-1", **PROPOSAL)
    second = world.run("alice", "Propose Command", idempotency_key="req-1", **PROPOSAL)
    assert (first.replayed, second.replayed) == (False, True)
    assert second.audit_id == first.audit_id and second.result == first.result
    assert world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 1
    assert len(world.audit(action="Propose Command")) == 1


def test_the_same_key_with_different_parameters_is_refused(world):
    world.run("alice", "Propose Command", idempotency_key="req-1", **PROPOSAL)
    with pytest.raises(InvalidAction, match="different parameters"):
        world.run("alice", "Propose Command", idempotency_key="req-1", **{**PROPOSAL, "reason": "another reason"})


def test_a_key_belongs_to_one_action(world):
    world.run("alice", "Propose Command", idempotency_key="k", **PROPOSAL)
    other = world.run("alice", "Open Anomaly", idempotency_key="k", spacecraft_id="MINISAT-1", title="t", severity="LOW")
    assert not other.replayed


def test_a_failed_attempt_does_not_use_up_the_key(world):
    with pytest.raises(InvalidAction):
        world.run("alice", "Propose Command", idempotency_key="req-9", **{**PROPOSAL, "command": "Explode"})
    ok = world.run("alice", "Propose Command", idempotency_key="req-9", **PROPOSAL)
    assert not ok.replayed


def test_two_identical_requests_at_the_same_moment_create_one_command(world):
    results, errors = [], []
    barrier = threading.Barrier(2)

    def worker():
        try:
            barrier.wait()
            results.append(world.run("alice", "Propose Command", idempotency_key="race", **PROPOSAL))
        except Exception as exc:                                     # noqa: BLE001 - reported below
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errors, errors
    assert len({r.result["execution_id"] for r in results}) == 1
    assert world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 1
    assert len(world.audit(action="Propose Command", outcome="OK")) == 1
