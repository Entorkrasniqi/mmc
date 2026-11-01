"""Who may do what in the database (protocols/action-runner-and-audit.md).

Two kinds of check: an EXACT privilege matrix read from the catalog (so a new table, or a grant nobody decided
on, fails the test), and behaviour, by connecting as each real role and trying things it must not be able to do.
"""
import pytest

psycopg = pytest.importorskip("psycopg")
pytest.importorskip("alembic")

from psycopg import errors  # noqa: E402

TABLES = ["operator", "spacecraft", "ground_station", "contact_window", "anomaly", "alarm", "command_execution",
          "anomaly_command_execution", "spacecraft_event", "telemetry_samples", "audit_log", "outbox"]
PRIVILEGES = ["SELECT", "INSERT", "DELETE", "TRUNCATE", "REFERENCES", "TRIGGER"]     # UPDATE is checked per column
EVERYTHING = "ALL COLUMNS"

READER_TABLES = {t: {"SELECT"} for t in TABLES}
RUNNER_TABLES = {t: {"SELECT"} for t in TABLES}
RUNNER_TABLES.update({
    "contact_window": {"SELECT", "INSERT"}, "anomaly": {"SELECT", "INSERT"}, "alarm": {"SELECT", "INSERT"},
    "command_execution": {"SELECT", "INSERT"}, "outbox": {"SELECT", "INSERT"},
    "anomaly_command_execution": {"SELECT", "INSERT"}, "spacecraft_event": {"SELECT", "INSERT"},
    "audit_log": {"SELECT", "INSERT"},
})
INGEST_TABLES = {t: set() for t in TABLES}
INGEST_TABLES.update({"spacecraft": {"SELECT"}, "telemetry_samples": {"SELECT", "INSERT"}})

# role -> table privileges, and the columns each role may UPDATE (missing table = none)
MATRIX = {
    "app_reader": (READER_TABLES, {}),
    "app_runner": (RUNNER_TABLES, {
        "spacecraft": {"health_status"}, "contact_window": EVERYTHING, "anomaly": EVERYTHING, "alarm": EVERYTHING,
        "command_execution": EVERYTHING, "outbox": EVERYTHING, "spacecraft_event": {"anomaly_id"}}),
    "ingest": (INGEST_TABLES, {"spacecraft": {"latest_values", "last_contact_at"}}),
}


def denied(conn, sql, error=errors.InsufficientPrivilege):
    with pytest.raises(error):
        with conn.transaction():
            conn.execute(sql)


