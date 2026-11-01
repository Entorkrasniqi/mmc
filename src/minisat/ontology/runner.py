"""The action runner: the one place where operations data is allowed to change (protocols/action-runner-and-audit.md).

Every call to :meth:`ActionRunner.run` does the same steps:

1. look the caller up (an unknown operator is refused);
2. check the caller's role may run this action at all;
3. validate the parameters against the action's typed schema;
4. replay the stored result if the same idempotency key was already used successfully;
5. apply the action in ONE database transaction together with its audit row and any outbox messages;
6. commit.

A refused attempt (DENIED or INVALID) or a failure (ERROR) is audited too, in its own transaction, then raised as an
:class:`ActionError`. The database enforces the most important rules a second time (two-person rule, human-only approval,
append-only audit log), so a bug in a handler cannot silently break them.

The outbox (``ops.outbox``) is infrastructure, not business state: the worker claims and completes its rows directly.
"""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple, Type

import psycopg
from psycopg import errors as pg_errors
from psycopg import sql
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb
from pydantic import BaseModel, ValidationError

from ..spec import Spec
from .definitions import Definitions, definitions_from_spec

__all__ = ["ActionError", "PermissionDenied", "InvalidAction", "ActionFailed", "Operator", "Outcome", "ActionResult",
           "RunnerConfig", "ActionContext", "Action", "ActionRegistry", "ActionRunner", "utcnow"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _dumps(obj) -> str:
    return json.dumps(obj, default=str)


def _json(obj) -> Jsonb:
    return Jsonb(obj, dumps=_dumps)


# ------------------------------------------------------------------------------------------------ results and errors

class ActionError(Exception):
    """An action did not happen. ``outcome`` is the value written to the audit log."""
    outcome = "ERROR"

    def __init__(self, message: str, *, audit_id: Optional[int] = None, action: Optional[str] = None):
        super().__init__(message)
        self.audit_id = audit_id
        self.action = action


class PermissionDenied(ActionError):
    """The operator may not do this (wrong role, two-person rule, unknown operator)."""
    outcome = "DENIED"


class InvalidAction(ActionError):
    """The request is not valid in the current state (bad parameters, wrong status, expired, conflict)."""
    outcome = "INVALID"


class ActionFailed(ActionError):
    """Something unexpected went wrong (for example the database refused a change the handler did not foresee)."""
    outcome = "ERROR"


@dataclass(frozen=True)
class Operator:
    operator_id: str
    display_name: str
    kind: str          # HUMAN | AGENT | SYSTEM
    role: str          # VIEWER | OPERATOR | SUPERVISOR | AGENT | SYSTEM


@dataclass
class Outcome:
    """What a handler returns: the answer for the caller and snapshots of what it changed, for the audit log."""
    result: Dict[str, Any]
    before: Dict[str, Any] = field(default_factory=dict)
    after: Dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ActionResult:
    action: str
    audit_id: int
    result: Dict[str, Any]
    warnings: Tuple[str, ...]
    correlation_id: uuid.UUID
    replayed: bool = False


@dataclass(frozen=True)
class RunnerConfig:
    proposal_ttl: timedelta = timedelta(minutes=15)      # how long a proposal (and its approval) stays valid
    stale_factor: float = 3.0                            # telemetry older than this many periods is "stale"
    require_contact: bool = True                         # releasing needs a contact window (a supervisor may override)


# ------------------------------------------------------------------------------------------------ context for handlers

class ActionContext:
    """What a handler may use: the open transaction, who is calling, the time, and small SQL helpers.

    Table and column names passed to the helpers come from code, never from a request.
    """

    def __init__(self, conn, operator: Operator, now: datetime, spec: Spec, definitions: Definitions,
                 config: RunnerConfig, correlation_id: uuid.UUID):
        self.conn = conn
        self.operator = operator
        self.now = now
        self.spec = spec
        self.definitions = definitions
        self.config = config
        self.correlation_id = correlation_id
        self.warnings: List[str] = []

    # ---- outcomes
    def invalid(self, message: str):
        raise InvalidAction(message)

    def deny(self, message: str):
        raise PermissionDenied(message)

    def warn(self, message: str) -> None:
        self.warnings.append(message)

    # ---- reading
    def one(self, query: str, params=()) -> Optional[dict]:
        return self.conn.execute(query, params).fetchone()

    def all(self, query: str, params=()) -> List[dict]:
        return self.conn.execute(query, params).fetchall()

    def snapshot(self, table: str, key_col: str, key) -> Optional[dict]:
        """The row as JSON (what goes into the audit log)."""
        row = self.one(sql.SQL("SELECT to_jsonb(t) AS j FROM ops.{} t WHERE {} = %s").format(
            sql.Identifier(table), sql.Identifier(key_col)), (key,))
        return row["j"] if row else None

    def lock(self, table: str, key_col: str, key, what: str) -> dict:
        """Read one row and lock it until the transaction ends, so two actions cannot change it at once."""
        row = self.one(sql.SQL("SELECT * FROM ops.{} WHERE {} = %s FOR UPDATE").format(
            sql.Identifier(table), sql.Identifier(key_col)), (key,))
        if row is None:
            self.invalid(f"no such {what}: {key}")
        return row

    # ---- writing (all values are passed as parameters)
    @staticmethod
    def _adapt(value):
        return _json(value) if isinstance(value, (dict, list)) else value

    def insert(self, table: str, **fields) -> dict:
        query = sql.SQL("INSERT INTO ops.{} ({}) VALUES ({}) RETURNING *").format(
            sql.Identifier(table), sql.SQL(", ").join(map(sql.Identifier, fields)),
            sql.SQL(", ").join(sql.Placeholder() * len(fields)))
        return self.conn.execute(query, [self._adapt(v) for v in fields.values()]).fetchone()

    def update(self, table: str, key_col: str, key, **fields) -> Tuple[Optional[dict], Optional[dict]]:
        """Change columns of one row; returns (snapshot before, snapshot after)."""
        before = self.snapshot(table, key_col, key)
        query = sql.SQL("UPDATE ops.{} SET {} WHERE {} = %s").format(
            sql.Identifier(table), sql.SQL(", ").join(sql.SQL("{} = %s").format(sql.Identifier(c)) for c in fields),
            sql.Identifier(key_col))
        self.conn.execute(query, [self._adapt(v) for v in fields.values()] + [key])
        return before, self.snapshot(table, key_col, key)

    def outbox(self, topic: str, payload: dict) -> None:
        """Queue a side effect; it is delivered only after this transaction commits."""
        self.conn.execute("INSERT INTO ops.outbox (topic, payload, correlation_id) VALUES (%s, %s, %s)",
                          (topic, _json(payload), self.correlation_id))


# ------------------------------------------------------------------------------------------------ registry

@dataclass(frozen=True)
class Action:
    name: str
    params: Type[BaseModel]
    roles: frozenset                         # roles allowed to run it at all; handlers add object-level rules
    handler: Callable[[ActionContext, Any], Outcome]
    description: str = ""
    agent_callable: bool = False             # may the AI agent's tool surface expose it?
    requires_human_confirmation: bool = False

    def json_schema(self) -> dict:
        return self.params.model_json_schema()


class ActionRegistry:
    def __init__(self, actions=()):
        self._actions: Dict[str, Action] = {}
        for a in actions:
            self.add(a)

    def add(self, action: Action) -> None:
        if action.name in self._actions:
            raise ValueError(f"action {action.name!r} is registered twice")
        self._actions[action.name] = action

    def get(self, name: str) -> Optional[Action]:
        return self._actions.get(name)

    def __iter__(self):
        return iter(self._actions.values())

    def __len__(self):
        return len(self._actions)


# ------------------------------------------------------------------------------------------------ the runner

def _summarise(error: ValidationError) -> str:
    parts = []
    for e in error.errors():
        where = ".".join(str(p) for p in e["loc"]) or "parameters"
        parts.append(f"{where}: {e['msg']}")
    return "; ".join(parts)


class ActionRunner:
    """Runs actions as the ``app_runner`` database role.

    ``connect`` returns a new connection as that role (for example ``lambda: dbconfig.connect("runner")``); the runner opens
    one per call and closes it, so it is safe to use from several threads.
    """

    def __init__(self, connect: Callable[[], Any], spec: Spec, registry: ActionRegistry,
                 config: Optional[RunnerConfig] = None, clock: Callable[[], datetime] = utcnow):
        self._connect = connect
        self.spec = spec
        self.definitions = definitions_from_spec(spec)
        self.registry = registry
        self.config = config or RunnerConfig()
        self.clock = clock

    def run(self, operator_id: str, action_name: str, params, *, correlation_id: Optional[uuid.UUID] = None,
            idempotency_key: Optional[str] = None) -> ActionResult:
        correlation_id = correlation_id or uuid.uuid4()
        raw = params.model_dump(mode="json") if isinstance(params, BaseModel) else dict(params)
        conn = self._connect()
        conn.row_factory = dict_row
        try:
            return self._run(conn, operator_id, action_name, raw, correlation_id, idempotency_key)
        finally:
            conn.close()

    # ------------------------------------------------------------------------------------------ steps
    def _run(self, conn, operator_id, action_name, raw, correlation_id, key) -> ActionResult:
        operator = self._load_operator(conn, operator_id)

        def refuse(error: ActionError, parameters=None):
            """Undo whatever the handler did, record the refusal, and raise."""
            conn.rollback()
            audit_id = self._audit(conn, operator, operator_id, action_name, error.outcome, parameters or raw, None,
                                   {"error": str(error)}, correlation_id, None)
            conn.commit()
            error.audit_id, error.action = audit_id, action_name
            raise error

        if operator is None:
            refuse(PermissionDenied(f"unknown operator {operator_id!r}"))
        action = self.registry.get(action_name)
        if action is None:
            refuse(InvalidAction(f"unknown action {action_name!r}"))
        if operator.role not in action.roles:
            refuse(PermissionDenied(f"role {operator.role} may not run '{action.name}' "
                                    f"(allowed: {', '.join(sorted(action.roles))})"))
        try:
            model = action.params.model_validate(raw)
        except ValidationError as exc:
            refuse(InvalidAction(_summarise(exc)))
        normalized = model.model_dump(mode="json")

        if key:
            replay = self._replay(conn, action.name, key, normalized)
            if replay == "MISMATCH":
                refuse(InvalidAction(f"idempotency key {key!r} was already used with different parameters"), normalized)
            if replay:
                conn.rollback()
                return replay

        ctx = ActionContext(conn, operator, self.clock(), self.spec, self.definitions, self.config, correlation_id)
        try:
            outcome = action.handler(ctx, model)
            audit_id = self._audit(conn, operator, operator_id, action.name, "OK", normalized, outcome.before,
                                   {**outcome.after, "_result": outcome.result, "_warnings": ctx.warnings},
                                   correlation_id, key)
            conn.commit()
        except ActionError as exc:
            refuse(exc, normalized)
        except pg_errors.UniqueViolation as exc:
            conn.rollback()
            if key and exc.diag.constraint_name == "audit_log_idempotency":       # two identical requests raced
                replay = self._replay(conn, action.name, key, normalized)
                conn.rollback()
                if isinstance(replay, ActionResult):
                    return replay
            refuse(ActionFailed(f"the database refused the change: {exc}"), normalized)
        except psycopg.Error as exc:
            refuse(ActionFailed(f"the database refused the change: {exc}"), normalized)
        except Exception as exc:
            conn.rollback()
            audit_id = self._audit(conn, operator, operator_id, action.name, "ERROR", normalized, None,
                                   {"error": f"{type(exc).__name__}: {exc}"}, correlation_id, None)
            conn.commit()
            raise
        return ActionResult(action.name, audit_id, outcome.result, tuple(ctx.warnings), correlation_id)

    @staticmethod
    def _load_operator(conn, operator_id) -> Optional[Operator]:
        row = conn.execute("SELECT operator_id, display_name, kind, role FROM ops.operator WHERE operator_id = %s",
                           (operator_id,)).fetchone()
        return Operator(**row) if row else None

    @staticmethod
    def _audit(conn, operator: Optional[Operator], operator_id, action, outcome, parameters, before, after,
               correlation_id, key) -> int:
        row = conn.execute(
            "INSERT INTO ops.audit_log (operator_id, operator_kind, action, outcome, parameters, before, after, "
            "correlation_id, idempotency_key) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING audit_id",
            (operator_id, operator.kind if operator else None, action, outcome, _json(parameters),
             _json(before) if before is not None else None, _json(after) if after is not None else None,
             correlation_id, key)).fetchone()
        return row["audit_id"]

    @staticmethod
    def _replay(conn, action, key, normalized):
        """The stored result of an earlier successful call with this key; "MISMATCH" if its parameters differ."""
        row = conn.execute("SELECT audit_id, parameters, after, correlation_id FROM ops.audit_log "
                           "WHERE action = %s AND idempotency_key = %s AND outcome = 'OK'", (action, key)).fetchone()
        if row is None:
            return None
        if row["parameters"] != normalized:
            return "MISMATCH"
        after = row["after"] or {}
        return ActionResult(action, row["audit_id"], after.get("_result", {}), tuple(after.get("_warnings", ())),
                            row["correlation_id"], replayed=True)
