"""Liveness and readiness (protocols/observability-and-operations.md).

``/health/live``   the process answers; it touches nothing else.
``/health/ready``  the API can really do its job: the database is reachable as the reader and as the runner, the schema is
                   on the revision this code expects, and telemetry is fresh (unless the stack has no live source).

The answer names the checks and whether each passed. It never contains connection strings, passwords or SQL errors.
"""
from __future__ import annotations

import logging
from typing import Dict

import psycopg

from ..ontology.functions import telemetry_period_s
from .context import AppContext

__all__ = ["EXPECTED_SCHEMA_REVISION", "readiness"]

log = logging.getLogger("minisat.api.health")

# The newest migration in migrations/versions; tests/api/test_health.py fails if this and the migrations disagree.
EXPECTED_SCHEMA_REVISION = "0003"


def _check(ok: bool, detail: str) -> Dict[str, object]:
    return {"ok": ok, "detail": detail}


def readiness(ctx: AppContext) -> Dict[str, object]:
    checks: Dict[str, Dict[str, object]] = {}
    try:
        with ctx.store.session() as conn:
            checks["database_reader"] = _check(True, "the read-only role can connect")
            row = None
            try:
                row = conn.execute("SELECT version_num FROM public.alembic_version").fetchone()
            except psycopg.Error:                       # no table or no privilege: it cannot be shown to be current
                conn.rollback()
            if row is None:
                checks["migrations"] = _check(False, "the installed schema revision cannot be read")
            elif row["version_num"] != EXPECTED_SCHEMA_REVISION:
                checks["migrations"] = _check(False, f"the database is on revision {row['version_num']}, "
                                                     f"this code needs {EXPECTED_SCHEMA_REVISION}: run 'alembic upgrade head'")
            else:
                checks["migrations"] = _check(True, f"on revision {EXPECTED_SCHEMA_REVISION}")
            newest = conn.execute("SELECT max(last_contact_at) AS newest, count(*) AS n FROM ops.spacecraft").fetchone()
    except psycopg.Error as exc:
        log.warning("readiness: the database is not usable: %s", exc)
        checks["database_reader"] = _check(False, "the read-only role cannot connect or query")
        checks.pop("migrations", None)
        return {"status": "not ready", "checks": checks}

    try:
        runner_conn = ctx.connect_runner()
        try:
            runner_conn.execute("SELECT 1")
            checks["database_runner"] = _check(True, "the action runner's role can connect")
        finally:
            runner_conn.close()
    except psycopg.Error as exc:
        log.warning("readiness: the runner role cannot connect: %s", exc)
        checks["database_runner"] = _check(False, "the action runner's role cannot connect")

    if not ctx.settings.live_source:
        checks["telemetry"] = _check(True, "skipped: the stack is configured without a live telemetry source")
    elif newest["n"] == 0:
        checks["telemetry"] = _check(False, "no spacecraft exists yet (run 'minisat db-seed')")
    else:
        limit = ctx.runner.config.stale_factor * telemetry_period_s(ctx.spec)
        age = (ctx.clock() - newest["newest"]).total_seconds() if newest["newest"] else None
        if age is None:
            checks["telemetry"] = _check(False, "no telemetry has ever been received")
        elif age > limit:
            checks["telemetry"] = _check(False, f"the newest telemetry is {age:.1f} s old (limit {limit:g} s)")
        else:
            checks["telemetry"] = _check(True, f"the newest telemetry is {age:.1f} s old")
    ready = all(c["ok"] for c in checks.values())
    return {"status": "ready" if ready else "not ready", "checks": checks}
