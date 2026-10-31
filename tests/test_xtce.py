"""Tests of the generated XTCE database.

Three independent kinds of evidence, because Yamcs itself cannot run inside a unit test:

1. the committed file is exactly what the generator produces now (nobody forgot to regenerate);
2. it is valid XTCE 1.2 according to the official schema (only if the schema is available - see below);
3. an independent interpreter (tests/xtce_interp.py), reading ONLY the XML, decodes every packet the Python codec
   encodes to the same values, and builds the same telecommand bytes. Agreement means the XML describes the real wire format.
"""
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from minisat.codec import decode_tc, decode_tm, encode_tc, encode_tm
from minisat.xtce import generate_xtce
from xtce_interp import Xtce

from conftest import XTCE_PATH
from test_codec import HK_VALUES


@pytest.fixture(scope="module")
def xml_text():
    return XTCE_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def xtce(xml_text):
    return Xtce(xml_text)


def test_committed_database_is_up_to_date(spec, xml_text):
    assert xml_text == generate_xtce(spec), "spec/minisat.yaml changed - run: minisat gen-xtce"


def test_generation_is_deterministic(spec):
    assert generate_xtce(spec) == generate_xtce(spec)


def _xsd_candidates():
    env = os.environ.get("XTCE_XSD")
    if env:
        yield Path(env)
    yield Path(__file__).resolve().parent / "SpaceSystemV1.2.xsd"


def test_valid_against_the_official_schema(xml_text):
    pytest.importorskip("lxml")
    from validate_xtce import validate
    xsd = next((p for p in _xsd_candidates() if p.exists()), None)
    if xsd is None:
        if os.environ.get("XTCE_ONLINE") != "1":
            pytest.skip("set XTCE_XSD=<path to SpaceSystemV1.2.xsd> (or XTCE_ONLINE=1 to download it) to run this check")
    errors = validate(XTCE_PATH, xsd)
    assert errors == []


# ------------------------------------------------------------------------------ telemetry through the interpreter

def test_interpreter_decodes_housekeeping_like_the_codec(spec, xtce):
    packet = encode_tm(spec, "Housekeeping", HK_VALUES, 1_792_800_000_123, 42)
    container, values = xtce.decode(packet)
    assert container == "Housekeeping"
    tm = decode_tm(spec, packet)
    assert values["sc_time_ms"] == tm.sc_time_ms
    assert values["CCSDS_Packet_ID/APID"] == 100 and values["CCSDS_Packet_Sequence/Count"] == 42
    for name, expected in tm.values.items():
        assert values[name] == pytest.approx(expected), name


def test_interpreter_decodes_position(spec, xtce):
    packet = encode_tm(spec, "Position", dict(latitude_deg=-12.5, longitude_deg=170.25, altitude_km=560.0), 99, 3)
    container, values = xtce.decode(packet)
    assert container == "Position"
    assert (values["latitude_deg"], values["longitude_deg"], values["altitude_km"]) == (-12.5, 170.25, 560.0)


def test_interpreter_agrees_on_extreme_values(spec, xtce):
    hk = dict(HK_VALUES, cmd_accepted=65535, uptime_s=2 ** 32 - 1, mode=2, in_eclipse=1, heater=0)
    container, values = xtce.decode(encode_tm(spec, "Housekeeping", hk, 2 ** 63, 16383))
    assert container == "Housekeeping" and values["cmd_accepted"] == 65535 and values["uptime_s"] == 2 ** 32 - 1
    assert values["sc_time_ms"] == 2 ** 63 and values["CCSDS_Packet_Sequence/Count"] == 16383


def test_unknown_apid_matches_no_child_container(spec, xtce):
    # An APID nobody defined stops at the generic TelemetryPacket container, which has no entries of its own - so the
    # interpreter (like Yamcs, which would log an "unknown packet") cannot explain the data bytes and says so.
    from minisat.ccsds import TM, build_packet
    with pytest.raises(ValueError, match="TelemetryPacket used 48 bits"):
        xtce.decode(build_packet(TM, 7, 0, b"\x00" * 8, sec_hdr_flag=1))


def test_telecommand_packets_do_not_match_a_telemetry_container(spec, xtce):
    with pytest.raises(ValueError, match="CCSDSPacket used 48 bits"):
        xtce.decode(encode_tc(spec, "Noop"))


