import math
import struct

import pytest

from minisat.ccsds import PacketError, TC, TM, build_packet, parse_packet
from minisat.codec import (check_range, decode_tc, decode_tm, encode_tc, encode_tm, enum_label, enum_value,
                           parse_text_value)

HK_VALUES = dict(mode=1, cmd_accepted=3, cmd_rejected=1, last_cmd_id=2, uptime_s=123456, battery_voltage=7.8,
                 battery_soc_pct=81.25, battery_temp_c=-3.5, solar_current_a=1.25, load_current_a=0.5,
                 in_eclipse=0, heater=1)


def test_housekeeping_roundtrip(spec):
    packet = encode_tm(spec, "Housekeeping", HK_VALUES, sc_time_ms=1_792_800_000_123, seq_count=42)
    assert len(packet) == 6 + 41                                      # primary header + hand-counted data field
    tm = decode_tm(spec, packet)
    assert (tm.packet, tm.apid, tm.seq_count, tm.sc_time_ms) == ("Housekeeping", 100, 42, 1_792_800_000_123)
    for name, sent in HK_VALUES.items():
        assert tm.values[name] == pytest.approx(sent, rel=1e-6), name  # float32 loses digits; integers are exact


def test_wire_bytes_of_a_small_packet_by_hand(spec):
    # Position: header 6 bytes, time 8 bytes, three float32. 0.0 -> 00 00 00 00 ; 1.0 -> 3f 80 00 00 ; -2.0 -> c0 00 00 00
    packet = encode_tm(spec, "Position", dict(latitude_deg=0.0, longitude_deg=1.0, altitude_km=-2.0), 258, 7)
    assert packet.hex() == ("0865" "c007" "0013"            # APID 101 -> 0x0865, seq flags 11 + count 7, length 20-1
                            "0000000000000102"              # 258 ms
                            "00000000" "3f800000" "c0000000")


def test_telecommand_roundtrip_and_bytes(spec):
    packet = encode_tc(spec, "SetMode", {"mode": "PAYLOAD"}, seq_count=9)
    assert packet.hex() == "100ac009" "0002" "0002" "02"      # type bit set, APID 10, count 9, length 3-1, id 2, mode 2
    cmd, args, header = decode_tc(spec, packet)
    assert (cmd.name, args, header.seq_count) == ("SetMode", {"mode": 2}, 9)


def test_command_without_arguments(spec):
    packet = encode_tc(spec, "Noop")
    assert packet.hex() == "100ac000" "0001" "0001"
    assert decode_tc(spec, packet)[0].name == "Noop"


def test_float_argument_roundtrip(spec):
    cmd, args, _ = decode_tc(spec, encode_tc(spec, "SetTmRate", {"period_s": 2.5}))
    assert cmd.name == "SetTmRate" and args == {"period_s": 2.5}


def test_enum_helpers(spec):
    mode = next(f for f in spec.all_tm_fields() if f.name == "mode")
    assert enum_value(spec, mode, "PAYLOAD") == 2
    assert enum_value(spec, mode, 1) == 1
    assert enum_label(spec, mode, 0) == "SAFE"
    assert enum_label(spec, mode, 77) is None
    with pytest.raises(PacketError, match="not one of"):
        enum_value(spec, mode, "WARP")
    with pytest.raises(PacketError, match="not a defined value"):
        enum_value(spec, mode, 9)


def test_parse_text_values(spec):
    set_mode = spec.command_by_name("SetMode").args[0]
    rate = spec.command_by_name("SetTmRate").args[0]
    assert parse_text_value(spec, set_mode, "PAYLOAD") == 2
    assert parse_text_value(spec, set_mode, "1") == 1
    assert parse_text_value(spec, set_mode, "0x2") == 2
    assert parse_text_value(spec, rate, "0.5") == 0.5
    with pytest.raises(PacketError):
        parse_text_value(spec, rate, "fast")
    with pytest.raises(PacketError):
        parse_text_value(spec, set_mode, "PAYLOADS")


