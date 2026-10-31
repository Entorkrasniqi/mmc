"""Loading and validating the mission specification (spec/minisat.yaml).

The specification is plain YAML so a human can read and edit it. This module turns it into typed Python
objects and, more importantly, REFUSES a specification that does not make sense (duplicate names, an enum value
that does not fit in its field, overlapping limits ...) with an error message that says where the problem is.
Catching these mistakes here is far cheaper than debugging a garbled packet later.
"""
from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

__all__ = ["SpecError", "ScalarType", "SCALARS", "Limits", "Field", "TmPacketSpec", "CommandSpec", "Spec",
           "load_spec", "parse_spec"]


class SpecError(ValueError):
    """The mission specification is invalid. The message names the offending place."""


@dataclass(frozen=True)
class ScalarType:
    """A fixed-size number as it appears on the wire.

    ``fmt`` is the format character of Python's :mod:`struct` module; the ``>`` (big-endian) prefix is added
    when packing. ``kind`` is ``"uint"``, ``"int"`` or ``"float"``.
    """
    name: str
    fmt: str
    size: int          # bytes
    kind: str

    @property
    def bits(self) -> int:
        return self.size * 8

    def contains(self, value: int) -> bool:
        """Does this integer type have room for ``value``? (Always False for float types.)"""
        if self.kind == "uint":
            return 0 <= value < 2 ** self.bits
        if self.kind == "int":
            return -(2 ** (self.bits - 1)) <= value < 2 ** (self.bits - 1)
        return False


SCALARS = {t.name: t for t in (
    ScalarType("uint8", "B", 1, "uint"), ScalarType("uint16", "H", 2, "uint"),
    ScalarType("uint32", "I", 4, "uint"), ScalarType("uint64", "Q", 8, "uint"),
    ScalarType("int8", "b", 1, "int"), ScalarType("int16", "h", 2, "int"),
    ScalarType("int32", "i", 4, "int"), ScalarType("int64", "q", 8, "int"),
    ScalarType("float32", "f", 4, "float"), ScalarType("float64", "d", 8, "float"),
)}
# sanity check of the table against the struct module (cheap, and catches typos in the table)
for _t in SCALARS.values():
    assert struct.calcsize(">" + _t.fmt) == _t.size, _t


@dataclass(frozen=True)
class Limits:
    """Alarm limits of a telemetry value. Each is ``(minimum, maximum)``; ``None`` means "no limit on that side".

    The values are the range that is still FINE: outside ``warning`` a yellow alarm is raised, outside ``critical``
    a red one (this is how XTCE and Yamcs define them).
    """
    warning: Optional[tuple]
    critical: Optional[tuple]


@dataclass(frozen=True)
class Field:
    """One value inside a telemetry packet, or one argument of a telecommand."""
    name: str
    type: ScalarType
    description: str = ""
    unit: Optional[str] = None
    enum: Optional[str] = None                # name of an entry in Spec.enums
    limits: Optional[Limits] = None           # telemetry only
    range: Optional[tuple] = None             # telecommand arguments only: allowed (min, max)


@dataclass(frozen=True)
class TmPacketSpec:
    name: str
    apid: int
    period_s: float
    description: str
    fields: tuple

    @property
    def data_size(self) -> int:
        """Bytes after the primary header: 8 (spacecraft time) + the fields."""
        return 8 + sum(f.type.size for f in self.fields)


@dataclass(frozen=True)
class CommandSpec:
    name: str
    id: int
    description: str
    args: tuple
    significance: Optional[str] = None        # None or "vital" ...

    @property
    def data_size(self) -> int:
        """Bytes after the primary header: 2 (command id) + the arguments."""
        return 2 + sum(a.type.size for a in self.args)


@dataclass(frozen=True)
class Spec:
    mission_name: str
    description: str
    tm_port: int
    tc_port: int
    tc_apid: int
    enums: dict = field(default_factory=dict)          # name -> {label: value}
    tm_packets: tuple = ()
    commands: tuple = ()

    def tm_by_name(self, name: str) -> TmPacketSpec:
        for p in self.tm_packets:
            if p.name == name:
                return p
        raise KeyError(f"no telemetry packet named {name!r}")

    def tm_by_apid(self, apid: int) -> Optional[TmPacketSpec]:
        return next((p for p in self.tm_packets if p.apid == apid), None)

    def command_by_name(self, name: str) -> CommandSpec:
        for c in self.commands:
            if c.name == name:
                return c
        raise KeyError(f"no command named {name!r}")

    def command_by_id(self, cmd_id: int) -> Optional[CommandSpec]:
        return next((c for c in self.commands if c.id == cmd_id), None)

    def all_tm_fields(self):
        for p in self.tm_packets:
            yield from p.fields


# ------------------------------------------------------------------------------------------------ parsing

