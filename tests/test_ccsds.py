import random

import pytest

from minisat.ccsds import (PRIMARY_HEADER_SIZE, TC, TM, PacketError, PrimaryHeader, build_packet, iter_packets,
                           pack_primary, parse_packet, unpack_primary)


def test_known_telemetry_header_bytes():
    # Worked out by hand: version 000, type 0 (TM), sec.hdr.flag 1, APID 100 = 0b00001100100
    #   -> 0000 1000 0110 0100 = 0x0864 ; sequence flags 11 + count 5 -> 1100 0000 0000 0101 = 0xC005 ; length 10
    header = PrimaryHeader(packet_type=TM, sec_hdr_flag=1, apid=100, seq_count=5, data_length=10)
    assert pack_primary(header).hex() == "0864c005000a"


def test_known_telecommand_header_bytes():
    # type bit 1 (TC), no secondary header, APID 10 -> 0001 0000 0000 1010 = 0x100A ; flags 11, count 0 -> 0xC000
    header = PrimaryHeader(packet_type=TC, sec_hdr_flag=0, apid=10, seq_count=0, data_length=2)
    assert pack_primary(header).hex() == "100ac0000002"


def test_pack_unpack_roundtrip_on_random_headers():
    rng = random.Random(7)
    for _ in range(500):
        h = PrimaryHeader(packet_type=rng.randint(0, 1), sec_hdr_flag=rng.randint(0, 1), apid=rng.randint(0, 2047),
                          seq_count=rng.randint(0, 16383), data_length=rng.randint(0, 65535),
                          seq_flags=rng.randint(0, 3), version=rng.randint(0, 7))
        assert unpack_primary(pack_primary(h)) == h


@pytest.mark.parametrize("field,value", [("apid", 2048), ("seq_count", 16384), ("data_length", 65536),
                                         ("packet_type", 2), ("seq_flags", 4), ("version", 8), ("apid", -1)])
def test_values_that_do_not_fit_are_rejected(field, value):
    kwargs = dict(packet_type=TM, sec_hdr_flag=0, apid=1, seq_count=0, data_length=0)
    kwargs[field] = value
    with pytest.raises(PacketError):
        pack_primary(PrimaryHeader(**kwargs))


def test_build_packet_computes_the_length_field():
    packet = build_packet(TM, 100, 0, b"\x01\x02\x03")
    assert len(packet) == PRIMARY_HEADER_SIZE + 3
    assert unpack_primary(packet).data_length == 2           # "bytes minus one"
    assert unpack_primary(packet).data_field_size == 3


def test_empty_data_field_is_rejected():
    with pytest.raises(PacketError):
        build_packet(TM, 100, 0, b"")


def test_parse_packet_checks_the_length_field():
    good = build_packet(TM, 100, 3, b"abcd")
    header, data = parse_packet(good)
    assert (header.apid, header.seq_count, data) == (100, 3, b"abcd")
    with pytest.raises(PacketError):
        parse_packet(good + b"x")                            # too long
    with pytest.raises(PacketError):
        parse_packet(good[:-1])                              # too short
    with pytest.raises(PacketError):
        parse_packet(good[:4])                               # not even a full header


def test_iter_packets_splits_a_recording():
    a, b, c = (build_packet(TM, 100, i, bytes([i]) * (i + 1)) for i in range(3))
    assert list(iter_packets(a + b + c)) == [a, b, c]
    assert list(iter_packets(b"")) == []


def test_iter_packets_detects_truncation():
    a = build_packet(TM, 100, 0, b"abcdef")
    with pytest.raises(PacketError, match="truncated"):
        list(iter_packets(a + a[:-2]))
