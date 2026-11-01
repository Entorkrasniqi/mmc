"""Read-only routes: the objects of the ontology, the links between them, and time series (ontology.md sections 1, 2, 4, 9).

Every route needs a caller (any role may read; the roles matter for actions) and runs its queries as ``app_reader``.
Names follow the ontology and the action parameters: snake_case, ids as strings, times as ISO 8601 with a time zone.
Lists take ``limit`` (default 50, at most 500) and ``offset`` and come back as ``{"items": [...], "limit": n, "offset": n}``.
"""
from __future__ import annotations

import dataclasses
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple, get_args

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from ..ccsds import PacketError
from ..codec import decode_tc, encode_tc
from ..ontology.actions.records import EVENT_TYPES
from ..ontology.definitions import CommandDefinition, TelemetryPacketType, TelemetryParameter
from ..ontology.functions import estimate_time_to_safe, preflight_command
from . import store
from .auth import Principal, current_principal
from .context import AppContext, context_of

router = APIRouter(prefix="/api", dependencies=[Depends(current_principal)])

ALARM_STATES = ("ACTIVE", "ACKNOWLEDGED", "CLEARED")
COMMAND_STATUSES = ("PROPOSED", "APPROVED", "RELEASED", "SENT", "ACCEPTED", "REJECTED_ONBOARD", "VERIFIED", "FAILED",
                    "CANCELLED")
ANOMALY_STATUSES = ("OPEN", "INVESTIGATING", "RESOLVED")
CONTACT_STATUSES = ("PLANNED", "ACTIVE", "COMPLETED", "MISSED")
EVENT_TYPE_NAMES = get_args(EVENT_TYPES)


# ------------------------------------------------------------------------------------------------ helpers