_IDENT = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
_RESERVED = {"sc_time_ms"}          # names used by the packet framing itself


def load_spec(path) -> Spec:
    """Read and validate a specification file."""
    text = Path(path).read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise SpecError(f"{path}: not valid YAML: {exc}") from exc
    return parse_spec(data, source=str(path))


def parse_spec(data, source: str = "<spec>") -> Spec:
    """Validate an already-loaded YAML document (a dict) and build a :class:`Spec`."""
    def fail(where: str, msg: str):
        raise SpecError(f"{source}: {where}: {msg}")

    if not isinstance(data, dict):
        fail("top level", "expected a mapping")
    for key in ("mission", "links", "enums", "telemetry", "telecommand"):
        if key not in data:
            fail("top level", f"missing section '{key}'")

    mission = data["mission"] or {}
    mission_name = mission.get("name")
    if not isinstance(mission_name, str) or not _IDENT.match(mission_name):
        fail("mission.name", "must be an identifier (letters, digits, underscore; starts with a letter)")

    links = data["links"] or {}
    ports = {}
    for key in ("tm_udp_port", "tc_udp_port"):
        port = links.get(key)
        if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
            fail(f"links.{key}", "must be an integer between 1 and 65535")
        ports[key] = port
    if ports["tm_udp_port"] == ports["tc_udp_port"]:
        fail("links", "telemetry and telecommand ports must differ")

    enums = {}
    for ename, values in (data["enums"] or {}).items():
        if not _IDENT.match(str(ename)):
            fail(f"enums.{ename}", "enum name must be an identifier")
        if not isinstance(values, dict) or not values:
            fail(f"enums.{ename}", "expected a non-empty mapping label -> integer")
        seen_values = set()
        for label, value in values.items():
            if isinstance(label, bool):
                fail(f"enums.{ename}", f"a label was read as the boolean {label}: YAML turns unquoted "
                                       "ON/OFF/YES/NO/TRUE/FALSE into booleans - put the label in quotes")
            if not _IDENT.match(str(label)):
                fail(f"enums.{ename}.{label}", "label must be an identifier")
            if not isinstance(value, int) or isinstance(value, bool) or value < 0:
                fail(f"enums.{ename}.{label}", "value must be a non-negative integer")
            if value in seen_values:
                fail(f"enums.{ename}", f"value {value} is used twice")
            seen_values.add(value)
        enums[str(ename)] = {str(k): int(v) for k, v in values.items()}

    def parse_field(raw, where: str, telemetry: bool) -> Field:
        if not isinstance(raw, dict):
            fail(where, "expected a mapping")
        name = raw.get("name")
        if not isinstance(name, str) or not _IDENT.match(name):
            fail(where, "'name' must be an identifier")
        where = f"{where}[{name}]"
        if name in _RESERVED:
            fail(where, f"'{name}' is reserved for the packet framing")
        tname = raw.get("type")
        if tname not in SCALARS:
            fail(where, f"unknown type {tname!r} (known: {', '.join(SCALARS)})")
        ftype = SCALARS[tname]
        enum = raw.get("enum")
        if enum is not None:
            if enum not in enums:
                fail(where, f"unknown enum {enum!r}")
            if ftype.kind == "float":
                fail(where, "an enum field must have an integer type")
            for label, value in enums[enum].items():
                if not ftype.contains(value):
                    fail(where, f"enum value {label}={value} does not fit in {tname}")
        unit = raw.get("unit")
        if unit is not None and not isinstance(unit, str):
            fail(where, "'unit' must be a string")
        limits = None
        if "limits" in raw:
            if not telemetry:
                fail(where, "'limits' only make sense for telemetry")
            limits = _parse_limits(raw["limits"], where, fail)
        rng = None
        if "range" in raw:
            if telemetry:
                fail(where, "'range' only makes sense for telecommand arguments")
            rng = _parse_pair(raw["range"], f"{where}.range", fail, allow_open=False)
        return Field(name=name, type=ftype, description=str(raw.get("description", "")), unit=unit, enum=enum,
                     limits=limits, range=rng)

    # ---- telemetry
    tm_section = data["telemetry"] or {}
    packets = []
    used_names = set()
    used_apids = set()
    for i, raw in enumerate(tm_section.get("packets") or []):
        where = f"telemetry.packets[{i}]"
        if not isinstance(raw, dict):
            fail(where, "expected a mapping")
        pname = raw.get("name")
        if not isinstance(pname, str) or not _IDENT.match(pname):
            fail(where, "'name' must be an identifier")
        where = f"telemetry.packets[{pname}]"
        apid = raw.get("apid")
        if not isinstance(apid, int) or isinstance(apid, bool) or not 0 <= apid <= 2039:
            fail(where, "'apid' must be an integer 0..2039 (2040-2047 are reserved by CCSDS)")
        if apid in used_apids:
            fail(where, f"apid {apid} is already used by another packet")
        used_apids.add(apid)
        period = raw.get("period_s")
        if not isinstance(period, (int, float)) or isinstance(period, bool) or period <= 0:
            fail(where, "'period_s' must be a positive number")
        fields = []
        for j, rf in enumerate(raw.get("fields") or []):
            f = parse_field(rf, f"{where}.fields[{j}]", telemetry=True)
            if f.name in used_names:
                fail(f"{where}.fields[{f.name}]", "telemetry field names must be unique across ALL packets "
                                                  "(they become Yamcs parameter names)")
            used_names.add(f.name)
            fields.append(f)
        if not fields:
            fail(where, "a packet needs at least one field")
        pkt = TmPacketSpec(pname, apid, float(period), str(raw.get("description", "")), tuple(fields))
        if pkt.data_size > 65536:
            fail(where, "packet too large for the CCSDS length field")
        packets.append(pkt)
    if not packets:
        fail("telemetry.packets", "at least one packet is required")
    if len({p.name for p in packets}) != len(packets):
        fail("telemetry.packets", "packet names must be unique")

    # ---- telecommands
    tc_section = data["telecommand"] or {}
    tc_apid = tc_section.get("apid")
    if not isinstance(tc_apid, int) or isinstance(tc_apid, bool) or not 0 <= tc_apid <= 2039:
        fail("telecommand.apid", "must be an integer 0..2039")
    if tc_apid in used_apids:
        fail("telecommand.apid", f"apid {tc_apid} is already used by a telemetry packet")
    commands = []
    used_ids = set()
    for i, raw in enumerate(tc_section.get("commands") or []):
        where = f"telecommand.commands[{i}]"
        if not isinstance(raw, dict):
            fail(where, "expected a mapping")
        cname = raw.get("name")
        if not isinstance(cname, str) or not _IDENT.match(cname):
            fail(where, "'name' must be an identifier")
        where = f"telecommand.commands[{cname}]"
        cid = raw.get("id")
        if not isinstance(cid, int) or isinstance(cid, bool) or not 1 <= cid <= 65535:
            fail(where, "'id' must be an integer 1..65535 (0 is reserved for 'no command')")
        if cid in used_ids:
            fail(where, f"command id {cid} is used twice")
        used_ids.add(cid)
        significance = raw.get("significance")
        if significance not in (None, "vital"):
            fail(where, "'significance' must be omitted or 'vital'")
        args = []
        for j, ra in enumerate(raw.get("args") or []):
            a = parse_field(ra, f"{where}.args[{j}]", telemetry=False)
            if any(a.name == b.name for b in args):
                fail(f"{where}.args[{a.name}]", "argument names must be unique within a command")
            args.append(a)
        commands.append(CommandSpec(cname, cid, str(raw.get("description", "")), tuple(args), significance))
    if not commands:
        fail("telecommand.commands", "at least one command is required")
    if len({c.name for c in commands}) != len(commands):
        fail("telecommand.commands", "command names must be unique")

    return Spec(mission_name=mission_name, description=str(mission.get("description", "")),
                tm_port=ports["tm_udp_port"], tc_port=ports["tc_udp_port"], tc_apid=tc_apid, enums=enums,
                tm_packets=tuple(packets), commands=tuple(commands))


