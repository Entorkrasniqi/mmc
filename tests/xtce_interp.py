"""A miniature, independent interpreter for the XTCE subset that ``minisat gen-xtce`` produces.

WHY THIS EXISTS: Yamcs is the program that will really read the generated file, and it cannot run in a test suite
here. The next best thing is a second program that reads the same file and answers the question Yamcs will ask:
"given these bytes, what are the parameter values?" and "given this command and its arguments, which bytes do I send?".
If this interpreter - which knows nothing about the specification or about codec.py, only about XTCE - agrees with the
codec on every packet, then the XTCE file describes the real wire format.

It implements just enough of XTCE: integer/float/enumerated/boolean/aggregate types, container inheritance with
restriction criteria, meta-command inheritance with argument assignments, fixed-value entries, and static alarm ranges.
It is NOT a general XTCE implementation.
"""
from __future__ import annotations

import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

NS = {"x": "http://www.omg.org/spec/XTCE/20180204"}


def _q(tag: str) -> str:
    return "{%s}%s" % (NS["x"], tag)


class BitReader:
    """Reads bits most-significant-first, like a CCSDS packet is laid out."""

    def __init__(self, data: bytes):
        self.value = int.from_bytes(data, "big")
        self.nbits = len(data) * 8
        self.pos = 0

    def read(self, n: int) -> int:
        if self.pos + n > self.nbits:
            raise ValueError("packet too short for the container")
        shift = self.nbits - self.pos - n
        self.pos += n
        return (self.value >> shift) & ((1 << n) - 1)


