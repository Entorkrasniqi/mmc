"""The command lifecycle (protocols/command-safety-protocol.md):

    PROPOSED -> APPROVED -> RELEASED -> SENT -> ACCEPTED -> VERIFIED
                                              |-> REJECTED_ONBOARD / FAILED          (ACCEPTED -> FAILED too)
    PROPOSED / APPROVED -> CANCELLED

People and agents run Propose, Approve, Release and Cancel. Recording that the bytes were sent and what became of them is
done by the SYSTEM operator (the outbox worker and the automations), never by a person.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field

from ...ccsds import PacketError
from ...codec import decode_tc, encode_tc
from ..functions import expected_effect, preflight_command
from ..runner import Action, ActionContext, Outcome

IN_FLIGHT = ("RELEASED", "SENT", "ACCEPTED")
OPEN_STATES = ("PROPOSED", "APPROVED") + IN_FLIGHT

# which outcomes the system may record, from which status
OUTCOME_FROM = {"ACCEPTED": ("SENT",), "REJECTED_ONBOARD": ("SENT",), "FAILED": ("SENT", "ACCEPTED"),
                "VERIFIED": ("ACCEPTED",)}


class _Params(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProposeCommandParams(_Params):
    spacecraft_id: str
    command: str = Field(description="command name, e.g. SetMode")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="argument values; enum arguments accept labels")
    reason: str = Field(description="why this command is being proposed")
    responds_to_alarm_id: Optional[uuid.UUID] = None


class ApproveCommandParams(_Params):
    execution_id: uuid.UUID
    note: Optional[str] = None


class ReleaseCommandParams(_Params):
    execution_id: uuid.UUID
    override_reason: Optional[str] = Field(default=None, description="supervisors only: release without a contact window")


class CancelCommandParams(_Params):
    execution_id: uuid.UUID
    reason: str


class RecordCommandSentParams(_Params):
    execution_id: uuid.UUID
    outbox_id: Optional[int] = None


class RecordCommandOutcomeParams(_Params):
    execution_id: uuid.UUID
    outcome: Literal["ACCEPTED", "REJECTED_ONBOARD", "VERIFIED", "FAILED"]
    reason: Optional[str] = None


def _blank(text: Optional[str]) -> bool:
    return text is None or not text.strip()


def _spacecraft(ctx: ActionContext, spacecraft_id: str) -> dict:
    row = ctx.one("SELECT * FROM ops.spacecraft WHERE spacecraft_id = %s", (spacecraft_id,))
    if row is None:
        ctx.invalid(f"unknown spacecraft {spacecraft_id!r}")
    return row


def _preflight(ctx: ActionContext, sc: dict, command_name: str, args: dict):
    return preflight_command(ctx.spec, sc["latest_values"], command_name, args, last_contact_at=sc["last_contact_at"],
                             now=ctx.now, stale_factor=ctx.config.stale_factor)


def _warn_about(ctx: ActionContext, pre) -> None:
    if not pre.known:
        ctx.warn("no telemetry received yet, so the command could not be checked against the spacecraft state")
    elif pre.predicts_rejection:
        ctx.warn(f"the spacecraft is predicted to REJECT this command: {pre.reason}")
    elif pre.stale:
        ctx.warn(f"the newest telemetry is {pre.state_age_s:.0f} s old; the check may not reflect the spacecraft now")


# ------------------------------------------------------------------------------------------------ people's actions

def propose_command(ctx: ActionContext, p: ProposeCommandParams) -> Outcome:
    sc = _spacecraft(ctx, p.spacecraft_id)
    try:
        cmd = ctx.spec.command_by_name(p.command)
    except KeyError:
        ctx.invalid(f"unknown command {p.command!r}; known: {', '.join(c.name for c in ctx.spec.commands)}")
    if _blank(p.reason):
        ctx.invalid("a reason is required")
    try:                                    # the same checks and bytes as a careful ground system would use
        packet = encode_tc(ctx.spec, cmd.name, p.arguments, validate=True)
        _, args, _ = decode_tc(ctx.spec, packet)
    except (PacketError, TypeError, ValueError, OverflowError) as exc:
        ctx.invalid(str(exc))
    clash = ctx.one("SELECT execution_id, status FROM ops.command_execution WHERE spacecraft_id = %s "
                    "AND command_id = %s AND status = ANY(%s)", (p.spacecraft_id, cmd.id, list(OPEN_STATES)))
    if clash:
        ctx.invalid(f"{cmd.name} already has an open execution ({clash['execution_id']}, {clash['status']})")
    if p.responds_to_alarm_id is not None:
        alarm = ctx.one("SELECT spacecraft_id FROM ops.alarm WHERE alarm_id = %s", (p.responds_to_alarm_id,))
        if alarm is None or alarm["spacecraft_id"] != p.spacecraft_id:
            ctx.invalid(f"alarm {p.responds_to_alarm_id} does not exist for {p.spacecraft_id}")

    pre = _preflight(ctx, sc, cmd.name, args)
    vital = cmd.significance == "vital"
    row = ctx.insert(
        "command_execution", spacecraft_id=p.spacecraft_id, command_id=cmd.id, command_name=cmd.name, vital=vital,
        arguments=args, reason=p.reason.strip(), proposed_by=ctx.operator.operator_id,
        responds_to_alarm_id=p.responds_to_alarm_id, raw_bytes_hex=packet.hex(), proposed_at=ctx.now,
        expires_at=ctx.now + ctx.config.proposal_ttl, preflight=pre.to_dict(), state_snapshot=sc["latest_values"],
        expected_effect=expected_effect(ctx.spec, cmd.name, args))
    _warn_about(ctx, pre)
    if vital:
        ctx.warn("this is a VITAL command: a supervisor other than the proposer must approve it")
    eid = row["execution_id"]
    return Outcome({"execution_id": str(eid), "status": "PROPOSED", "vital": vital, "arguments": args,
                    "raw_bytes_hex": packet.hex(), "preflight": pre.to_dict(), "expires_at": row["expires_at"].isoformat()},
                   after={f"command_execution:{eid}": ctx.snapshot("command_execution", "execution_id", eid)})


def approve_command(ctx: ActionContext, p: ApproveCommandParams) -> Outcome:
    row = ctx.lock("command_execution", "execution_id", p.execution_id, "command execution")
    if row["status"] != "PROPOSED":
        ctx.invalid(f"only a PROPOSED command can be approved; this one is {row['status']}")
    if ctx.now >= row["expires_at"]:
        ctx.invalid(f"the proposal expired at {row['expires_at'].isoformat()}; propose it again")
    op = ctx.operator
    if row["vital"]:
        if op.role != "SUPERVISOR":
            ctx.deny("a VITAL command must be approved by a supervisor")
        if op.operator_id == row["proposed_by"]:
            ctx.deny("two-person rule: a vital command cannot be approved by the person who proposed it")
    sc = _spacecraft(ctx, row["spacecraft_id"])
    args = row["arguments"]
    pre = _preflight(ctx, sc, row["command_name"], args)           # the state may have changed since the proposal
    if pre.predicts_rejection:
        if op.role != "SUPERVISOR" or _blank(p.note):
            ctx.invalid(f"the spacecraft is predicted to REJECT this command ({pre.reason}); only a supervisor may "
                        f"approve it anyway, and only with a written note")
    _warn_about(ctx, pre)
    key = row["execution_id"]
    before, after = ctx.update("command_execution", "execution_id", key, status="APPROVED",
                               approved_by=op.operator_id, approved_at=ctx.now, approval_note=p.note,
                               preflight=pre.to_dict())
    return Outcome({"execution_id": str(key), "status": "APPROVED", "preflight": pre.to_dict()},
                   {f"command_execution:{key}": before}, {f"command_execution:{key}": after})


def release_command(ctx: ActionContext, p: ReleaseCommandParams) -> Outcome:
    row = ctx.lock("command_execution", "execution_id", p.execution_id, "command execution")
    if row["status"] != "APPROVED":
        ctx.invalid(f"only an APPROVED command can be released; this one is {row['status']}")
    if ctx.now >= row["expires_at"]:
        ctx.invalid(f"the approval expired at {row['expires_at'].isoformat()}; propose the command again")
    busy = ctx.one("SELECT execution_id, command_name, status FROM ops.command_execution WHERE spacecraft_id = %s "
                   "AND status = ANY(%s) AND execution_id <> %s", (row["spacecraft_id"], list(IN_FLIGHT), p.execution_id))
    if busy:
        # telemetry reports counters, not which command they belong to: one command at a time keeps verification sound
        ctx.invalid(f"{busy['command_name']} ({busy['execution_id']}) is still in flight ({busy['status']}); "
                    f"wait until it is verified, rejected or failed")
    contact = ctx.one("SELECT contact_id FROM ops.contact_window WHERE spacecraft_id = %s "
                      "AND status IN ('PLANNED', 'ACTIVE') AND start_at <= %s AND end_at > %s ORDER BY start_at LIMIT 1",
                      (row["spacecraft_id"], ctx.now, ctx.now))
    override = None
    if contact is None and ctx.config.require_contact:
        if _blank(p.override_reason):
            ctx.invalid("there is no contact window with the spacecraft right now; a supervisor may release anyway "
                        "with an override_reason")
        if ctx.operator.role != "SUPERVISOR":
            ctx.deny("only a supervisor may release a command without a contact window")
        override = p.override_reason.strip()
        ctx.warn(f"released without a contact window (override: {override})")
    key = row["execution_id"]
    before, after = ctx.update("command_execution", "execution_id", key, status="RELEASED", released_at=ctx.now,
                               contact_id=contact["contact_id"] if contact else None, override_reason=override)
    ctx.outbox("send_telecommand", {"execution_id": str(key), "spacecraft_id": row["spacecraft_id"],
                                    "command": row["command_name"], "raw_bytes_hex": row["raw_bytes_hex"]})
    return Outcome({"execution_id": str(key), "status": "RELEASED"},
                   {f"command_execution:{key}": before}, {f"command_execution:{key}": after})


def cancel_command(ctx: ActionContext, p: CancelCommandParams) -> Outcome:
    row = ctx.lock("command_execution", "execution_id", p.execution_id, "command execution")
    if row["status"] not in ("PROPOSED", "APPROVED"):
        ctx.invalid(f"a command can be cancelled only before it is released; this one is {row['status']}")
    if _blank(p.reason):
        ctx.invalid("a reason is required")
    op = ctx.operator
    own = op.operator_id == row["proposed_by"]
    expired_sweep = op.role == "SYSTEM" and ctx.now >= row["expires_at"]
    if op.role in ("AGENT", "SYSTEM") and not own and not expired_sweep:
        ctx.deny("an agent or the system may cancel only its own proposals (or, for the system, expired ones)")
    key = row["execution_id"]
    before, after = ctx.update("command_execution", "execution_id", key, status="CANCELLED",
                               cancelled_by=op.operator_id, cancel_reason=p.reason.strip())
    return Outcome({"execution_id": str(key), "status": "CANCELLED"},
                   {f"command_execution:{key}": before}, {f"command_execution:{key}": after})


# ------------------------------------------------------------------------------------------------ the system's actions

def record_command_sent(ctx: ActionContext, p: RecordCommandSentParams) -> Outcome:
    row = ctx.lock("command_execution", "execution_id", p.execution_id, "command execution")
    if row["status"] != "RELEASED":
        ctx.invalid(f"only a RELEASED command can be marked as sent; this one is {row['status']}")
    sc = _spacecraft(ctx, row["spacecraft_id"])
    key = row["execution_id"]
    before, after = ctx.update("command_execution", "execution_id", key, status="SENT", sent_at=ctx.now,
                               send_baseline=sc["latest_values"])
    if p.outbox_id is not None:
        ctx.conn.execute("UPDATE ops.outbox SET processed_at = %s, attempts = attempts + 1 WHERE outbox_id = %s "
                         "AND processed_at IS NULL", (ctx.now, p.outbox_id))
    return Outcome({"execution_id": str(key), "status": "SENT"},
                   {f"command_execution:{key}": before}, {f"command_execution:{key}": after})


def record_command_outcome(ctx: ActionContext, p: RecordCommandOutcomeParams) -> Outcome:
    row = ctx.lock("command_execution", "execution_id", p.execution_id, "command execution")
    if row["status"] not in OUTCOME_FROM[p.outcome]:
        ctx.invalid(f"{p.outcome} cannot follow {row['status']}")
    if p.outcome in ("REJECTED_ONBOARD", "FAILED") and _blank(p.reason):
        ctx.invalid(f"{p.outcome} needs a reason")
    fields: Dict[str, Any] = {"status": p.outcome}
    if p.outcome == "VERIFIED":
        fields["verified_at"] = ctx.now
    if p.reason:
        fields["rejection_reason"] = p.reason.strip()            # also holds the reason for FAILED
    key = row["execution_id"]
    before, after = ctx.update("command_execution", "execution_id", key, **fields)
    return Outcome({"execution_id": str(key), "status": p.outcome},
                   {f"command_execution:{key}": before}, {f"command_execution:{key}": after})


PEOPLE = frozenset({"OPERATOR", "SUPERVISOR"})
PROPOSERS = frozenset({"OPERATOR", "SUPERVISOR", "AGENT", "SYSTEM"})

ACTIONS = (
    Action("Propose Command", ProposeCommandParams, PROPOSERS, propose_command,
           "Propose a telecommand; nothing is sent until a person approves and releases it.", agent_callable=True),
    Action("Approve Command", ApproveCommandParams, PEOPLE, approve_command,
           "Approve a proposed command (vital commands: a supervisor other than the proposer)."),
    Action("Release Command", ReleaseCommandParams, PEOPLE, release_command,
           "Release an approved command to the link during a contact window."),
    Action("Cancel Command", CancelCommandParams, PROPOSERS, cancel_command,
           "Cancel a command before it is released.", agent_callable=True),
    Action("Record Command Sent", RecordCommandSentParams, frozenset({"SYSTEM"}), record_command_sent,
           "The outbox worker is about to put the bytes on the link."),
    Action("Record Command Outcome", RecordCommandOutcomeParams, frozenset({"SYSTEM"}), record_command_outcome,
           "What the telemetry showed became of a sent command."),
)
