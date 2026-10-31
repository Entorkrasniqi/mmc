"""``minisat db-seed | act | actions | status`` against a real database (and their error handling)."""
import json

import pytest

pytest.importorskip("psycopg")
pytest.importorskip("pydantic")

from conftest import SPEC_PATH  # noqa: E402
from dbfixtures import PASSWORDS  # noqa: E402
from minisat.cli import main  # noqa: E402


@pytest.fixture()
def cli(database_factory, monkeypatch, tmp_path):
    """A migrated, EMPTY database (no reference data) and the environment the commands read their settings from."""
    database = database_factory()
    from psycopg.conninfo import conninfo_to_dict
    d = conninfo_to_dict(database.conninfo("migrator"))
    monkeypatch.chdir(tmp_path)                                     # no .env here unless a test writes one
    monkeypatch.setenv("MINISAT_DB_HOST", d["host"])
    monkeypatch.setenv("MINISAT_DB_PORT", str(d.get("port", 5432)))
    monkeypatch.setenv("MINISAT_DB_NAME", d["dbname"])
    for role, password in PASSWORDS.items():
        monkeypatch.setenv(f"MINISAT_DB_PASSWORD_{role.upper()}", password)
    return database


def run(capsys, *argv):
    code = main(["--spec", str(SPEC_PATH), *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def test_db_seed_creates_what_is_missing_and_is_harmless_to_repeat(cli, capsys):
    code, out, _ = run(capsys, "db-seed", "--demo", "--operator", "zoe:Zoe:OPERATOR")
    assert code == 0 and "1 spacecraft" in out and "8 operators" in out and "1 stations" in out
    code, out, _ = run(capsys, "db-seed", "--demo", "--operator", "zoe:Zoe:OPERATOR")
    assert code == 0 and "0 spacecraft, 0 operators, 0 stations" in out
    with cli.session("admin") as conn:
        rows = dict(conn.execute("SELECT operator_id, kind || '/' || role FROM ops.operator").fetchall())
    assert rows["automation"] == "SYSTEM/SYSTEM" and rows["helper"] == "AGENT/AGENT" and rows["zoe"] == "HUMAN/OPERATOR"
    assert rows["sam"] == "HUMAN/SUPERVISOR"


@pytest.mark.parametrize("bad", ["alice", "alice:Alice", "alice:Alice:BOSS", ":Alice:OPERATOR"])
def test_db_seed_rejects_a_malformed_operator(cli, capsys, bad):
    code, _, err = run(capsys, "db-seed", "--operator", bad)
    assert code == 2 and ("id:Display Name:ROLE" in err or "role must be" in err)


def test_act_runs_an_action_and_prints_the_result_as_json(cli, capsys):
    run(capsys, "db-seed", "--demo")
    code, out, _ = run(capsys, "act", "alice", "Propose Command",
                       json.dumps({"spacecraft_id": "MINISAT-1", "command": "SetMode", "arguments": {"mode": "PAYLOAD"},
                                   "reason": "payload pass"}))
    assert code == 0
    answer = json.loads(out)
    assert answer["action"] == "Propose Command" and answer["result"]["status"] == "PROPOSED"
    assert answer["result"]["raw_bytes_hex"] == "100ac0000002000202" and answer["audit_id"] >= 1
    assert any("no telemetry" in w for w in answer["warnings"])


def test_act_reports_refusals_with_the_audit_number_and_exit_code_2(cli, capsys):
    run(capsys, "db-seed", "--demo")
    code, _, err = run(capsys, "act", "vera", "Approve Command", '{"execution_id": "5b1ac9f1-0000-4000-8000-000000000000"}')
    assert code == 2 and err.startswith("DENIED:") and "(audit #" in err
    code, _, err = run(capsys, "act", "alice", "Approve Command", '{"execution_id": "5b1ac9f1-0000-4000-8000-000000000000"}')
    assert code == 2 and err.startswith("INVALID:") and "no such command execution" in err
    code, _, err = run(capsys, "act", "mallory", "Approve Command", "{}")
    assert code == 2 and "unknown operator" in err


def test_act_needs_valid_json_that_is_an_object(cli, capsys):
    assert run(capsys, "act", "alice", "Propose Command", "{not json")[0] == 2
    assert run(capsys, "act", "alice", "Propose Command", "[1, 2]")[0] == 2


def test_release_through_the_cli_can_skip_the_contact_check_for_the_simulator(cli, capsys):
    run(capsys, "db-seed", "--demo")
    _, out, _ = run(capsys, "act", "alice", "Propose Command",
                    json.dumps({"spacecraft_id": "MINISAT-1", "command": "Noop", "reason": "link test"}))
    eid = json.loads(out)["result"]["execution_id"]
    run(capsys, "act", "bob", "Approve Command", json.dumps({"execution_id": eid}))
    code, _, err = run(capsys, "act", "bob", "Release Command", json.dumps({"execution_id": eid}))
    assert code == 2 and "no contact window" in err
    code, out, _ = run(capsys, "act", "bob", "Release Command", json.dumps({"execution_id": eid}), "--no-contact-check")
    assert code == 0 and json.loads(out)["result"]["status"] == "RELEASED"


def test_actions_lists_every_action_with_its_roles_and_parameters(capsys):
    code, out, _ = run(capsys, "actions")
    assert code == 0
    for name in ("Propose Command", "Approve Command", "Release Command", "Raise Alarm", "Plan Contact"):
        assert name in out
    assert "[OPERATOR, SUPERVISOR]" in out and "(agent may call it)" in out and "execution_id: string" in out


def test_status_shows_the_spacecraft_alarms_commands_and_events(cli, capsys):
    run(capsys, "db-seed", "--demo")
    run(capsys, "act", "alice", "Propose Command",
        json.dumps({"spacecraft_id": "MINISAT-1", "command": "Noop", "reason": "link test"}))
    code, out, _ = run(capsys, "status")
    assert code == 0 and out.startswith("MINISAT-1") and "health: NOMINAL" in out and "last contact: never" in out
    assert "open alarms: none" in out and "Noop" in out and "PROPOSED" in out and "by alice" in out


def test_status_of_an_unknown_spacecraft_says_what_to_do(cli, capsys):
    code, _, err = run(capsys, "status", "--spacecraft", "NOPE")
    assert code == 2 and "db-seed" in err


def test_a_missing_password_is_a_message_not_a_traceback(cli, capsys, monkeypatch):
    monkeypatch.delenv("MINISAT_DB_PASSWORD_READER")
    code, _, err = run(capsys, "status")
    assert code == 2 and "configuration error" in err and "MINISAT_DB_PASSWORD_READER" in err


def test_an_unreachable_database_is_a_message_not_a_traceback(cli, capsys, monkeypatch):
    monkeypatch.setenv("MINISAT_DB_PORT", "1")
    code, _, err = run(capsys, "status")
    assert code == 1 and "cannot reach the database" in err


def test_settings_are_read_from_a_dot_env_file_but_the_environment_wins(cli, capsys, monkeypatch, tmp_path):
    monkeypatch.delenv("MINISAT_DB_PASSWORD_READER")
    (tmp_path / ".env").write_text(f"# comment\nMINISAT_DB_PASSWORD_READER={PASSWORDS['reader']}\n"
                                   f"MINISAT_DB_NAME=ignored-because-the-environment-wins\n", encoding="utf-8")
    run(capsys, "db-seed", "--demo")
    code, out, _ = run(capsys, "status")
    assert code == 0 and out.startswith("MINISAT-1")
    import os
    assert os.environ["MINISAT_DB_NAME"] != "ignored-because-the-environment-wins"
