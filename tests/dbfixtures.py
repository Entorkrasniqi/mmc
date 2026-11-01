"""Fixtures for the tests in tests/db that need a real PostgreSQL server (imported by tests/conftest.py).

Set ``MINISAT_TEST_ADMIN_URL`` to a superuser connection, e.g. ``postgresql://postgres:secret@localhost:5432/postgres``.
Without it (or without psycopg, alembic or the ``psql`` program) every test in tests/db is skipped. The tests
create the four roles of db/roles.sql if missing, and a fresh database per use, which they drop afterwards.
There are no mocks: permissions are checked by connecting as the real roles.
"""
import os
import shutil
import subprocess
import uuid
from contextlib import contextmanager
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
ADMIN_URL_ENV = "MINISAT_TEST_ADMIN_URL"
PASSWORDS = {"migrator": "test-migrator-pw", "runner": "test-runner-pw", "reader": "test-reader-pw",
             "ingest": "test-ingest-pw"}


def _unavailable(reason):
    """Skip the database tests, or FAIL when MINISAT_REQUIRE_DB is set (CI), so that they can never skip unnoticed."""
    if os.environ.get("MINISAT_REQUIRE_DB"):
        pytest.fail(f"MINISAT_REQUIRE_DB is set but: {reason}")
    pytest.skip(reason)


@pytest.fixture(scope="session")
def admin_conninfo():
    url = os.environ.get(ADMIN_URL_ENV)
    if not url:
        _unavailable(f"{ADMIN_URL_ENV} is not set (a PostgreSQL superuser URL is needed for the database tests)")
    if shutil.which("psql") is None:
        _unavailable("the psql program is needed to apply db/roles.sql")
    return url


@pytest.fixture(scope="session")
def roles_ready(admin_conninfo):
    """Create (or refresh the passwords of) the four roles, exactly the way the Docker init script does.

    Roles belong to the whole server, so this changes their passwords. It therefore refuses to run on a server that holds
    the development database (named like MINISAT_DB_NAME, default "minisat"): use a throw-away server, for example
    ``docker run --rm -d -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:16``.
    """
    import psycopg
    dev_name = os.environ.get("MINISAT_DB_NAME", "minisat")
    with psycopg.connect(admin_conninfo) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (dev_name,)).fetchone():
            pytest.fail(f"{ADMIN_URL_ENV} points at a server that has a database called {dev_name!r}: this looks like the "
                        f"development database, and the tests would reset the passwords of its four roles. Point it at a "
                        f"throw-away PostgreSQL instead (see the docstring of roles_ready in tests/dbfixtures.py).")
    cmd = ["psql", admin_conninfo, "-v", "ON_ERROR_STOP=1", "-q",
           "-v", f"migrator_pw={PASSWORDS['migrator']}", "-v", f"runner_pw={PASSWORDS['runner']}",
           "-v", f"reader_pw={PASSWORDS['reader']}", "-v", f"ingest_pw={PASSWORDS['ingest']}",
           "-f", str(ROOT / "db" / "roles.sql")]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    return True


class Database:
    """A scratch database owned by the migrator role."""

    def __init__(self, name, admin_conninfo):
        from psycopg.conninfo import conninfo_to_dict
        self.name = name
        self._base = conninfo_to_dict(admin_conninfo)

    def conninfo(self, role):
        from psycopg.conninfo import make_conninfo
        user = {"migrator": "migrator", "runner": "app_runner", "reader": "app_reader", "ingest": "ingest",
                "admin": self._base.get("user")}[role]
        password = self._base.get("password") if role == "admin" else PASSWORDS[role]
        return make_conninfo(**{**self._base, "dbname": self.name, "user": user, "password": password})

    def sqlalchemy_url(self, role):
        from sqlalchemy.engine import URL
        from psycopg.conninfo import conninfo_to_dict
        d = conninfo_to_dict(self.conninfo(role))
        return URL.create("postgresql+psycopg", username=d["user"], password=d["password"], host=d["host"],
                          port=int(d.get("port", 5432)), database=d["dbname"]).render_as_string(hide_password=False)

    def connect_factory(self, role):
        """A function that opens a new dict-row connection as ``role`` (what the action runner and ingestor expect)."""
        import psycopg
        from psycopg.rows import dict_row
        return lambda: psycopg.connect(self.conninfo(role), row_factory=dict_row)

    @contextmanager
    def session(self, role):
        """A connection as ``role`` whose work is rolled back at the end, so tests do not affect each other."""
        import psycopg
        conn = psycopg.connect(self.conninfo(role))
        try:
            yield conn
        finally:
            conn.rollback()
            conn.close()

    def commit_params(self, role, statement, params):
        import psycopg
        with psycopg.connect(self.conninfo(role)) as conn:
            conn.execute(statement, params)

    def commit(self, role, *statements):
        """Run statements as ``role`` and keep the result (used to create reference data)."""
        import psycopg
        with psycopg.connect(self.conninfo(role)) as conn:
            for statement in statements:
                conn.execute(statement)


def alembic_config(url):
    from alembic.config import Config
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return cfg


