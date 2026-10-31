"""CCSDS Space Packet framing (the 6-byte primary header) - the envelope almost every spacecraft message uses.

CCSDS (Consultative Committee for Space Data Systems) is the standards body that agrees how space agencies and
companies format data. The *Space Packet Protocol* (CCSDS 133.0-B) defines a small header in front of every packet.
Bit layout of the 6 bytes (bit 0 = most significant bit of byte 0):

     3 bits   1 bit    1 bit      11 bits          2 bits        14 bits          16 bits
   +---------+------+----------+-----------+----------------+---------------+------------------+
   | version | type | sec.hdr. |   APID    | sequence flags | sequence count| data length - 1  |
   |  (= 0)  | 0=TM |  flag    | (channel) |  (3 = alone)   | (per APID)    |                  |
   |         | 1=TC | 1=present|           |                |               |                  |
   +---------+------+----------+-----------+----------------+---------------+------------------+
   |<------------ 16 bits ----------------->|<----------------- 16 bits ---->|<---- 16 bits --->|

* APID (Application Process Identifier): which "application" produced the packet; used to tell packet types apart.
* sequence count: increments by one per packet of the same APID, so the receiver can spot lost packets.
* data length: number of bytes after the header MINUS ONE (so a packet always carries at least one byte).
"""
from __future__ import annotations

import struct
from dataclasses import dataclass
from typing import Iterator, Tuple

__all__ = ["PacketError", "PRIMARY_HEADER_SIZE", "TM", "TC", "STANDALONE", "PrimaryHeader", "pack_primary",
           "unpack_primary", "build_packet", "parse_packet", "iter_packets"]

PRIMARY_HEADER_SIZE = 6
TM = 0              # packet type bit: telemetry (spacecraft -> ground)
TC = 1              # packet type bit: telecommand (ground -> spacecraft)
STANDALONE = 3      # sequence flags value meaning "this packet is not part of a split sequence"


class PacketError(ValueError):
    """A packet is malformed or a value does not fit."""


@dataclass(frozen=True)
class PrimaryHeader:
    packet_type: int            # TM or TC
    sec_hdr_flag: int           # 1 if a secondary header follows the primary header
    apid: int                   # 0..2047
    seq_count: int              # 0..16383
    data_length: int            # the raw header field: (bytes of data field) - 1
    version: int = 0
    seq_flags: int = STANDALONE

    @property
    def data_field_size(self) -> int:
        """Number of bytes that follow the primary header."""
        return self.data_length + 1


def pack_primary(h: PrimaryHeader) -> bytes:
    for name, value, limit in (("version", h.version, 8), ("packet_type", h.packet_type, 2),
                               ("sec_hdr_flag", h.sec_hdr_flag, 2), ("apid", h.apid, 2048),
                               ("seq_flags", h.seq_flags, 4), ("seq_count", h.seq_count, 16384),
                               ("data_length", h.data_length, 65536)):
        if not 0 <= value < limit:
            raise PacketError(f"{name}={value} does not fit in its header field (0..{limit - 1})")
    word1 = (h.version << 13) | (h.packet_type << 12) | (h.sec_hdr_flag << 11) | h.apid
    word2 = (h.seq_flags << 14) | h.seq_count
    return struct.pack(">HHH", word1, word2, h.data_length)


def unpack_primary(data: bytes) -> PrimaryHeader:
    if len(data) < PRIMARY_HEADER_SIZE:
        raise PacketError(f"packet shorter than the {PRIMARY_HEADER_SIZE}-byte primary header ({len(data)} bytes)")
    word1, word2, length = struct.unpack(">HHH", data[:PRIMARY_HEADER_SIZE])
    return PrimaryHeader(version=word1 >> 13, packet_type=(word1 >> 12) & 1, sec_hdr_flag=(word1 >> 11) & 1,
                         apid=word1 & 0x7FF, seq_flags=word2 >> 14, seq_count=word2 & 0x3FFF, data_length=length)


def build_packet(packet_type: int, apid: int, seq_count: int, data_field: bytes, sec_hdr_flag: int = 0,
                 seq_flags: int = STANDALONE) -> bytes:
    """Prefix ``data_field`` with a correct primary header (the length field is computed for you)."""
    if not data_field:
        raise PacketError("the data field of a space packet must not be empty")
    header = PrimaryHeader(packet_type=packet_type, sec_hdr_flag=sec_hdr_flag, apid=apid, seq_count=seq_count,
                           data_length=len(data_field) - 1, seq_flags=seq_flags)
    return pack_primary(header) + data_field


def parse_packet(packet: bytes) -> Tuple[PrimaryHeader, bytes]:
    """Split one complete packet into header and data field, checking that the length field is consistent."""
    header = unpack_primary(packet)
    data = packet[PRIMARY_HEADER_SIZE:]
    if len(data) != header.data_field_size:
        raise PacketError(f"length field says {header.data_field_size} data bytes but the packet carries "
                          f"{len(data)}")
    return header, data


def iter_packets(stream: bytes) -> Iterator[bytes]:
    """Cut a byte string that holds several packets back to back (e.g. a recording) into single packets."""
    pos = 0
    while pos < len(stream):
        header = unpack_primary(stream[pos:])
        end = pos + PRIMARY_HEADER_SIZE + header.data_field_size
        if end > len(stream):
            raise PacketError(f"truncated packet at byte {pos}: header announces {header.data_field_size} data bytes "
                              f"but only {len(stream) - pos - PRIMARY_HEADER_SIZE} remain")
        yield stream[pos:end]
        pos = end
