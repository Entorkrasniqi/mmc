"""Where the database is and how each database role connects (protocols/action-runner-and-audit.md).

Four roles, each with its own password, all read from environment variables (never from code):

    migrator  owns the schema; used only by the migration tool
    runner    the action runner: the only role that writes the operations tables
    reader    read-only: API reads, dashboard, agent read tools
    ingest    appends telemetry samples and updates the latest values of a spacecraft; nothing else
"""
from __future__ import annotations

import os
from typing import Mapping, Optional
from urllib.parse import quote

__all__ = ["ROLES", "ROLE_NAMES", "ConfigError", "database_url"]

ROLE_NAMES = {"migrator": "migrator", "runner": "app_runner", "reader": "app_reader", "ingest": "ingest"}
ROLES = tuple(ROLE_NAMES)


class ConfigError(RuntimeError):
    """A required setting is missing or wrong."""


def database_url(role: str, env: Optional[Mapping[str, str]] = None) -> str:
    """The SQLAlchemy/psycopg URL for connecting as one of the four roles.

    Reads ``MINISAT_DB_HOST`` (default localhost), ``MINISAT_DB_PORT`` (5432), ``MINISAT_DB_NAME`` (minisat) and
    ``MINISAT_DB_PASSWORD_<ROLE>`` (required).
    """
    if role not in ROLE_NAMES:
        raise ConfigError(f"unknown database role {role!r} (known: {', '.join(ROLES)})")
    env = os.environ if env is None else env
    var = f"MINISAT_DB_PASSWORD_{role.upper()}"
    password = env.get(var)
    if not password:
        raise ConfigError(f"{var} is not set (copy .env.example to .env and load it)")
    host = env.get("MINISAT_DB_HOST", "localhost")
    port = env.get("MINISAT_DB_PORT", "5432")
    name = env.get("MINISAT_DB_NAME", "minisat")
    if not port.isdigit():
        raise ConfigError(f"MINISAT_DB_PORT must be a number, got {port!r}")
    return f"postgresql+psycopg://{ROLE_NAMES[role]}:{quote(password, safe='')}@{host}:{port}/{name}"