class BitWriter:
    def __init__(self):
        self.value = 0
        self.nbits = 0

    def write(self, value: int, n: int) -> None:
        self.value = (self.value << n) | (value & ((1 << n) - 1))
        self.nbits += n

    def to_bytes(self) -> bytes:
        if self.nbits % 8:
            raise ValueError(f"command is {self.nbits} bits long, not a whole number of bytes")
        return self.value.to_bytes(self.nbits // 8, "big")


@dataclass
class TypeInfo:
    kind: str                       # "int", "float", "enum", "bool", "aggregate"
    bits: int = 0
    signed: bool = False
    labels: Optional[Dict[int, str]] = None
    members: Optional[List[tuple]] = None       # aggregate: (name, typeRef)
    zero: str = ""
    one: str = ""
    valid_range: Optional[tuple] = None
    alarm: Optional[dict] = None                # {"warning": (lo, hi), "critical": (lo, hi)}


class Xtce:
    def __init__(self, xml_text: str):
        self.root = ET.fromstring(xml_text)
        tm = self.root.find("x:TelemetryMetaData", NS)
        cm = self.root.find("x:CommandMetaData", NS)
        self.ptypes = {e.get("name"): self._type(e) for e in tm.find("x:ParameterTypeSet", NS)}
        self.params = {e.get("name"): e.get("parameterTypeRef") for e in tm.find("x:ParameterSet", NS)}
        self.containers = {e.get("name"): e for e in tm.find("x:ContainerSet", NS)}
        self.atypes = {e.get("name"): self._type(e) for e in cm.find("x:ArgumentTypeSet", NS)}
        self.commands = {e.get("name"): e for e in cm.find("x:MetaCommandSet", NS)}

    # ------------------------------------------------------------------ types

    @staticmethod
    def _type(e: ET.Element) -> TypeInfo:
        tag = e.tag.split("}")[1]
        if tag.startswith("Aggregate"):
            return TypeInfo("aggregate", members=[(m.get("name"), m.get("typeRef")) for m in e.find("x:MemberList", NS)])
        info = TypeInfo("int")
        ienc = e.find("x:IntegerDataEncoding", NS)
        fenc = e.find("x:FloatDataEncoding", NS)
        if fenc is not None:
            info.kind, info.bits = "float", int(fenc.get("sizeInBits"))
        else:
            info.bits = int(ienc.get("sizeInBits"))
            info.signed = ienc.get("encoding") == "twosComplement"
        if tag.startswith("Enumerated"):
            info.kind = "enum"
            info.labels = {int(x.get("value")): x.get("label") for x in e.find("x:EnumerationList", NS)}
        elif tag.startswith("Boolean"):
            info.kind, info.zero, info.one = "bool", e.get("zeroStringValue"), e.get("oneStringValue")
        if tag.startswith("Integer") and e.get("signed") == "true":
            info.signed = True
        vr = e.find("x:ValidRangeSet/x:ValidRange", NS)
        if vr is not None:
            info.valid_range = (float(vr.get("minInclusive")), float(vr.get("maxInclusive")))
        sar = e.find("x:DefaultAlarm/x:StaticAlarmRanges", NS)
        if sar is not None:
            info.alarm = {}
            for tag_name, key in (("WarningRange", "warning"), ("CriticalRange", "critical")):
                r = sar.find(f"x:{tag_name}", NS)
                if r is not None:
                    lo, hi = r.get("minInclusive"), r.get("maxInclusive")
                    info.alarm[key] = (None if lo is None else float(lo), None if hi is None else float(hi))
        return info

    @staticmethod
    def _decode_scalar(info: TypeInfo, reader: BitReader):
        raw = reader.read(info.bits)
        if info.kind == "float":
            return struct.unpack(">f" if info.bits == 32 else ">d", raw.to_bytes(info.bits // 8, "big"))[0]
        if info.signed and raw >= 1 << (info.bits - 1):
            raw -= 1 << info.bits
        return raw

    @staticmethod
    def _label(info: TypeInfo, raw: int):
        if info.kind == "enum":
            return info.labels[raw]
        if info.kind == "bool":
            return info.one if raw else info.zero
        return raw

    # ------------------------------------------------------------------ telemetry

    def alarm_level(self, parameter: str, value: float) -> str:
        """'normal', 'warning' or 'critical' for a value, following XTCE static alarm range semantics."""
        info = self.ptypes[self.params[parameter]]
        if not info.alarm:
            return "normal"
        for level in ("critical", "warning"):
            if level in info.alarm:
                lo, hi = info.alarm[level]
                if (lo is not None and value < lo) or (hi is not None and value > hi):
                    return level
        return "normal"

    def decode(self, packet: bytes) -> tuple:
        """Return (container name, {parameter: raw value}) for a telemetry packet."""
        reader = BitReader(packet)
        values: Dict[str, Any] = {}
        labels: Dict[str, Any] = {}      # label forms, used for restriction comparisons

        def read_entries(container: ET.Element):
            for entry in container.find("x:EntryList", NS):
                name = entry.get("parameterRef")
                info = self.ptypes[self.params[name]]
                if info.kind == "aggregate":
                    for member, ref in info.members:
                        minfo = self.ptypes[ref]
                        raw = self._decode_scalar(minfo, reader)
                        values[f"{name}/{member}"] = raw
                        labels[f"{name}/{member}"] = self._label(minfo, raw)
                else:
                    raw = self._decode_scalar(info, reader)
                    values[name] = raw
                    labels[name] = self._label(info, raw)

        def matches(container: ET.Element) -> bool:
            base = container.find("x:BaseContainer", NS)
            for cmp_ in base.findall("x:RestrictionCriteria/x:ComparisonList/x:Comparison", NS):
                if str(labels.get(cmp_.get("parameterRef"))) != cmp_.get("value"):
                    return False
            return True

        # walk the inheritance tree from the abstract root down to a concrete container
        current = next(c for c in self.containers.values() if c.find("x:BaseContainer", NS) is None)
        read_entries(current)
        while True:
            children = [c for c in self.containers.values()
                        if c.find("x:BaseContainer", NS) is not None
                        and c.find("x:BaseContainer", NS).get("containerRef") == current.get("name")]
            nxt = []
            for child in children:
                if matches(child):
                    nxt.append(child)
            if not nxt:
                break
            if len(nxt) > 1:
                raise ValueError("ambiguous container match: " + ", ".join(c.get("name") for c in nxt))
            current = nxt[0]
            read_entries(current)
        if reader.pos != reader.nbits:
            raise ValueError(f"container {current.get('name')} used {reader.pos} bits of {reader.nbits}")
        return current.get("name"), values

    # ------------------------------------------------------------------ commands

    def build_command(self, name: str, user_args: Dict[str, Any]) -> bytes:
        """Encode command ``name`` with the given argument values (enum labels or numbers)."""
        chain: List[ET.Element] = []
        mc = self.commands[name]
        while mc is not None:
            chain.append(mc)
            base = mc.find("x:BaseMetaCommand", NS)
            mc = self.commands[base.get("metaCommandRef")] if base is not None else None
        if self.commands[name].get("abstract") == "true":
            raise ValueError("cannot build an abstract command")
        chain.reverse()                                   # root ... leaf

        assignments: Dict[str, str] = {}
        arg_types: Dict[str, TypeInfo] = {}
        for c in chain:
            al = c.find("x:ArgumentList", NS)
            if al is not None:
                for a in al:
                    arg_types[a.get("name")] = self.atypes[a.get("argumentTypeRef")]
            base = c.find("x:BaseMetaCommand", NS)
            if base is not None:
                for aa in base.findall("x:ArgumentAssignmentList/x:ArgumentAssignment", NS):
                    if aa.get("argumentName") in assignments:
                        raise ValueError("assigned twice: " + aa.get("argumentName"))
                    assignments[aa.get("argumentName")] = aa.get("argumentValue")
        for given in user_args:
            if given in assignments or given not in arg_types:
                raise ValueError(f"argument {given!r} cannot be set by the user")
        unassigned = set(arg_types) - set(assignments) - set(user_args)
        if unassigned:
            raise ValueError("no value for " + ", ".join(sorted(unassigned)))

        writer = BitWriter()

        def encode(arg_name: str):
            info = arg_types[arg_name]
            value = assignments[arg_name] if arg_name in assignments else user_args[arg_name]
            if info.kind == "enum":
                inv = {v: k for k, v in info.labels.items()}
                raw = inv[value] if isinstance(value, str) and value in inv else int(value)
                if raw not in info.labels:
                    raise ValueError(f"{arg_name}: {value} not in enumeration")
                writer.write(raw, info.bits)
            elif info.kind == "bool":
                raw = {info.zero: 0, info.one: 1}[value]
                writer.write(raw, info.bits)
            elif info.kind == "float":
                f = float(value)
                if info.valid_range and not (info.valid_range[0] <= f <= info.valid_range[1]):
                    raise ValueError(f"{arg_name}: {f} outside {info.valid_range}")
                fmt = ">f" if info.bits == 32 else ">d"
                writer.write(int.from_bytes(struct.pack(fmt, f), "big"), info.bits)
            else:
                i = int(float(value))
                if info.valid_range and not (info.valid_range[0] <= i <= info.valid_range[1]):
                    raise ValueError(f"{arg_name}: {i} outside {info.valid_range}")
                writer.write(i, info.bits)

        # container chain: base containers first. Each MetaCommand has one CommandContainer.
        for c in chain:
            cc = c.find("x:CommandContainer", NS)
            for entry in cc.find("x:EntryList", NS):
                tag = entry.tag.split("}")[1]
                if tag == "ArgumentRefEntry":
                    encode(entry.get("argumentRef"))
                elif tag == "FixedValueEntry":
                    bits = int(entry.get("sizeInBits"))
                    hexvalue = entry.get("binaryValue")
                    full = int(hexvalue, 16)
                    writer.write(full >> (len(hexvalue) * 4 - bits), bits)      # the first `bits` bits of the hex string
                else:
                    raise ValueError(f"unsupported entry {tag}")
        return writer.to_bytes()
