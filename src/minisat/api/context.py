"""What every route can reach: the specification, the read-only store, the action runner and the settings."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Callable

from fastapi import Request

from ..ontology.definitions import Definitions
from ..ontology.runner import ActionRegistry, ActionRunner
from ..spec import Spec
from .auth import DevTokenAuthenticator
from .metrics import ApiMetrics
from .settings import ApiSettings
from .store import Store

__all__ = ["AppContext", "context_of"]


@dataclass
class AppContext:
    settings: ApiSettings
    spec: Spec
    defs: Definitions
    store: Store                             # reads, as the app_reader role
    connect_runner: Callable                 # a connection as app_runner: used for the readiness check only
    runner: ActionRunner                     # writes, as app_runner, through the action runner and nothing else
    registry: ActionRegistry
    authenticator: DevTokenAuthenticator
    metrics: ApiMetrics
    clock: Callable[[], datetime]


def context_of(request: Request) -> AppContext:
    return request.app.state.ctx
