import pytest

pytest.importorskip("psycopg")
pytest.importorskip("alembic")

from alembic import command  # noqa: E402

from dbfixtures import PASSWORDS, ROOT, alembic_config  # noqa: E402

EXPECTED_TABLES = {
    "operator", "spacecraft", "ground_station", "contact_window", "anomaly", "alarm", "command_execution",
    "anomaly_command_execution", "spacecraft_event", "telemetry_samples", "audit_log", "outbox",
}


def _tables(db):
    with db.session("admin") as conn:
        rows = conn.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'ops'").fetchall()
    return {r[0] for r in rows}


def test_upgrade_creates_exactly_the_operations_tables(db):
    assert _tables(db) == EXPECTED_TABLES


def test_the_definition_layer_is_not_stored_in_the_database(db):
    # ADR 0001: parameters, packet types and command definitions come from the specification
    assert not {t for t in _tables(db) if "definition" in t or t in ("telemetry_parameter", "telemetry_packet_type")}


def test_downgrade_removes_everything_and_upgrade_works_again(database_factory):
    database = database_factory()
    cfg = alembic_config(database.sqlalchemy_url("migrator"))
    assert _tables(database) == EXPECTED_TABLES
    command.downgrade(cfg, "base")
    assert _tables(database) == set()
    command.upgrade(cfg, "head")
    assert _tables(database) == EXPECTED_TABLES


def test_upgrade_is_refused_with_a_clear_message_when_a_role_is_missing(admin_conninfo, roles_ready, database_factory):
    import psycopg
    database = database_factory(migrate=False)
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        conn.execute("ALTER ROLE ingest RENAME TO ingest_gone")
    try:
        with pytest.raises(Exception, match="database roles missing: ingest"):
            command.upgrade(alembic_config(database.sqlalchemy_url("migrator")), "head")
    finally:
        with psycopg.connect(admin_conninfo, autocommit=True) as conn:
            conn.execute("ALTER ROLE ingest_gone RENAME TO ingest")
        # renaming a role clears its password; restore it
        with psycopg.connect(admin_conninfo, autocommit=True) as conn:
            conn.execute(f"ALTER ROLE ingest PASSWORD '{PASSWORDS['ingest']}'")


def test_running_the_roles_script_twice_is_harmless(admin_conninfo, roles_ready):
    import subprocess
    cmd = ["psql", admin_conninfo, "-v", "ON_ERROR_STOP=1", "-q", "-v", f"migrator_pw={PASSWORDS['migrator']}",
           "-v", f"runner_pw={PASSWORDS['runner']}", "-v", f"reader_pw={PASSWORDS['reader']}",
           "-v", f"ingest_pw={PASSWORDS['ingest']}", "-f", str(ROOT / "db" / "roles.sql")]
    assert subprocess.run(cmd, capture_output=True, text=True).returncode == 0


def test_roles_have_no_dangerous_attributes(admin_conninfo, roles_ready):
    import psycopg
    with psycopg.connect(admin_conninfo) as conn:
        rows = conn.execute(
            "SELECT rolname, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolcanlogin FROM pg_roles "
            "WHERE rolname IN ('migrator', 'app_runner', 'app_reader', 'ingest') ORDER BY rolname").fetchall()
    assert [r[0] for r in rows] == ["app_reader", "app_runner", "ingest", "migrator"]
    for name, sup, createdb, createrole, repl, login in rows:
        assert (sup, createdb, createrole, repl, login) == (False, False, False, False, True), name


def test_migration_0002_downgrades_to_0001_and_upgrades_again(database_factory):
    database = database_factory()
    cfg = alembic_config(database.sqlalchemy_url("migrator"))

    def columns():
        with database.session("admin") as conn:
            return {r[0] for r in conn.execute("SELECT column_name FROM information_schema.columns "
                                               "WHERE table_schema = 'ops' AND table_name = 'command_execution'")}
    assert {"preflight", "send_baseline", "cancelled_by", "expected_effect"} <= columns()
    command.downgrade(cfg, "0001")
    assert not ({"preflight", "send_baseline", "cancelled_by"} & columns())
    command.upgrade(cfg, "head")
    assert {"preflight", "send_baseline", "cancelled_by"} <= columns()


def test_migration_0003_gives_and_takes_back_the_readers_view_of_the_revision(database_factory):
    database = database_factory()
    cfg = alembic_config(database.sqlalchemy_url("migrator"))

    def reader_can_see_it():
        with database.session("admin") as conn:
            return conn.execute("SELECT has_table_privilege('app_reader', 'public.alembic_version', 'SELECT')").fetchone()[0]
    assert reader_can_see_it()
    command.downgrade(cfg, "0002")
    assert not reader_can_see_it()
    command.upgrade(cfg, "head")
    assert reader_can_see_it()
