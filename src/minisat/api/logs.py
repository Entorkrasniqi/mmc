"""Structured logs (protocols/observability-and-operations.md): one JSON object per line, UTC timestamps, and a
``correlationId`` on every line written while a request is being handled. Secrets and tokens are never passed to the log.
"""
from __future__ import annotations

import json
import logging
import sys
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Optional

__all__ = ["correlation_id_var", "JsonFormatter", "configure_logging", "log_event"]

# set by the request middleware; copied into the worker thread that runs a synchronous route
correlation_id_var: ContextVar[Optional[str]] = ContextVar("correlation_id", default=None)


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {"ts": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(timespec="milliseconds"),
                "level": record.levelname, "logger": record.name, "message": record.getMessage()}
        correlation_id = correlation_id_var.get()
        if correlation_id:                                   # for plain logging calls; log_event has already set its own
            data["correlationId"] = correlation_id
        data.update(getattr(record, "fields", None) or {})
        if record.exc_info:
            data["exception"] = self.formatException(record.exc_info)
        return json.dumps(data, default=str)


def log_event(logger: logging.Logger, level: int, event: str, exc_info=None, **fields) -> None:
    """``log_event(log, logging.INFO, "action", action="Propose Command", outcome="OK")``.

    The correlation id is taken when the event happens, not when a handler gets round to formatting it (which may be later,
    or in another thread). Pass ``correlationId=`` to name it explicitly, as code that runs outside the request must."""
    if "correlationId" not in fields and correlation_id_var.get():
        fields["correlationId"] = correlation_id_var.get()
    logger.log(level, event, exc_info=exc_info, extra={"fields": fields})


def configure_logging(level: int = logging.INFO) -> None:
    """Send the API's own logs (and uvicorn's errors) to standard output as JSON. Uvicorn's access log is replaced by ours."""
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    for name in ("minisat", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers[:] = [handler]
        logger.setLevel(level)
        logger.propagate = False
    logging.getLogger("uvicorn.access").disabled = True