def test_the_matrix_covers_every_table(db):
    with db.session("admin") as conn:
        actual = {r[0] for r in conn.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'ops'")}
    assert actual == set(TABLES), "a table was added or removed: decide its grants and update this matrix"


@pytest.mark.parametrize("role", sorted(MATRIX))
def test_exact_table_and_column_privileges(db, role):
    table_privileges, update_columns = MATRIX[role]
    with db.session("admin") as conn:
        for table in TABLES:
            granted = {p for p in PRIVILEGES
                       if conn.execute("SELECT has_table_privilege(%s, %s, %s)", (role, f"ops.{table}", p)).fetchone()[0]}
            assert granted == table_privileges[table], f"{role} on ops.{table}"
            columns = [r[0] for r in conn.execute(
                "SELECT column_name FROM information_schema.columns WHERE table_schema = 'ops' AND table_name = %s",
                (table,))]
            can_update = {c for c in columns if conn.execute(
                "SELECT has_column_privilege(%s, %s, %s, 'UPDATE')", (role, f"ops.{table}", c)).fetchone()[0]}
            expected = update_columns.get(table, set())
            assert can_update == (set(columns) if expected == EVERYTHING else expected), f"{role} UPDATE on ops.{table}"


@pytest.mark.parametrize("role", ["app_runner", "app_reader", "ingest"])
def test_no_role_can_create_objects_or_connect_unless_listed(db, role):
    with db.session("admin") as conn:
        def has(sql, *args):
            return conn.execute(sql, args).fetchone()[0]
        assert has("SELECT has_schema_privilege(%s, 'ops', 'USAGE')", role)
        assert not has("SELECT has_schema_privilege(%s, 'ops', 'CREATE')", role)
        assert not has("SELECT has_schema_privilege(%s, 'public', 'CREATE')", role)
        assert not has("SELECT has_database_privilege(%s, current_database(), 'TEMP')", role)
        assert not has("SELECT has_database_privilege(%s, current_database(), 'CREATE')", role)


def test_a_role_that_is_not_one_of_the_four_cannot_connect(db):
    with db.session("admin") as conn:
        conn.autocommit = True
        conn.execute("DROP ROLE IF EXISTS stranger")
        conn.execute("CREATE ROLE stranger LOGIN PASSWORD 'x'")
        try:
            assert not conn.execute("SELECT has_database_privilege('stranger', current_database(), 'CONNECT')"
                                    ).fetchone()[0]
        finally:
            conn.execute("DROP ROLE stranger")


# ------------------------------------------------------------------------------------------ behaviour

@pytest.mark.parametrize("table", TABLES)
def test_reader_cannot_write_anything(db, table):
    with db.session("reader") as conn:
        conn.execute(f"SELECT count(*) FROM ops.{table}").fetchone()
        denied(conn, f"INSERT INTO ops.{table} DEFAULT VALUES")
        denied(conn, f"DELETE FROM ops.{table}")
        denied(conn, f"TRUNCATE ops.{table}")


@pytest.mark.parametrize("table", TABLES)
def test_runner_never_deletes_or_truncates(db, table):
    with db.session("runner") as conn:
        denied(conn, f"DELETE FROM ops.{table}")
        denied(conn, f"TRUNCATE ops.{table}")


def test_runner_cannot_change_the_schema(db):
    with db.session("runner") as conn:
        denied(conn, "CREATE TABLE ops.sneaky (x int)")
        denied(conn, "CREATE TABLE public.sneaky (x int)")
        denied(conn, "ALTER TABLE ops.alarm ADD COLUMN sneaky int")
        denied(conn, "DROP TABLE ops.audit_log")
        denied(conn, "DROP TRIGGER audit_log_no_change ON ops.audit_log")
        # PostgreSQL only warns when a non-owner tries to GRANT ("no privileges were granted"): check the effect
        conn.execute("GRANT ALL ON ops.audit_log TO app_runner")
        denied(conn, "UPDATE ops.audit_log SET outcome = 'DENIED'")
        denied(conn, "DELETE FROM ops.audit_log")


def test_runner_cannot_create_reference_data_or_samples(db):
    with db.session("runner") as conn:
        denied(conn, "INSERT INTO ops.operator VALUES ('mallory', 'M', 'HUMAN', 'SUPERVISOR')")
        denied(conn, "INSERT INTO ops.spacecraft (spacecraft_id, name) VALUES ('X', 'X')")
        denied(conn, "INSERT INTO ops.ground_station VALUES ('X', 'X', 0, 0, 5)")
        denied(conn, "INSERT INTO ops.telemetry_samples (spacecraft_id, parameter_name, sc_time_ms, value) "
                     "VALUES ('MINISAT-1', 'mode', 1, 1)")
        denied(conn, "UPDATE ops.operator SET role = 'SUPERVISOR' WHERE operator_id = 'alice'")


def test_runner_may_update_health_status_but_no_other_spacecraft_column(db):
    with db.session("runner") as conn:
        conn.execute("UPDATE ops.spacecraft SET health_status = 'WARNING' WHERE spacecraft_id = 'MINISAT-1'")
        denied(conn, "UPDATE ops.spacecraft SET name = 'renamed' WHERE spacecraft_id = 'MINISAT-1'")
        denied(conn, "UPDATE ops.spacecraft SET latest_values = '{}' WHERE spacecraft_id = 'MINISAT-1'")


def test_runner_can_append_to_the_audit_log_but_not_change_it(db):
    with db.session("runner") as conn:
        conn.execute("INSERT INTO ops.audit_log (operator_id, operator_kind, action, outcome) "
                     "VALUES ('alice', 'HUMAN', 'Propose Command', 'OK')")
        assert conn.execute("SELECT count(*) FROM ops.audit_log").fetchone()[0] >= 1
        denied(conn, "UPDATE ops.audit_log SET outcome = 'DENIED'")
        denied(conn, "DELETE FROM ops.audit_log")


def test_ingest_can_append_samples_and_refresh_latest_values_only(db):
    with db.session("ingest") as conn:
        conn.execute("INSERT INTO ops.telemetry_samples (spacecraft_id, parameter_name, sc_time_ms, value) "
                     "VALUES ('MINISAT-1', 'battery_soc_pct', 1000, 90.0)")
        cur = conn.execute("INSERT INTO ops.telemetry_samples (spacecraft_id, parameter_name, sc_time_ms, value) "
                           "VALUES ('MINISAT-1', 'battery_soc_pct', 1000, 91.0) ON CONFLICT DO NOTHING")
        assert cur.rowcount == 0                                          # a repeated packet is ignored, not an error
        conn.execute("UPDATE ops.spacecraft SET latest_values = '{\"mode\": 1}', last_contact_at = now() "
                     "WHERE spacecraft_id = 'MINISAT-1'")
        denied(conn, "UPDATE ops.spacecraft SET health_status = 'CRITICAL' WHERE spacecraft_id = 'MINISAT-1'")
        denied(conn, "UPDATE ops.telemetry_samples SET value = 0")
        denied(conn, "DELETE FROM ops.telemetry_samples")
        denied(conn, "SELECT * FROM ops.alarm")
        denied(conn, "SELECT * FROM ops.command_execution")
        denied(conn, "INSERT INTO ops.audit_log (action, outcome) VALUES ('x', 'OK')")
        denied(conn, "INSERT INTO ops.spacecraft_event (spacecraft_id, event_type, occurred_at) "
                     "VALUES ('MINISAT-1', 'REBOOT', now())")


def test_nobody_can_change_the_audit_log_not_even_the_owner_or_a_superuser(db):
    """The trigger refuses UPDATE, DELETE and TRUNCATE for every role (the exception is raised as a privilege error)."""
    for role in ("migrator", "admin"):
        with db.session(role) as conn:
            conn.execute("INSERT INTO ops.audit_log (operator_id, operator_kind, action, outcome) "
                         "VALUES ('alice', 'HUMAN', 'Propose Command', 'OK')")
            for statement in ("UPDATE ops.audit_log SET outcome = 'DENIED'", "DELETE FROM ops.audit_log",
                              "TRUNCATE ops.audit_log"):
                with pytest.raises(errors.InsufficientPrivilege, match="append-only"):
                    with conn.transaction():
                        conn.execute(statement)


def test_only_the_reader_can_see_which_schema_revision_is_installed(db):
    """Migration 0003 lets the API's readiness check read public.alembic_version; nobody else gets it, and nobody but the
    migrator can change it."""
    with db.session("admin") as conn:
        for role in ("app_runner", "app_reader", "ingest", "migrator"):
            granted = {p for p in PRIVILEGES + ["UPDATE"]
                       if conn.execute("SELECT has_table_privilege(%s, 'public.alembic_version', %s)", (role, p)).fetchone()[0]}
            assert granted == ({"SELECT"} if role == "app_reader" else {"SELECT", "INSERT", "DELETE", "TRUNCATE", "REFERENCES",
                                                                        "TRIGGER", "UPDATE"} if role == "migrator" else set()), role
    with db.session("reader") as conn:
        assert conn.execute("SELECT version_num FROM public.alembic_version").fetchone()[0] == "0003"
        denied(conn, "UPDATE public.alembic_version SET version_num = '0001'")
        denied(conn, "DELETE FROM public.alembic_version")
    for role in ("runner", "ingest"):
        with db.session(role) as conn:
            denied(conn, "SELECT * FROM public.alembic_version")
