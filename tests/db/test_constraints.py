"""Rules of the ontology that the database enforces by itself, so that a bug in the action runner cannot break them.

Every test runs as the runner role (or ingest, where noted) in a transaction that is rolled back. The reference
data (operators alice/sam/vera/helper/automation, spacecraft MINISAT-1, station HEL) comes from tests/dbfixtures.py.
"""
from datetime import datetime, timedelta, timezone

import pytest

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("alembic")

from psycopg import errors  # noqa: E402
from psycopg.types.json import Jsonb  # noqa: E402

T0 = datetime(2026, 10, 31, 12, 0, tzinfo=timezone.utc)


def later(minutes=1):
    """A time safely after "now" in the database (its now() is the start of the transaction, which is a moment ago)."""
    return datetime.now(timezone.utc) + timedelta(minutes=minutes)


def insert(conn, table, returning=None, **values):
    columns = ", ".join(values)
    marks = ", ".join(["%s"] * len(values))
    sql = f"INSERT INTO ops.{table} ({columns}) VALUES ({marks})" + (f" RETURNING {returning}" if returning else "")
    cur = conn.execute(sql, [Jsonb(v) if isinstance(v, dict) else v for v in values.values()])
    return cur.fetchone()[0] if returning else None


def violates(conn, error, table, returning=None, **values):
    """The insert must fail with ``error``; a savepoint keeps the surrounding transaction usable."""
    with pytest.raises(error):
        with conn.transaction():
            insert(conn, table, returning, **values)


def proposal(**over):
    base = dict(spacecraft_id="MINISAT-1", command_id=2, command_name="SetMode", vital=False,
                arguments={"mode": 2}, reason="payload pass", proposed_by="alice",
                expires_at=later(15))
    base.update(over)
    return base


def approved(**over):
    return proposal(**{"status": "APPROVED", "approved_by": "sam", "approved_at": T0, **over})


# --------------------------------------------------------------------------------------------- commands

def test_a_new_proposal_starts_as_proposed(run):
    eid = insert(run, "command_execution", "execution_id", **proposal())
    assert run.execute("SELECT status, approved_by FROM ops.command_execution WHERE execution_id = %s", (eid,)
                       ).fetchone() == ("PROPOSED", None)


def test_two_person_rule_a_vital_command_is_not_approved_by_its_proposer(run):
    violates(run, errors.CheckViolation, "command_execution",
             **approved(command_id=4, command_name="Reboot", vital=True, proposed_by="sam", approved_by="sam"))
    insert(run, "command_execution", **approved(command_id=4, command_name="Reboot", vital=True,
                                                proposed_by="alice", approved_by="sam"))


def test_the_database_enforces_the_rule_only_for_vital_commands(run):
    insert(run, "command_execution", **approved(proposed_by="alice", approved_by="alice"))      # not vital: allowed


def test_an_agent_or_a_system_account_can_never_be_the_approver(run):
    for who in ("helper", "automation"):
        violates(run, errors.ForeignKeyViolation, "command_execution", **approved(approved_by=who))
    insert(run, "command_execution", **approved(approved_by="alice"))


def test_an_agent_may_be_the_proposer(run):
    insert(run, "command_execution", **proposal(proposed_by="helper"))


def test_a_command_cannot_go_beyond_proposed_without_an_approver(run):
    for status in ("APPROVED", "RELEASED", "SENT", "ACCEPTED", "VERIFIED", "FAILED"):
        violates(run, errors.CheckViolation, "command_execution", **proposal(status=status))
    insert(run, "command_execution", **proposal(status="CANCELLED"))


def test_approver_and_approval_time_go_together(run):
    violates(run, errors.CheckViolation, "command_execution", **proposal(approved_by="sam"))
    violates(run, errors.CheckViolation, "command_execution", **proposal(approved_at=T0))


@pytest.mark.parametrize("bad", [
    {"status": "DONE"}, {"command_id": 0}, {"command_id": 65536}, {"reason": "  "}, {"arguments": {}, "vital": None},
    {"raw_bytes_hex": "10 0a"}, {"raw_bytes_hex": "10A"}, {"raw_bytes_hex": "10AA"},
    {"status": "REJECTED_ONBOARD", "approved_by": "sam", "approved_at": T0},                 # needs a reason
])
def test_invalid_command_values_are_refused(run, bad):
    violates(run, (errors.CheckViolation, errors.NotNullViolation), "command_execution", **proposal(**bad))


