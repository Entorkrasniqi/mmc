"""The definition layer of the ontology (ontology.md section 1, ADR 0001).

TelemetryPacketType, TelemetryParameter and CommandDefinition are built from the loaded specification and are
read-only: they are never stored in the database and never edited at runtime. To change one, change
spec/minisat.yaml and run ``minisat gen-xtce``. The operations layer refers to them by stable names
(``parameter_name``, ``command_id``) without a foreign key, because they live in the specification, not in a table.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from minisat.spec import CommandSpec, Field, Spec, TmPacketSpec, load_spec

__all__ = ["TelemetryParameter", "TelemetryPacketType", "CommandArgument", "CommandDefinition", "Definitions",
           "definitions_from_spec", "load_definitions", "NORMAL", "VITAL"]

NORMAL = "NORMAL"
VITAL = "VITAL"

PRIMARY_HEADER_BYTES = 6


@dataclass(frozen=True)
class TelemetryParameter:
    """One measured quantity, independent of any value it ever had."""
    name: str
    packet_apid: int
    position: int                              # index within its packet; this is also the wire order
    data_type: str                             # "uint8", "float32", ...
    description: str = ""
    unit: Optional[str] = None
    enum_name: Optional[str] = None
    enum_labels: Optional[tuple] = None        # ((label, value), ...) in value order, when it is an enum
    warning: Optional[tuple] = None            # still-fine range (min, max); None = no limit on that side
    critical: Optional[tuple] = None

    @property
    def warning_low(self) -> Optional[float]:
        return self.warning[0] if self.warning else None

    @property
    def warning_high(self) -> Optional[float]:
        return self.warning[1] if self.warning else None

    @property
    def critical_low(self) -> Optional[float]:
        return self.critical[0] if self.critical else None

    @property
    def critical_high(self) -> Optional[float]:
        return self.critical[1] if self.critical else None

    def severity_of(self, value: float) -> Optional[str]:
        """``None`` if ``value`` is fine, else ``"WARNING"`` or ``"CRITICAL"`` (the worse of the two)."""
        if self.critical and not _inside(value, self.critical):
            return "CRITICAL"
        if self.warning and not _inside(value, self.warning):
            return "WARNING"
        return None


@dataclass(frozen=True)
class TelemetryPacketType:
    apid: int
    name: str
    period_s: float
    description: str
    size_bytes: int                            # the whole packet on the wire, primary header included
    parameter_names: tuple


@dataclass(frozen=True)
class CommandArgument:
    name: str
    data_type: str
    description: str = ""
    unit: Optional[str] = None
    enum_name: Optional[str] = None
    enum_labels: Optional[tuple] = None
    range_min: Optional[float] = None
    range_max: Optional[float] = None


@dataclass(frozen=True)
class CommandDefinition:
    command_id: int
    name: str
    description: str
    significance: str                          # NORMAL or VITAL
    arguments: tuple

    @property
    def is_vital(self) -> bool:
        return self.significance == VITAL


@dataclass(frozen=True)
class Definitions:
    mission_name: str
    packet_types: tuple
    parameters: tuple
    commands: tuple

    def parameter(self, name: str) -> TelemetryParameter:
        for p in self.parameters:
            if p.name == name:
                return p
        raise KeyError(f"no telemetry parameter named {name!r}")

    def packet_type(self, apid: int) -> TelemetryPacketType:
        for p in self.packet_types:
            if p.apid == apid:
                return p
        raise KeyError(f"no telemetry packet type with APID {apid}")

    def packet_parameters(self, apid: int) -> tuple:
        """The parameters of one packet type, in wire order."""
        return tuple(p for p in self.parameters if p.packet_apid == apid)

    def command(self, name_or_id) -> CommandDefinition:
        for c in self.commands:
            if c.name == name_or_id or c.command_id == name_or_id:
                return c
        raise KeyError(f"no command {name_or_id!r}")


def _inside(value: float, bounds: tuple) -> bool:
    lo, hi = bounds
    return (lo is None or value >= lo) and (hi is None or value <= hi)


def _enum_labels(spec: Spec, enum_name: Optional[str]) -> Optional[tuple]:
    if enum_name is None:
        return None
    return tuple(sorted(spec.enums[enum_name].items(), key=lambda item: item[1]))


def _parameter(spec: Spec, packet: TmPacketSpec, position: int, f: Field) -> TelemetryParameter:
    return TelemetryParameter(
        name=f.name, packet_apid=packet.apid, position=position, data_type=f.type.name, description=f.description,
        unit=f.unit, enum_name=f.enum, enum_labels=_enum_labels(spec, f.enum),
        warning=f.limits.warning if f.limits else None, critical=f.limits.critical if f.limits else None)


def _command(spec: Spec, c: CommandSpec) -> CommandDefinition:
    args = tuple(CommandArgument(
        name=a.name, data_type=a.type.name, description=a.description, unit=a.unit, enum_name=a.enum,
        enum_labels=_enum_labels(spec, a.enum),
        range_min=a.range[0] if a.range else None, range_max=a.range[1] if a.range else None) for a in c.args)
    return CommandDefinition(command_id=c.id, name=c.name, description=c.description,
                             significance=VITAL if c.significance == "vital" else NORMAL, arguments=args)


def definitions_from_spec(spec: Spec) -> Definitions:
    packet_types = []
    parameters = []
    for p in spec.tm_packets:
        packet_types.append(TelemetryPacketType(
            apid=p.apid, name=p.name, period_s=p.period_s, description=p.description,
            size_bytes=PRIMARY_HEADER_BYTES + p.data_size, parameter_names=tuple(f.name for f in p.fields)))
        parameters.extend(_parameter(spec, p, i, f) for i, f in enumerate(p.fields))
    return Definitions(mission_name=spec.mission_name, packet_types=tuple(packet_types),
                       parameters=tuple(parameters), commands=tuple(_command(spec, c) for c in spec.commands))


def load_definitions(path="spec/minisat.yaml") -> Definitions:
    return definitions_from_spec(load_spec(path))