@pytest.mark.parametrize("name,args,message", [
    ("SetMode", {}, "missing argument"),
    ("SetMode", {"mode": "SAFE", "extra": 1}, "unknown argument"),
    ("SetMode", {"mode": "WARP"}, "not one of"),
    ("SetTmRate", {"period_s": 0.01}, "outside the allowed range"),
    ("SetTmRate", {"period_s": 61}, "outside the allowed range"),
    ("SetTmRate", {"period_s": float("nan")}, "outside the allowed range"),
    ("Noop", {"x": 1}, "unknown argument"),
])
def test_bad_telecommands_are_refused_when_encoding(spec, name, args, message):
    with pytest.raises(PacketError, match=message):
        encode_tc(spec, name, args)


def test_validation_can_be_switched_off_to_craft_a_bad_command(spec):
    packet = encode_tc(spec, "SetTmRate", {"period_s": 1000.0}, validate=False)
    assert decode_tc(spec, packet)[1] == {"period_s": 1000.0}


def test_range_check_boundaries_are_inclusive(spec):
    field = spec.command_by_name("SetTmRate").args[0]
    check_range(field, 0.1)
    check_range(field, 60)
    with pytest.raises(PacketError):
        check_range(field, 60.0001)


def test_missing_and_unknown_telemetry_fields(spec):
    values = dict(HK_VALUES)
    values.pop("mode")
    with pytest.raises(PacketError, match="no value for mode"):
        encode_tm(spec, "Housekeeping", values, 0, 0)
    with pytest.raises(PacketError, match="unknown field"):
        encode_tm(spec, "Housekeeping", {**HK_VALUES, "bogus": 1}, 0, 0)


@pytest.mark.parametrize("field,value", [("cmd_accepted", 70000), ("cmd_accepted", -1), ("uptime_s", 2 ** 32),
                                         ("cmd_accepted", 1.5), ("cmd_accepted", "x")])
def test_integers_that_do_not_fit_are_refused(spec, field, value):
    with pytest.raises(PacketError):
        encode_tm(spec, "Housekeeping", {**HK_VALUES, field: value}, 0, 0)


def test_float32_overflow_is_refused(spec):
    with pytest.raises(PacketError, match="does not fit"):
        encode_tm(spec, "Position", dict(latitude_deg=1e39, longitude_deg=0, altitude_km=0), 0, 0)


def test_sequence_counter_must_fit_14_bits(spec):
    with pytest.raises(PacketError):
        encode_tm(spec, "Housekeeping", HK_VALUES, 0, 16384)


def test_decoding_rejects_foreign_or_damaged_packets(spec):
    good = encode_tm(spec, "Housekeeping", HK_VALUES, 0, 0)
    with pytest.raises(PacketError, match="unknown telemetry APID"):
        decode_tm(spec, build_packet(TM, 5, 0, b"\x00" * 9, sec_hdr_flag=1))
    with pytest.raises(PacketError, match="expected 41 data bytes"):
        header, data = parse_packet(good)
        decode_tm(spec, build_packet(TM, 100, 0, data[:-1], sec_hdr_flag=1))
    with pytest.raises(PacketError, match="not a telemetry packet"):
        decode_tm(spec, encode_tc(spec, "Noop"))
    with pytest.raises(PacketError, match="secondary header flag"):
        header, data = parse_packet(good)
        decode_tm(spec, build_packet(TM, 100, 0, data, sec_hdr_flag=0))
    with pytest.raises(PacketError):
        decode_tm(spec, good[:-1])


def test_decoding_rejects_bad_telecommands(spec):
    with pytest.raises(PacketError, match="not a telecommand"):
        decode_tc(spec, encode_tm(spec, "Position", dict(latitude_deg=0, longitude_deg=0, altitude_km=0), 0, 0))
    with pytest.raises(PacketError, match="is not the command APID"):
        decode_tc(spec, build_packet(TC, 11, 0, b"\x00\x01"))
    with pytest.raises(PacketError, match="unknown command id"):
        decode_tc(spec, build_packet(TC, 10, 0, struct.pack(">H", 99)))
    with pytest.raises(PacketError, match="expected 3 data bytes"):
        decode_tc(spec, build_packet(TC, 10, 0, struct.pack(">H", 2)))        # SetMode without its argument
    with pytest.raises(PacketError, match="too short"):
        decode_tc(spec, build_packet(TC, 10, 0, b"\x01"))


def test_nan_survives_a_telemetry_roundtrip(spec):
    packet = encode_tm(spec, "Position", dict(latitude_deg=float("nan"), longitude_deg=0, altitude_km=0), 0, 0)
    assert math.isnan(decode_tm(spec, packet).values["latitude_deg"])