def _parse_pair(raw, where, fail, allow_open: bool):
    if not isinstance(raw, (list, tuple)) or len(raw) != 2:
        fail(where, "expected [minimum, maximum]")
    lo, hi = raw
    for v in (lo, hi):
        if v is None:
            if not allow_open:
                fail(where, "both ends are required")
        elif not isinstance(v, (int, float)) or isinstance(v, bool):
            fail(where, "limits must be numbers (or null for 'no limit')")
    if lo is None and hi is None:
        fail(where, "at least one end must be given")
    if lo is not None and hi is not None and lo >= hi:
        fail(where, "minimum must be smaller than maximum")
    return (lo, hi)


def _parse_limits(raw, where, fail) -> Limits:
    if not isinstance(raw, dict) or not set(raw) <= {"warning", "critical"} or not raw:
        fail(f"{where}.limits", "expected a mapping with 'warning' and/or 'critical'")
    warning = _parse_pair(raw["warning"], f"{where}.limits.warning", fail, True) if "warning" in raw else None
    critical = _parse_pair(raw["critical"], f"{where}.limits.critical", fail, True) if "critical" in raw else None
    if warning and critical:
        # the critical range must be at least as wide as the warning range
        for side, (w, c) in enumerate(zip(warning, critical)):
            if w is None and c is not None:
                fail(f"{where}.limits", "critical has a limit where warning has none")
            if w is not None and c is not None and ((c > w) if side == 0 else (c < w)):
                fail(f"{where}.limits", "the critical range must contain the warning range")
    return Limits(warning, critical)
