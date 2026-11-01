"""Who is calling (protocols/security-and-threat-model.md, threat 3).

**DEV ONLY.** Authentication here is a static bearer token per operator, set in ``MINISAT_API_DEV_TOKENS``. That is enough to
tell operators apart on one machine and to test the role checks; it is NOT a login: tokens do not expire, cannot be revoked
without a restart, and anyone who reads the environment can use them. A shared deployment needs real login (OIDC) and
short-lived tokens, which is an open decision in PLAN.md. With no tokens configured, nobody can call the API.

The role is read from the database on every request, so a role change takes effect at once. The roles themselves are
enforced by the action runner, not here: this module only says who the caller is.
"""
from __future__ import annotations

import hmac
import logging
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .logs import log_event
from .store import get_operator

__all__ = ["Principal", "DevTokenAuthenticator", "current_principal", "bearer"]

log = logging.getLogger("minisat.api.auth")
bearer = HTTPBearer(auto_error=False, description="DEV ONLY: a static token from MINISAT_API_DEV_TOKENS")


@dataclass(frozen=True)
class Principal:
    operator_id: str
    display_name: str
    kind: str          # HUMAN | AGENT
    role: str          # VIEWER | OPERATOR | SUPERVISOR | AGENT


class DevTokenAuthenticator:
    def __init__(self, tokens: Iterable[Tuple[str, str]] = ()):
        self._tokens = [(operator_id, token.encode()) for operator_id, token in tokens]

    @property
    def enabled(self) -> bool:
        return bool(self._tokens)

    def operator_for(self, presented: str) -> Optional[str]:
        """The operator that owns this token. Compares against every token so the time taken does not reveal a near miss."""
        data, found = presented.encode(), None
        for operator_id, token in self._tokens:
            if hmac.compare_digest(token, data):
                found = operator_id
        return found


def _unauthorised(request: Request, reason: str) -> HTTPException:
    # the same answer for every reason: the caller learns nothing about which operators exist; the log says why
    log_event(log, logging.WARNING, "authentication failed", reason=reason, method=request.method, path=request.url.path)
    return HTTPException(status_code=401, detail="authentication required: send 'Authorization: Bearer <token>'",
                         headers={"WWW-Authenticate": "Bearer"})


def current_principal(request: Request,
                      credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer)) -> Principal:
    from .context import context_of
    ctx = context_of(request)
    if credentials is None:
        raise _unauthorised(request, "no token")
    operator_id = ctx.authenticator.operator_for(credentials.credentials)
    if operator_id is None:
        raise _unauthorised(request, "unknown token")
    with ctx.store.session() as conn:
        row = get_operator(conn, operator_id)
    if row is None:
        raise _unauthorised(request, f"token of {operator_id!r}, who does not exist")
    if row["kind"] == "SYSTEM":                       # the automation account acts inside the ground station, never over HTTP
        raise _unauthorised(request, f"token of {operator_id!r}, a SYSTEM operator")
    request.state.operator_id = operator_id
    return Principal(row["operator_id"], row["display_name"], row["kind"], row["role"])
