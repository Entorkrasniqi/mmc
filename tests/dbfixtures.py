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
    """Create (or refresh the passwords of) the four roles, exactly the way the Docker init script does."""
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

    def create(migrate=True):
        name = "minisat_test_" + uuid.uuid4().hex[:12]
        with psycopg.connect(admin_conninfo, autocommit=True) as conn:
            conn.execute(f'CREATE DATABASE "{name}" OWNER migrator')
        created.append(name)
        db = Database(name, admin_conninfo)
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
    "INSERT INTO ops.operator VALUES ('alice', 'Alice', 'HUMAN', 'OPERATOR'), ('sam', 'Sam', 'HUMAN', 'SUPERVISOR'), "
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