def test_a_proposal_must_expire_after_it_was_made(run):
    violates(run, errors.CheckViolation, "command_execution",
             **proposal(proposed_at=T0, expires_at=T0))


def test_unknown_spacecraft_or_operator_is_refused(run):
    violates(run, errors.ForeignKeyViolation, "command_execution", **proposal(spacecraft_id="NOPE"))
    violates(run, errors.ForeignKeyViolation, "command_execution", **proposal(proposed_by="nobody"))


def test_valid_raw_bytes_and_rejection_reason_are_accepted(run):
    insert(run, "command_execution", **approved(status="SENT", raw_bytes_hex="100ac00000020002" + "02"))
    insert(run, "command_execution", **approved(
        status="REJECTED_ONBOARD", rejection_reason="battery too low for PAYLOAD mode (25 % < 30 %)"))


# --------------------------------------------------------------------------------------------- alarms

def alarm(**over):
    base = dict(spacecraft_id="MINISAT-1", parameter_name="battery_soc_pct", severity="WARNING", trigger_value=34.0,
                limit_violated="minInclusive 35")
    base.update(over)
    return base


def test_only_one_open_alarm_per_parameter(run):
    insert(run, "alarm", **alarm())
    violates(run, errors.UniqueViolation, "alarm", **alarm(severity="CRITICAL"))
    insert(run, "alarm", **alarm(parameter_name="battery_voltage"))                  # another parameter is fine


def test_a_cleared_alarm_lets_a_new_episode_start(run):
    insert(run, "alarm", **alarm(state="CLEARED", cleared_at=later()))
    insert(run, "alarm", **alarm())


def test_only_a_person_acknowledges_an_alarm(run):
    for who in ("helper", "automation"):
        violates(run, errors.ForeignKeyViolation, "alarm",
                 **alarm(state="ACKNOWLEDGED", acknowledged_by=who, acknowledged_at=T0))
    insert(run, "alarm", **alarm(state="ACKNOWLEDGED", acknowledged_by="alice", acknowledged_at=T0))


@pytest.mark.parametrize("bad", [
    {"state": "ACKNOWLEDGED"},                                                    # nobody acknowledged it
    {"state": "ACTIVE", "acknowledged_by": "alice", "acknowledged_at": T0},       # active yet acknowledged
    {"acknowledged_by": "alice"},                                                 # acknowledger without a time
    {"state": "CLEARED"},                                                         # cleared without a time
    {"cleared_at": T0},                                                           # a time without being cleared
    {"severity": "FATAL"}, {"state": "GONE"},
])
def test_inconsistent_alarm_states_are_refused(run, bad):
    violates(run, errors.CheckViolation, "alarm", **alarm(**bad))


# --------------------------------------------------------------------------------------------- anomalies

def anomaly(**over):
    base = dict(spacecraft_id="MINISAT-1", title="Unplanned SAFE mode", severity="HIGH", opened_by="alice")
    base.update(over)
    return base


def test_an_anomaly_cannot_be_resolved_without_a_root_cause(run):
    violates(run, errors.CheckViolation, "anomaly", **anomaly(status="RESOLVED", resolved_at=later()))
    violates(run, errors.CheckViolation, "anomaly",
             **anomaly(status="RESOLVED", resolved_at=later(), root_cause="   "))
    insert(run, "anomaly", **anomaly(
        status="RESOLVED", resolved_at=later(), root_cause="payload left on across two eclipses"))


def test_resolved_and_resolution_time_go_together(run):
    violates(run, errors.CheckViolation, "anomaly", **anomaly(resolved_at=later()))
    violates(run, errors.CheckViolation, "anomaly", **anomaly(title=" "))
    violates(run, errors.CheckViolation, "anomaly", **anomaly(severity="MEH"))


def test_alarms_and_commands_link_to_an_anomaly(run):
    aid = insert(run, "anomaly", "anomaly_id", **anomaly())
    insert(run, "alarm", **alarm(anomaly_id=aid))
    eid = insert(run, "command_execution", "execution_id", **approved(status="SENT"))
    insert(run, "anomaly_command_execution", anomaly_id=aid, execution_id=eid)
    violates(run, errors.UniqueViolation, "anomaly_command_execution", anomaly_id=aid, execution_id=eid)


# --------------------------------------------------------------------------------------------- contacts

def contact(start_h, end_h, **over):
    base = dict(spacecraft_id="MINISAT-1", station_id="HEL", created_by="sam",
                start_at=T0 + timedelta(hours=start_h), end_at=T0 + timedelta(hours=end_h))
    base.update(over)
    return base