def test_interpreter_reports_its_own_mismatch_loudly(spec, xtce):
    from minisat.ccsds import TM, build_packet
    with pytest.raises(ValueError):
        xtce.decode(build_packet(TM, 101, 0, b"\x00" * 9, sec_hdr_flag=1))      # one byte too short for Position


# ------------------------------------------------------------------------------ alarms

@pytest.mark.parametrize("parameter,value,expected", [
    ("battery_soc_pct", 80.0, "normal"), ("battery_soc_pct", 35.0, "normal"), ("battery_soc_pct", 34.9, "warning"),
    ("battery_soc_pct", 20.0, "warning"), ("battery_soc_pct", 19.9, "critical"), ("battery_soc_pct", 100.0, "normal"),
    ("battery_voltage", 7.4, "normal"), ("battery_voltage", 6.7, "warning"), ("battery_voltage", 6.3, "critical"),
    ("battery_voltage", 8.55, "warning"), ("battery_voltage", 8.7, "critical"),
    ("battery_temp_c", 20, "normal"), ("battery_temp_c", -1, "warning"), ("battery_temp_c", -6, "critical"),
    ("battery_temp_c", 40, "warning"), ("battery_temp_c", 46, "critical"),
    ("solar_current_a", 99.0, "normal"),
])
def test_alarm_levels_follow_the_specification(spec, xtce, parameter, value, expected):
    assert xtce.alarm_level(parameter, value) == expected


def test_alarm_ranges_in_xml_equal_the_limits_in_the_spec(spec, xtce):
    for field in spec.all_tm_fields():
        info = xtce.ptypes[xtce.params[field.name]]
        if field.limits is None:
            assert info.alarm is None, field.name
            continue
        for level in ("warning", "critical"):
            declared = getattr(field.limits, level)
            if declared is None:
                assert level not in info.alarm
            else:
                assert info.alarm[level] == tuple(None if v is None else float(v) for v in declared), (field.name, level)


# ------------------------------------------------------------------------------ telecommands through the interpreter

COMMAND_CASES = [("Noop", {}), ("SetMode", {"mode": "SAFE"}), ("SetMode", {"mode": "PAYLOAD"}),
                 ("SetHeater", {"state": "ON"}), ("SetHeater", {"state": "OFF"}), ("Reboot", {}),
                 ("SetTmRate", {"period_s": 0.1}), ("SetTmRate", {"period_s": 2.5}), ("SetTmRate", {"period_s": 60})]


@pytest.mark.parametrize("name,args", COMMAND_CASES)
def test_interpreter_builds_the_same_bytes_as_the_codec(spec, xtce, name, args):
    for seq in (0,):       # the sequence count is assigned by the link layer (Yamcs), not by the command definition
        expected = encode_tc(spec, name, args, seq_count=seq)
        assert xtce.build_command(name, args) == expected, name
    cmd, decoded_args, header = decode_tc(spec, xtce.build_command(name, args))
    assert cmd.name == name and header.apid == spec.tc_apid


def test_interpreter_enforces_the_declared_ranges(xtce):
    with pytest.raises(ValueError):
        xtce.build_command("SetTmRate", {"period_s": 0.05})
    with pytest.raises(ValueError):
        xtce.build_command("SetTmRate", {"period_s": 61})
    with pytest.raises(ValueError):
        xtce.build_command("SetMode", {"mode": "WARP"})


def test_interpreter_refuses_to_let_the_user_set_assigned_arguments(xtce):
    with pytest.raises(ValueError, match="cannot be set"):
        xtce.build_command("Noop", {"Command_ID": 4})
    with pytest.raises(ValueError, match="abstract"):
        xtce.build_command("MiniSat_TC", {})


def test_reboot_is_marked_vital_and_nothing_else_is(xml_text):
    root = ET.fromstring(xml_text)
    ns = {"x": "http://www.omg.org/spec/XTCE/20180204"}
    marked = {mc.get("name") for mc in root.iterfind(".//x:MetaCommand", ns)
              if mc.find("x:DefaultSignificance", ns) is not None}
    assert marked == {"Reboot"}


def test_every_telemetry_packet_and_command_of_the_spec_is_in_the_database(spec, xtce):
    assert {p.name for p in spec.tm_packets} <= set(xtce.containers)
    assert {c.name for c in spec.commands} <= set(xtce.commands)
    assert {f.name for f in spec.all_tm_fields()} <= set(xtce.params)


def test_no_tabs_or_trailing_spaces_in_generated_file(xml_text):
    assert "\t" not in xml_text and not re.search(r"[ ]+\n", xml_text)
