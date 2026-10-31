"""Packing and unpacking of telemetry and telecommand packets, driven entirely by the specification.

Nothing here knows about "battery voltage" or "SetMode": it reads the field list from :mod:`minisat.spec` and
packs/unpacks accordingly. So adding a field to ``spec/minisat.yaml`` changes the wire format without touching Python.
"""
from __future__ import annotations

import math
import struct
from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from .ccsds import TC, TM, PacketError, PrimaryHeader, build_packet, parse_packet
from .spec import CommandSpec, Field, Spec

__all__ = ["Telemetry", "encode_tm", "decode_tm", "encode_tc", "decode_tc", "enum_value", "enum_label",
           "parse_text_value"]


@dataclass(frozen=True)
class Telemetry:
    """A decoded telemetry packet. ``values`` holds the raw numbers (enum fields as integers)."""
    packet: str
    apid: int
    seq_count: int
    sc_time_ms: int
    values: dict


# ------------------------------------------------------------------------------------------------ enums

def enum_value(spec: Spec, field: Field, value) -> int:
    """Turn an enum label ("PAYLOAD") or an integer into the integer; reject anything not defined."""
    labels = spec.enums[field.enum]
    if isinstance(value, str):
        if value not in labels:
            raise PacketError(f"{field.name}: {value!r} is not one of {', '.join(labels)}")
        return labels[value]
    if value not in labels.values():
        raise PacketError(f"{field.name}: {value} is not a defined value of enum {field.enum}")
    return int(value)


def enum_label(spec: Spec, field: Field, value: int) -> Optional[str]:
    """The label for ``value`` (None if the number is not defined in the enum)."""
    for label, v in spec.enums[field.enum].items():
        if v == value:
            return label
    return None


def parse_text_value(spec: Spec, field: Field, text: str):
    """Interpret a command-line string for ``field``: enum label, integer or float according to its type."""
    if field.enum:
        if text in spec.enums[field.enum]:
            return enum_value(spec, field, text)
        try:
            return enum_value(spec, field, int(text, 0))
        except ValueError:                                  # neither a label nor a number: list the valid labels
            return enum_value(spec, field, text)
    return _to_float(field, text) if field.type.kind == "float" else _to_int(field, text)


def _to_int(field: Field, text: str) -> int:
    try:
        return int(text, 0)
    except ValueError:
        raise PacketError(f"{field.name}: {text!r} is not an integer") from None


def _to_float(field: Field, text: str) -> float:
    try:
        return float(text)
    except ValueError:
        raise PacketError(f"{field.name}: {text!r} is not a number") from None


# ------------------------------------------------------------------------------------------------ scalars

def _pack_scalar(field: Field, value, spec: Spec) -> bytes:
    t = field.type
    if field.enum:
        value = enum_value(spec, field, value)
    if t.kind == "float":
        try:
            return struct.pack(">" + t.fmt, float(value))
        except OverflowError:
            raise PacketError(f"{field.name}: {value} does not fit in {t.name}") from None
    if isinstance(value, float):
        if not value.is_integer():
            raise PacketError(f"{field.name}: {value} is not an integer")
        value = int(value)
    if not isinstance(value, int) or not t.contains(value):
        raise PacketError(f"{field.name}: {value!r} does not fit in {t.name}")
    return struct.pack(">" + t.fmt, value)


def _unpack_scalar(field: Field, data: bytes, offset: int):
    value, = struct.unpack_from(">" + field.type.fmt, data, offset)
    return value


# ------------------------------------------------------------------------------------------------ telemetry

def encode_tm(spec: Spec, packet_name: str, values: Mapping, sc_time_ms: int, seq_count: int) -> bytes:
    """Build a complete telemetry packet: primary header + 8-byte spacecraft time + the fields in spec order."""
    pkt = spec.tm_by_name(packet_name)
    missing = [f.name for f in pkt.fields if f.name not in values]
    if missing:
        raise PacketError(f"{packet_name}: no value for {', '.join(missing)}")
    extra = set(values) - {f.name for f in pkt.fields}
    if extra:
        raise PacketError(f"{packet_name}: unknown field(s) {', '.join(sorted(extra))}")
    if not 0 <= sc_time_ms < 2 ** 64:
        raise PacketError("spacecraft time does not fit in 64 bits")
    body = struct.pack(">Q", sc_time_ms) + b"".join(_pack_scalar(f, values[f.name], spec) for f in pkt.fields)
    return build_packet(TM, pkt.apid, seq_count, body, sec_hdr_flag=1)