def _csv(text: Optional[str], allowed: Sequence[str], name: str) -> List[str]:
    """``?status=ACTIVE,CLEARED`` -> ["ACTIVE", "CLEARED"]; a value that does not exist is a 422, not an empty answer."""
    values = [v.strip() for v in (text or "").split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown:
        raise HTTPException(422, f"{name}: unknown value {', '.join(map(repr, unknown))}; allowed: {', '.join(allowed)}")
    return values


def _aware(value: Optional[datetime], name: str) -> Optional[datetime]:
    if value is not None and value.tzinfo is None:
        raise HTTPException(422, f"{name} must include a time zone, for example 2026-11-01T12:00:00Z")
    return value


_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _ms(moment: datetime, round_up: bool = False) -> int:
    """Milliseconds since 1970 in exact integer arithmetic (a float timestamp can land one millisecond off).
    Samples sit on whole milliseconds, so the start of a window rounds up and the end rounds down."""
    whole, rest = divmod(moment - _EPOCH, timedelta(milliseconds=1))
    return whole + (1 if round_up and rest else 0)


def _page(items: list, limit: int, offset: int) -> Dict[str, Any]:
    return {"items": items, "limit": limit, "offset": offset}


def _found(row, what: str):
    if row is None:
        raise HTTPException(404, f"no such {what}")
    return row


def _sc(conn, spacecraft_id: str) -> dict:
    return _found(store.get_spacecraft(conn, spacecraft_id), f"spacecraft {spacecraft_id!r}")


Limit = Query(50, ge=1, le=store.MAX_PAGE)
Offset = Query(0, ge=0)


# ------------------------------------------------------------------------------------------------ who am I, who is there

@router.get("/me", tags=["operators"], summary="The calling operator, with role")
def me(principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    return dataclasses.asdict(principal)


@router.get("/operators", tags=["operators"], summary="Operators (display names only, unless you are a supervisor)")
def operators(request: Request, principal: Principal = Depends(current_principal)) -> Dict[str, Any]:
    with context_of(request).store.session() as conn:
        rows = store.list_operators(conn)
    return {"items": [store.operator_view(r, full=principal.role == "SUPERVISOR") for r in rows]}


# ------------------------------------------------------------------------------------------------ definitions (from the spec)

def _parameter(p: TelemetryParameter) -> dict:
    data = dataclasses.asdict(p)
    data["warning"], data["critical"] = store.bounds(p.warning), store.bounds(p.critical)
    data["enum_labels"] = [{"label": label, "value": value} for label, value in (p.enum_labels or ())] or None
    return data


def _command(c: CommandDefinition) -> dict:
    data = dataclasses.asdict(c)
    for argument in data["arguments"]:
        argument["enum_labels"] = [{"label": label, "value": value} for label, value in (argument["enum_labels"] or ())] or None
    return data


def _packet_type(defs, p: TelemetryPacketType) -> dict:
    data = dataclasses.asdict(p)
    data["parameters"] = [_parameter(x) for x in defs.packet_parameters(p.apid)]
    return data


@router.get("/definitions", tags=["definitions"], summary="Everything the specification defines")
def definitions(request: Request) -> Dict[str, Any]:
    defs = context_of(request).defs
    return {"mission_name": defs.mission_name, "packet_types": [_packet_type(defs, p) for p in defs.packet_types],
            "parameters": [_parameter(p) for p in defs.parameters], "commands": [_command(c) for c in defs.commands]}


@router.get("/definitions/parameters", tags=["definitions"])
def parameters(request: Request) -> Dict[str, Any]:
    return {"items": [_parameter(p) for p in context_of(request).defs.parameters]}


@router.get("/definitions/parameters/{name}", tags=["definitions"])
def parameter(name: str, request: Request) -> Dict[str, Any]:
    try:
        return _parameter(context_of(request).defs.parameter(name))
    except KeyError:
        raise HTTPException(404, f"no telemetry parameter named {name!r}") from None


@router.get("/definitions/packet-types", tags=["definitions"])
def packet_types(request: Request) -> Dict[str, Any]:
    defs = context_of(request).defs
    return {"items": [_packet_type(defs, p) for p in defs.packet_types]}


@router.get("/definitions/packet-types/{apid}", tags=["definitions"])
def packet_type(apid: int, request: Request) -> Dict[str, Any]:
    defs = context_of(request).defs
    try:
        return _packet_type(defs, defs.packet_type(apid))
    except KeyError:
        raise HTTPException(404, f"no telemetry packet type with APID {apid}") from None


@router.get("/definitions/commands", tags=["definitions"])
def commands_defined(request: Request) -> Dict[str, Any]:
    return {"items": [_command(c) for c in context_of(request).defs.commands]}


@router.get("/definitions/commands/{name}", tags=["definitions"])
def command_defined(name: str, request: Request) -> Dict[str, Any]:
    try:
        return _command(context_of(request).defs.command(name))
    except KeyError:
        raise HTTPException(404, f"no command named {name!r}") from None


@router.get("/ground-stations", tags=["contacts"])
def ground_stations(request: Request) -> Dict[str, Any]:
    with context_of(request).store.session() as conn:
        return {"items": store.list_stations(conn)}


# ------------------------------------------------------------------------------------------------ spacecraft and its links

def _spacecraft_view(ctx: AppContext, row: dict) -> dict:
    return store.spacecraft_view(ctx.spec, ctx.defs, row, ctx.clock(), ctx.runner.config.stale_factor)


@router.get("/spacecraft", tags=["spacecraft"], summary="All spacecraft with their newest state")
def spacecraft_list(request: Request) -> Dict[str, Any]:
    ctx = context_of(request)
    with ctx.store.session() as conn:
        return {"items": [_spacecraft_view(ctx, r) for r in store.list_spacecraft(conn)]}


@router.get("/spacecraft/{spacecraft_id}", tags=["spacecraft"],
            summary="One spacecraft: health, newest values read against their limits, age of the data")
def spacecraft_get(spacecraft_id: str, request: Request) -> Dict[str, Any]:
    ctx = context_of(request)
    with ctx.store.session() as conn:
        return _spacecraft_view(ctx, _sc(conn, spacecraft_id))


@router.get("/spacecraft/{spacecraft_id}/alarms", tags=["links"], summary="Alarms of a spacecraft, newest first")
def spacecraft_alarms(spacecraft_id: str, request: Request, state: Optional[str] = Query(None, description="comma separated"),
                      parameter: Optional[str] = None, since: Optional[datetime] = None, until: Optional[datetime] = None,
                      limit: int = Limit, offset: int = Offset) -> Dict[str, Any]:
    states = _csv(state, ALARM_STATES, "state")
    with context_of(request).store.session() as conn:
        _sc(conn, spacecraft_id)
        rows = store.list_alarms(conn, spacecraft_id, states, parameter, _aware(since, "since"), _aware(until, "until"),
                                 limit, offset)
    return _page(rows, limit, offset)


@router.get("/spacecraft/{spacecraft_id}/commands", tags=["links"],
            summary="Command executions of a spacecraft, newest first (with the contact each was released in)")
def spacecraft_commands(spacecraft_id: str, request: Request, status: Optional[str] = Query(None, description="comma separated"),
                        command: Optional[str] = None, since: Optional[datetime] = None, until: Optional[datetime] = None,
                        responds_to_alarm_id: Optional[uuid.UUID] = None, limit: int = Limit,
                        offset: int = Offset) -> Dict[str, Any]:
    statuses = _csv(status, COMMAND_STATUSES, "status")
    ctx = context_of(request)
    with ctx.store.session() as conn:
        _sc(conn, spacecraft_id)
        rows = store.list_commands(conn, ctx.defs, spacecraft_id, statuses, command, _aware(since, "since"),
                                   _aware(until, "until"), responds_to_alarm_id, limit, offset)
    return _page(rows, limit, offset)


@router.get("/spacecraft/{spacecraft_id}/events", tags=["links"], summary="Spacecraft events, newest first")
def spacecraft_events(spacecraft_id: str, request: Request, type: Optional[str] = Query(None, description="comma separated"),
                      since: Optional[datetime] = None, until: Optional[datetime] = None,
                      anomaly_id: Optional[uuid.UUID] = None, limit: int = Limit, offset: int = Offset) -> Dict[str, Any]:
    types = _csv(type, EVENT_TYPE_NAMES, "type")
    with context_of(request).store.session() as conn:
        _sc(conn, spacecraft_id)
        rows = store.list_events(conn, spacecraft_id, types, _aware(since, "since"), _aware(until, "until"), anomaly_id,
                                 limit, offset)
    return _page(rows, limit, offset)


@router.get("/spacecraft/{spacecraft_id}/anomalies", tags=["links"], summary="Anomalies of a spacecraft, newest first")
def spacecraft_anomalies(spacecraft_id: str, request: Request, status: Optional[str] = Query(None, description="comma separated"),
                         limit: int = Limit, offset: int = Offset) -> Dict[str, Any]:
    statuses = _csv(status, ANOMALY_STATUSES, "status")
    with context_of(request).store.session() as conn:
        _sc(conn, spacecraft_id)
        return _page(store.list_anomalies(conn, spacecraft_id, statuses, limit, offset), limit, offset)


@router.get("/spacecraft/{spacecraft_id}/contacts", tags=["links"],
            summary="Contact windows overlapping [since, until), oldest first, with the packets lost during each")
def spacecraft_contacts(spacecraft_id: str, request: Request, since: Optional[datetime] = None,
                        until: Optional[datetime] = None, status: Optional[str] = Query(None, description="comma separated"),
                        limit: int = Limit, offset: int = Offset) -> Dict[str, Any]:
    statuses = _csv(status, CONTACT_STATUSES, "status")
    with context_of(request).store.session() as conn:
        _sc(conn, spacecraft_id)
        rows = store.list_contacts(conn, spacecraft_id, _aware(since, "since"), _aware(until, "until"), statuses, limit, offset)
    return _page(rows, limit, offset)


@router.get("/spacecraft/{spacecraft_id}/packet-loss", tags=["links"],
            summary="Telemetry packets lost between two instants (from sequence-counter gaps)")
def spacecraft_packet_loss(spacecraft_id: str, request: Request, since: datetime = Query(..., alias="from"),
                           until: datetime = Query(..., alias="to")) -> Dict[str, Any]:
    since, until = _aware(since, "from"), _aware(until, "to")
    if until <= since:
        raise HTTPException(422, "'to' must be after 'from'")
    with context_of(request).store.session() as conn:
        _sc(conn, spacecraft_id)
        return {"spacecraft_id": spacecraft_id, "from": since, "to": until, **store.packet_loss(conn, spacecraft_id, since, until)}


@router.get("/spacecraft/{spacecraft_id}/series/{parameter}", tags=["series"],
            summary="A telemetry parameter over time (spacecraft time), thinned to at most max_points")
def spacecraft_series(spacecraft_id: str, parameter: str, request: Request, since: Optional[datetime] = Query(None, alias="from"),
                      until: Optional[datetime] = Query(None, alias="to"),
                      window_s: float = Query(3600.0, gt=0, le=30 * 86400, description="used when 'from' is omitted"),
                      max_points: int = Query(600, ge=2, le=5000)) -> Dict[str, Any]:
    """Without 'to' the series ends at its newest sample; without 'from' it starts ``window_s`` seconds earlier. The
    answer also carries the parameter's definition, so a chart can draw the warning and critical bands."""
    ctx = context_of(request)
    try:
        definition = ctx.defs.parameter(parameter)
    except KeyError:
        raise HTTPException(404, f"no telemetry parameter named {parameter!r}") from None
    since, until = _aware(since, "from"), _aware(until, "to")
    with ctx.store.session() as conn:
        _sc(conn, spacecraft_id)
        to_ms = _ms(until) if until else store.newest_sample_ms(conn, spacecraft_id, parameter)
        if to_ms is None:
            result: Dict[str, Any] = {"resolution": "raw", "bucket_ms": None, "samples": 0, "points": []}
            from_ms = to_ms = None
        else:
            from_ms = _ms(since, round_up=True) if since else to_ms - int(window_s * 1000)
            if to_ms < from_ms:
                raise HTTPException(422, "'to' must not be before 'from'")
            result = store.series(conn, spacecraft_id, parameter, from_ms, to_ms, max_points)
    return {"spacecraft_id": spacecraft_id, "parameter": _parameter(definition),
            "from": store.iso_ms(from_ms) if from_ms is not None else None,
            "to": store.iso_ms(to_ms) if to_ms is not None else None, **result}


# ------------------------------------------------------------------------------------------------ single objects

@router.get("/alarms/{alarm_id}", tags=["objects"], summary="An alarm and the commands sent in response to it")
def alarm_get(alarm_id: uuid.UUID, request: Request) -> Dict[str, Any]:
    with context_of(request).store.session() as conn:
        return _found(store.get_alarm(conn, alarm_id), "alarm")


@router.get("/command-executions/{execution_id}", tags=["objects"],
            summary="A command execution with everything an approver and a reviewer need")
def command_get(execution_id: uuid.UUID, request: Request) -> Dict[str, Any]:
    ctx = context_of(request)
    with ctx.store.session() as conn:
        return _found(store.get_command(conn, ctx.defs, execution_id), "command execution")


@router.get("/anomalies/{anomaly_id}", tags=["objects"], summary="An anomaly with its alarms, events and commands")
def anomaly_get(anomaly_id: uuid.UUID, request: Request) -> Dict[str, Any]:
    ctx = context_of(request)
    with ctx.store.session() as conn:
        return _found(store.get_anomaly(conn, ctx.defs, anomaly_id), "anomaly")


@router.get("/contacts/{contact_id}", tags=["objects"], summary="A contact window, the packets lost during it, its commands")
def contact_get(contact_id: uuid.UUID, request: Request) -> Dict[str, Any]:
    with context_of(request).store.session() as conn:
        return _found(store.get_contact(conn, contact_id), "contact window")


# ------------------------------------------------------------------------------------------------ functions (no side effects)

class _FunctionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spacecraft_id: str


class PreflightRequest(_FunctionRequest):
    command: str
    arguments: Dict[str, Any] = Field(default_factory=dict, description="enum arguments accept labels, like Propose Command")


class TimeToSafeRequest(_FunctionRequest):
    command: Optional[str] = Field(None, description="'if I send this now': leave out for the state as it is")
    arguments: Dict[str, Any] = Field(default_factory=dict)
    horizon_hours: float = Field(6.0, gt=0, le=48)


def _checked_arguments(ctx: AppContext, command: str, arguments: Dict[str, Any]) -> Tuple[str, dict]:
    """The same check and normalisation as Propose Command, so a preflight judges what a proposal would carry."""
    try:
        definition = ctx.spec.command_by_name(command)
    except KeyError:
        raise HTTPException(422, f"unknown command {command!r}; known: {', '.join(c.name for c in ctx.spec.commands)}") from None
    try:
        packet = encode_tc(ctx.spec, definition.name, arguments, validate=True)
        _, args, _ = decode_tc(ctx.spec, packet)
    except (PacketError, TypeError, ValueError, OverflowError) as exc:
        raise HTTPException(422, str(exc)) from None
    return definition.name, args


@router.post("/functions/preflight-command", tags=["functions"],
             summary="Would the spacecraft accept this command if it arrived now? (changes nothing, is not audited)")
def preflight(body: PreflightRequest, request: Request) -> Dict[str, Any]:
    ctx = context_of(request)
    name, args = _checked_arguments(ctx, body.command, body.arguments)
    with ctx.store.session() as conn:
        sc = _sc(conn, body.spacecraft_id)
    result = preflight_command(ctx.spec, sc["latest_values"], name, args, last_contact_at=sc["last_contact_at"],
                               now=ctx.clock(), stale_factor=ctx.runner.config.stale_factor)
    return {"spacecraft_id": body.spacecraft_id, "command": name, "arguments": args, **result.to_dict()}


@router.post("/functions/estimate-time-to-safe", tags=["functions"],
             summary="When would the battery reach the FDIR limit, optionally after a command? (changes nothing)")
def time_to_safe(body: TimeToSafeRequest, request: Request) -> Dict[str, Any]:
    ctx = context_of(request)
    name = args = None
    if body.command is not None:
        name, args = _checked_arguments(ctx, body.command, body.arguments)
    with ctx.store.session() as conn:
        sc = _sc(conn, body.spacecraft_id)
        eclipse = store.eclipse_context(conn, body.spacecraft_id)
    verdict = None
    if name is not None:
        verdict = preflight_command(ctx.spec, sc["latest_values"], name, args, last_contact_at=sc["last_contact_at"],
                                    now=ctx.clock(), stale_factor=ctx.runner.config.stale_factor).to_dict()
    estimate = estimate_time_to_safe(ctx.spec, sc["latest_values"], command_name=name, args=args,
                                     eclipse_transition=eclipse[1] if eclipse else None,
                                     horizon_s=body.horizon_hours * 3600.0)
    return {"spacecraft_id": body.spacecraft_id, "command": name, "arguments": args, "preflight": verdict,
            "time_to_safe": estimate.to_dict()}