def test_one_station_cannot_serve_two_overlapping_contacts(run):
    insert(run, "contact_window", **contact(0, 1))
    violates(run, errors.ExclusionViolation, "contact_window", **contact(0.5, 1.5))
    insert(run, "contact_window", **contact(1, 2))                                   # back to back is fine


def test_a_missed_contact_frees_its_slot(run):
    insert(run, "contact_window", **contact(0, 1, status="MISSED"))
    insert(run, "contact_window", **contact(0, 1))


def test_contact_values_are_checked(run):
    violates(run, errors.CheckViolation, "contact_window", **contact(2, 1))
    violates(run, errors.CheckViolation, "contact_window", **contact(0, 1, max_elevation_deg=95))
    violates(run, errors.CheckViolation, "contact_window", **contact(0, 1, packets_lost=-1))


# --------------------------------------------------------------------------------------------- telemetry & spacecraft

def test_a_sample_is_unique_per_spacecraft_parameter_and_time(db):
    sample = dict(spacecraft_id="MINISAT-1", parameter_name="mode", sc_time_ms=5, value=1.0)
    with db.session("ingest") as conn:
        insert(conn, "telemetry_samples", **sample)
        violates(conn, errors.UniqueViolation, "telemetry_samples", **sample)
        insert(conn, "telemetry_samples", **{**sample, "parameter_name": "heater"})
        insert(conn, "telemetry_samples", **{**sample, "sc_time_ms": 6})


def test_invalid_samples_are_refused(db):
    sample = dict(spacecraft_id="MINISAT-1", parameter_name="mode", sc_time_ms=5, value=1.0)
    with db.session("ingest") as conn:
        violates(conn, errors.CheckViolation, "telemetry_samples", **{**sample, "sc_time_ms": -1})
        violates(conn, errors.CheckViolation, "telemetry_samples", **{**sample, "packet_seq_count": 16384})
        insert(conn, "telemetry_samples", **{**sample, "packet_seq_count": 16383})
        violates(conn, errors.ForeignKeyViolation, "telemetry_samples", **{**sample, "spacecraft_id": "NOPE"})


def test_spacecraft_values_are_validated(db):
    with db.session("ingest") as conn:
        with pytest.raises(errors.CheckViolation):
            with conn.transaction():
                conn.execute("UPDATE ops.spacecraft SET latest_values = '[1, 2]'")
    with db.session("runner") as conn:
        with pytest.raises(errors.CheckViolation):
            with conn.transaction():
                conn.execute("UPDATE ops.spacecraft SET health_status = 'GREAT'")


def test_operator_kind_and_role_must_match(db):
    with db.session("migrator") as conn:
        for kind, role in (("AGENT", "OPERATOR"), ("HUMAN", "AGENT"), ("SYSTEM", "SUPERVISOR"), ("HUMAN", "SYSTEM")):
            violates(conn, errors.CheckViolation, "operator", operator_id="x", display_name="X", kind=kind, role=role)
        insert(conn, "operator", operator_id="x", display_name="X", kind="HUMAN", role="VIEWER")


# --------------------------------------------------------------------------------------------- audit log

def test_audit_rows_are_validated_and_idempotency_keys_are_unique_for_successes(run):
    row = dict(operator_id="alice", operator_kind="HUMAN", action="Propose Command", outcome="OK",
               idempotency_key="k-1")
    insert(run, "audit_log", **row)
    violates(run, errors.UniqueViolation, "audit_log", **row)                          # a retry with the same key
    insert(run, "audit_log", **{**row, "outcome": "DENIED"})                           # refusals may repeat
    insert(run, "audit_log", **{**row, "idempotency_key": "k-2"})
    violates(run, errors.CheckViolation, "audit_log", **{**row, "outcome": "MAYBE", "idempotency_key": None})


def test_a_refused_attempt_by_an_unknown_caller_is_still_recorded(run):
    insert(run, "audit_log", action="Approve Command", outcome="DENIED", parameters={"reason": "no such operator"})


def test_the_outbox_accepts_work_and_marks_it_done(run):
    oid = insert(run, "outbox", "outbox_id", topic="send_telecommand", payload={"execution": "x"})
    run.execute("UPDATE ops.outbox SET processed_at = now(), attempts = attempts + 1 WHERE outbox_id = %s", (oid,))
    violates(run, errors.CheckViolation, "outbox", topic="t", payload={}, attempts=-1)