def decode_tm(spec: Spec, packet: bytes) -> Telemetry:
    """Parse a telemetry packet; raises PacketError if it is not one this mission defines."""
    header, data = parse_packet(packet)
    if header.packet_type != TM:
        raise PacketError("not a telemetry packet (type bit is 1)")
    pkt = spec.tm_by_apid(header.apid)
    if pkt is None:
        raise PacketError(f"unknown telemetry APID {header.apid}")
    if not header.sec_hdr_flag:
        raise PacketError(f"{pkt.name}: secondary header flag not set")
    if len(data) != pkt.data_size:
        raise PacketError(f"{pkt.name}: expected {pkt.data_size} data bytes, got {len(data)}")
    sc_time_ms, = struct.unpack_from(">Q", data, 0)
    values, offset = {}, 8
    for f in pkt.fields:
        values[f.name] = _unpack_scalar(f, data, offset)
        offset += f.type.size
    return Telemetry(pkt.name, header.apid, header.seq_count, sc_time_ms, values)


# ------------------------------------------------------------------------------------------------ telecommands

def check_range(field: Field, value) -> None:
    """Raise PacketError if ``value`` lies outside the argument's allowed range (if it has one)."""
    if field.range is None:
        return
    lo, hi = field.range
    if not (lo <= value <= hi) or (isinstance(value, float) and math.isnan(value)):
        raise PacketError(f"{field.name}: {value} is outside the allowed range [{lo}, {hi}]")


def encode_tc(spec: Spec, command_name: str, args: Optional[Mapping] = None, seq_count: int = 0,
              validate: bool = True) -> bytes:
    """Build a telecommand packet. With ``validate`` (default) argument ranges are enforced, like a careful ground
    system would; pass ``validate=False`` to craft an out-of-range command on purpose (the spacecraft must still
    defend itself)."""
    cmd = spec.command_by_name(command_name)
    args = dict(args or {})
    missing = [a.name for a in cmd.args if a.name not in args]
    if missing:
        raise PacketError(f"{cmd.name}: missing argument(s) {', '.join(missing)}")
    extra = set(args) - {a.name for a in cmd.args}
    if extra:
        raise PacketError(f"{cmd.name}: unknown argument(s) {', '.join(sorted(extra))}")
    body = struct.pack(">H", cmd.id)
    for a in cmd.args:
        value = args[a.name]
        if validate and not a.enum:
            check_range(a, value)
        body += _pack_scalar(a, value, spec)
    return build_packet(TC, spec.tc_apid, seq_count, body, sec_hdr_flag=0)


def decode_tc(spec: Spec, packet: bytes) -> Tuple[CommandSpec, dict, PrimaryHeader]:
    """Parse a telecommand packet into (command, raw argument values, header)."""
    header, data = parse_packet(packet)
    if header.packet_type != TC:
        raise PacketError("not a telecommand packet (type bit is 0)")
    if header.apid != spec.tc_apid:
        raise PacketError(f"telecommand APID {header.apid} is not the command APID {spec.tc_apid}")
    if len(data) < 2:
        raise PacketError("telecommand too short: no command id")
    cmd_id, = struct.unpack_from(">H", data, 0)
    cmd = spec.command_by_id(cmd_id)
    if cmd is None:
        raise PacketError(f"unknown command id {cmd_id}")
    if len(data) != cmd.data_size:
        raise PacketError(f"{cmd.name}: expected {cmd.data_size} data bytes, got {len(data)}")
    args, offset = {}, 2
    for a in cmd.args:
        args[a.name] = _unpack_scalar(a, data, offset)
        offset += a.type.size
    return cmd, args, header