@pytest.fixture(scope="session")
def database_factory(admin_conninfo, roles_ready):
    pytest.importorskip("psycopg")
    pytest.importorskip("alembic")
    import psycopg
    created = []

    def create(migrate=True, template=None):
        name = "minisat_test_" + uuid.uuid4().hex[:12]
        with psycopg.connect(admin_conninfo, autocommit=True) as conn:
            clone = f' TEMPLATE "{template.name}"' if template else ""
            conn.execute(f'CREATE DATABASE "{name}"{clone} OWNER migrator')
        created.append(name)
        db = Database(name, admin_conninfo)
        if template:                                    # a copy of a migrated and seeded database: nothing else to do
            return db
        subprocess.run(["psql", db.conninfo("admin"), "-v", "ON_ERROR_STOP=1", "-q", "-f",
                        str(ROOT / "db" / "database.sql")], check=True, capture_output=True, text=True)
        if migrate:
            from alembic import command
            command.upgrade(alembic_config(db.sqlalchemy_url("migrator")), "head")
        return db

    yield create
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        for name in created:
            conn.execute(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)')


SEED = [
    "INSERT INTO ops.operator VALUES ('alice', 'Alice', 'HUMAN', 'OPERATOR'), ('bob', 'Bob', 'HUMAN', 'OPERATOR'), "
    "('sam', 'Sam', 'HUMAN', 'SUPERVISOR'), ('tina', 'Tina', 'HUMAN', 'SUPERVISOR'), "
    "('vera', 'Vera', 'HUMAN', 'VIEWER'), ('helper', 'Helper', 'AGENT', 'AGENT'), "
    "('automation', 'Automation', 'SYSTEM', 'SYSTEM')",
    "INSERT INTO ops.spacecraft (spacecraft_id, name) VALUES ('MINISAT-1', 'MiniSat 1')",
    "INSERT INTO ops.ground_station VALUES ('HEL', 'Helsinki', 60.2, 24.9, 5)",
]


@pytest.fixture(scope="module")
def db(database_factory):
    """A migrated database with a few operators, one spacecraft and one station (committed reference data)."""
    database = database_factory()
    database.commit("migrator", *SEED)
    return database


@pytest.fixture()
def run(db):
    """A runner-role session; ``run.execute`` / ``run.fails`` for compact tests. Rolled back after each test."""
    with db.session("runner") as conn:
        yield conn


# ------------------------------------------------------------------------------------------------ action runner tests

class Clock:
    """A clock the test moves by hand, so expiry and timeouts need no sleeping."""

    def __init__(self, start=None):
        from datetime import datetime, timezone
        self.now = start or datetime.now(timezone.utc)

    def __call__(self):
        return self.now

    def advance(self, seconds):
        from datetime import timedelta
        self.now += timedelta(seconds=seconds)


@pytest.fixture(scope="session")
def template_db(database_factory):
    """A migrated database with the reference data of SEED; every test gets a copy of it."""
    database = database_factory()
    database.commit("migrator", *SEED)
    return database


@pytest.fixture()
def fresh_db(template_db, database_factory, admin_conninfo):
    import psycopg
    database = database_factory(template=template_db)
    yield database
    with psycopg.connect(admin_conninfo, autocommit=True) as conn:
        conn.execute(f'DROP DATABASE IF EXISTS "{database.name}" WITH (FORCE)')


@pytest.fixture()
def clock():
    return Clock()


class World:
    """A fresh database with an action runner on it, plus shortcuts the tests use."""

    def __init__(self, database, spec, clock, config=None):
        from minisat.ontology.actions import default_registry
        from minisat.ontology.runner import ActionRunner
        self.db, self.spec, self.clock = database, spec, clock
        self.runner = ActionRunner(database.connect_factory("runner"), spec, default_registry(), config=config, clock=clock)

    def run(self, operator, action, correlation_id=None, idempotency_key=None, **params):
        return self.runner.run(operator, action, params, correlation_id=correlation_id, idempotency_key=idempotency_key)

    def rows(self, query, *params):
        with self.db.session("admin") as conn:
            from psycopg.rows import dict_row
            return conn.cursor(row_factory=dict_row).execute(query, params).fetchall()

    def row(self, query, *params):
        rows = self.rows(query, *params)
        return rows[0] if rows else None

    def execution(self, execution_id):
        return self.row("SELECT * FROM ops.command_execution WHERE execution_id = %s", execution_id)

    def audit(self, **where):
        clause = " AND ".join(f"{k} = %s" for k in where) or "true"
        return self.rows(f"SELECT * FROM ops.audit_log WHERE {clause} ORDER BY audit_id", *where.values())

    def set_state(self, **values):
        """Pretend telemetry arrived: set the newest values of MINISAT-1 and its last contact (as the ingest role would)."""
        from psycopg.types.json import Jsonb
        self.db.commit_params("migrator", "UPDATE ops.spacecraft SET latest_values = latest_values || %s, "
                              "last_contact_at = %s WHERE spacecraft_id = 'MINISAT-1'", (Jsonb(values), self.clock.now))

    def contact_window(self, minutes=10):
        """A contact window around now (planned as the supervisor would)."""
        from datetime import timedelta
        return self.run("sam", "Plan Contact", spacecraft_id="MINISAT-1", station_id="HEL",
                        start_at=(self.clock.now - timedelta(minutes=1)).isoformat(),
                        end_at=(self.clock.now + timedelta(minutes=minutes)).isoformat())


@pytest.fixture()
def world(fresh_db, spec, clock):
    return World(fresh_db, spec, clock)
