"""Action routes, generated from the action registry (protocols/action-runner-and-audit.md: "the UI, the API and the agent tools
are all generated from this registry. Nothing else defines what an action is.").

``POST /api/actions/<slug>`` runs one action as the calling operator. The route does not check the role and does not
validate the parameters: the body goes to the action runner as it is, because the runner does both and records every refusal in
the audit log. (If this layer validated first, a bad request would never be audited.)

Actions that only the system may run (raising alarms, recording that a command was sent, ...) are not exposed here at all: the
ground station runs them in its own process, and a caller of this API is a person or the agent.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

import psycopg
from fastapi import APIRouter, Body, Depends, Header, Request
from fastapi.responses import JSONResponse

from ..ontology.runner import Action, ActionError, ActionRegistry
from .auth import Principal, current_principal
from .context import context_of
from .logs import log_event

__all__ = ["build_router", "slug", "exposed_actions"]

log = logging.getLogger("minisat.api.actions")

STATUS = {"DENIED": 403, "INVALID": 422, "ERROR": 500}


def slug(action_name: str) -> str:
    return action_name.lower().replace(" ", "-")


def exposed_actions(registry: ActionRegistry):
    """Every action that someone other than the system may run."""
    return [a for a in registry if a.roles - {"SYSTEM"}]


def _failure(exc: ActionError, correlation_id) -> JSONResponse:
    detail = str(exc)
    if exc.outcome == "ERROR":               # what the database said stays in the log; the caller gets the audit number
        detail = f"the action failed unexpectedly (audit #{exc.audit_id}); see the server log with this correlation id"
    return JSONResponse(status_code=STATUS.get(exc.outcome, 500),
                        content={"detail": detail, "outcome": exc.outcome, "action": exc.action, "audit_id": exc.audit_id,
                                 "correlation_id": str(correlation_id)})


def _handler(action: Action):
    def run_action(request: Request, body: Optional[Dict[str, Any]] = Body(default=None),
                   principal: Principal = Depends(current_principal),
                   idempotency_key: Optional[str] = Header(default=None, alias="Idempotency-Key", max_length=200)):
        ctx = context_of(request)
        correlation_id = request.state.correlation_id
        started, outcome, audit_id = time.perf_counter(), "EXCEPTION", None
        try:
            result = ctx.runner.run(principal.operator_id, action.name, body or {}, correlation_id=correlation_id,
                                    idempotency_key=idempotency_key)
            outcome, audit_id = "OK", result.audit_id
            return {"action": result.action, "audit_id": result.audit_id, "result": result.result,
                    "warnings": list(result.warnings), "replayed": result.replayed, "correlation_id": str(correlation_id)}
        except ActionError as exc:
            outcome, audit_id = exc.outcome, exc.audit_id
            if exc.outcome == "ERROR":
                log_event(log, logging.ERROR, "action failed", action=action.name, auditId=exc.audit_id, error=str(exc))
            return _failure(exc, correlation_id)
        except psycopg.OperationalError:          # fail closed: nothing was written; the app answers 503
            outcome = "UNAVAILABLE"
            raise
        finally:
            seconds = time.perf_counter() - started
            ctx.metrics.actions.labels(action.name, outcome).inc()
            ctx.metrics.action_seconds.labels(action.name).observe(seconds)
            log_event(log, logging.INFO, "action", action=action.name, outcome=outcome, auditId=audit_id,
                      operator=principal.operator_id, durationMs=round(seconds * 1000, 1))
    return run_action


def build_router(registry: ActionRegistry) -> APIRouter:
    router = APIRouter(prefix="/api", dependencies=[Depends(current_principal)])

    @router.get("/actions", tags=["actions"], summary="The actions this API exposes, who may run them, and their parameters")
    def list_actions(principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
        return {"items": [{"name": a.name, "slug": slug(a.name), "path": f"/api/actions/{slug(a.name)}",
                           "description": a.description, "roles": sorted(a.roles - {"SYSTEM"}),
                           "agent_callable": a.agent_callable, "requires_human_confirmation": a.requires_human_confirmation,
                           "allowed_for_me": principal.role in a.roles, "schema": a.json_schema()}
                          for a in exposed_actions(registry)]}

    for action in exposed_actions(registry):
        router.add_api_route(
            f"/actions/{slug(action.name)}", _handler(action), methods=["POST"], name=action.name, tags=["actions"],
            summary=action.name, description=f"{action.description}\n\nRoles: {', '.join(sorted(action.roles - {'SYSTEM'}))}.",
            openapi_extra={"requestBody": {"required": False, "content": {"application/json": {"schema": action.json_schema()}}}},
            responses={403: {"description": "the role may not run this action (audited as DENIED)"},
                       422: {"description": "invalid parameters, or the rules refuse it in the current state (audited as INVALID)"}})
    return router
