"""The HTTP API (PLAN.md phase 4): FastAPI over the ontology.

    browser / agent --HTTP--> this app --reads as app_reader--> PostgreSQL
                                       \\--actions via ActionRunner as app_runner--> PostgreSQL --outbox--> ground station

* reads: ``routes_read.py`` (objects, links, series, functions); the SQL is in ``store.py``;
* writes: ``routes_actions.py``, one route per action of the registry, all through the action runner;
* who is calling: ``auth.py`` (a DEV-ONLY static token per operator); what they may do: the runner;
* ``/health/live``, ``/health/ready``, ``/metrics``, JSON logs with correlation IDs (protocols/observability-and-operations.md).
"""
from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Callable, Optional

import psycopg
from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.middleware.cors import CORSMiddleware

from .. import __version__
from ..ontology.actions import default_registry
from ..ontology.runner import ActionRegistry, ActionRunner, RunnerConfig, utcnow
from ..spec import Spec
from .auth import DevTokenAuthenticator, current_principal
from .context import AppContext, context_of
from .health import readiness
from .logs import correlation_id_var, log_event
from .metrics import ApiMetrics
from .routes_actions import build_router
from .routes_read import router as read_router
from .settings import ApiSettings
from .store import Store

__all__ = ["create_app"]

log = logging.getLogger("minisat.api")
CORRELATION_HEADER = "X-Correlation-ID"
QUIET_PATHS = ("/health/", "/metrics")                       # probes and scrapes every few seconds: DEBUG, not INFO


def _correlation_id(request: Request) -> uuid.UUID:
    """Reuse the caller's id if it is a UUID (so a click can be followed through every log line), else make one."""
    try:
        return uuid.UUID(request.headers.get(CORRELATION_HEADER, ""))
    except ValueError:
        return uuid.uuid4()


def create_app(settings: ApiSettings, spec: Spec, connect_reader: Callable, connect_runner: Callable, *,
               registry: Optional[ActionRegistry] = None, runner_config: Optional[RunnerConfig] = None,
               clock: Callable[[], datetime] = utcnow) -> FastAPI:
    """``connect_reader`` / ``connect_runner`` open a new connection as ``app_reader`` / ``app_runner``."""
    registry = registry or default_registry()
    store = Store(connect_reader)
    runner = ActionRunner(connect_runner, spec, registry, config=runner_config, clock=clock)
    ctx = AppContext(settings=settings, spec=spec, defs=runner.definitions, store=store, connect_runner=connect_runner,
                     runner=runner, registry=registry, authenticator=DevTokenAuthenticator(settings.dev_tokens),
                     metrics=ApiMetrics(store, clock), clock=clock)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if ctx.authenticator.enabled:
            log.warning("DEV-ONLY authentication is on: a static bearer token for %d operator(s). Not for any shared "
                        "deployment (protocols/security-and-threat-model.md)", len(settings.dev_tokens))
        else:
            log.warning("no MINISAT_API_DEV_TOKENS are set: every route except /health/* answers 401")
        yield

    app = FastAPI(title="MiniSat mission control API", version=__version__, lifespan=lifespan,
                  description="Objects, links and series of the ontology, and its actions. Authentication is a DEV-ONLY "
                              "static bearer token per operator.",
                  docs_url="/docs" if settings.docs else None, redoc_url=None,
                  openapi_url="/openapi.json" if settings.docs else None)
    app.state.ctx = ctx

    # ---------------------------------------------------------------------------------------------- every request
    @app.middleware("http")
    async def request_context(request: Request, call_next):
        correlation_id = _correlation_id(request)
        request.state.correlation_id = correlation_id
        token = correlation_id_var.set(str(correlation_id))
        started, status = time.perf_counter(), 500
        try:
            response = await call_next(request)
            status = response.status_code
        finally:
            seconds = time.perf_counter() - started
            route = request.scope.get("route")
            label = getattr(route, "path", None) or "unmatched"          # the route template, so the labels stay few
            ctx.metrics.requests.labels(request.method, label, str(status)).inc()
            ctx.metrics.request_seconds.labels(request.method, label).observe(seconds)
            quiet = request.url.path.startswith(QUIET_PATHS)
            log_event(log, logging.DEBUG if quiet else logging.INFO, "request", method=request.method,
                      path=request.url.path, status=status, durationMs=round(seconds * 1000, 1),
                      operator=getattr(request.state, "operator_id", None))
            correlation_id_var.reset(token)
        response.headers[CORRELATION_HEADER] = str(correlation_id)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    # the dashboard's origin only; the browser may read the correlation id to quote it in a bug report
    app.add_middleware(CORSMiddleware, allow_origins=list(settings.cors_origins), allow_methods=["GET", "POST"],
                       allow_headers=["Authorization", "Content-Type", "Idempotency-Key", CORRELATION_HEADER],
                       expose_headers=[CORRELATION_HEADER])

    # ---------------------------------------------------------------------------------------------- errors
    def _error(request: Request, status: int, detail: str) -> JSONResponse:
        cid = getattr(request.state, "correlation_id", None) or uuid.uuid4()
        return JSONResponse(status_code=status, content={"detail": detail, "correlation_id": str(cid)},
                            headers={CORRELATION_HEADER: str(cid), "Cache-Control": "no-store"})

    @app.exception_handler(psycopg.OperationalError)
    async def database_unavailable(request: Request, exc: psycopg.OperationalError):
        log_event(log, logging.ERROR, "database unavailable", error=str(exc).strip(), path=request.url.path,
                  correlationId=str(getattr(request.state, "correlation_id", "")))
        return _error(request, 503, "the database is unavailable; nothing was changed")

    @app.exception_handler(Exception)
    async def unexpected(request: Request, exc: Exception):
        # this handler runs outside the request middleware, after it has reset the correlation id: name it explicitly
        log_event(log, logging.ERROR, "unhandled error", exc_info=exc, method=request.method, path=request.url.path,
                  correlationId=str(getattr(request.state, "correlation_id", "")))
        return _error(request, 500, "internal error; the details are in the server log under this correlation id")

    # ---------------------------------------------------------------------------------------------- probes and metrics
    @app.get("/health/live", tags=["operations"], summary="The process is up (touches nothing else)")
    def live():
        return {"status": "ok"}

    @app.get("/health/ready", tags=["operations"], summary="Database, migrations and fresh telemetry")
    def ready(request: Request, response: Response):
        report = readiness(context_of(request))
        response.status_code = 200 if report["status"] == "ready" else 503
        return report

    @app.get("/metrics", tags=["operations"], summary="Prometheus metrics (needs a token)",
             dependencies=[Depends(current_principal)])
    def metrics(request: Request):
        return Response(generate_latest(context_of(request).metrics.registry), media_type=CONTENT_TYPE_LATEST)

    app.include_router(read_router)
    app.include_router(build_router(registry))
    return app
