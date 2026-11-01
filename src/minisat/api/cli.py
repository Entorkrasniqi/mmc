"""``minisat api`` runs the HTTP API; ``minisat dev-tokens`` makes the tokens it accepts (DEV ONLY).

Settings come from the environment (MINISAT_DB_*, MINISAT_API_*); a ``.env`` file in the current directory is read first.
"""
from __future__ import annotations

import ipaddress
import re
import secrets
import sys

from ..ontology.cli import _guard, _load_dotenv
from ..spec import load_spec

__all__ = ["cmd_api", "cmd_dev_tokens", "DEMO_OPERATOR_IDS", "make_dev_tokens"]

DEMO_OPERATOR_IDS = ("alice", "bob", "sam", "tina", "vera", "helper")      # the operators of 'minisat db-seed --demo'
OPERATOR_ID = re.compile(r"^[A-Za-z0-9_.-]+$")


def make_dev_tokens(operator_ids) -> str:
    """A ready-to-paste ``MINISAT_API_DEV_TOKENS=...`` line with a random token per operator (32 bytes of randomness each)."""
    bad = [o for o in operator_ids if not OPERATOR_ID.match(o)]
    if bad:
        raise ValueError(f"not a usable operator id: {', '.join(map(repr, bad))} (letters, digits, '_', '.', '-')")
    if len(set(operator_ids)) != len(operator_ids):
        raise ValueError("an operator was named twice")
    return "MINISAT_API_DEV_TOKENS=" + ",".join(f"{o}={secrets.token_urlsafe(32)}" for o in operator_ids)


def cmd_dev_tokens(args) -> int:
    try:
        line = make_dev_tokens(args.operators or DEMO_OPERATOR_IDS)
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    print("# DEV ONLY: static tokens, no expiry. Put this line in .env (which git ignores); never commit it.")
    print(line)
    return 0


def _is_loopback(host: str) -> bool:
    if host == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


@_guard
def cmd_api(args) -> int:
    import uvicorn
    from ..ontology.dbconfig import connect
    from ..ontology.runner import RunnerConfig
    from .app import create_app
    from .logs import configure_logging
    from .settings import ApiSettings

    settings = ApiSettings.from_env()
    if not _is_loopback(args.host) and not args.allow_remote:
        print(f"refusing to listen on {args.host}: the only authentication is a static DEV-ONLY token per operator, which "
              f"must not be reachable from a network. Use 127.0.0.1, or --allow-remote if you understand that.", file=sys.stderr)
        return 2
    spec = load_spec(args.spec)
    app = create_app(settings, spec, lambda: connect("reader"), lambda: connect("runner"),
                     runner_config=RunnerConfig(require_contact=not args.no_contact_check))
    configure_logging(args.log_level)
    uvicorn.run(app, host=args.host, port=args.port, log_config=None, access_log=False)
    return 0
