"""The Yamcs configuration files cannot be executed in the test suite (that needs Yamcs and Maven), but the numbers in
them that must agree with the specification and the packet layout can be checked: ports, time offset, time unit, file names.
Everything else in these files is plain Yamcs configuration; see the README for how it was checked."""
import xml.etree.ElementTree as ET

import pytest
import yaml

from minisat.ccsds import PRIMARY_HEADER_SIZE
from minisat.codec import decode_tm, encode_tm

from conftest import ROOT, XTCE_PATH
from test_codec import HK_VALUES

ETC = ROOT / "yamcs" / "src" / "main" / "yamcs" / "etc"


@pytest.fixture(scope="module")
def instance():
    return yaml.safe_load((ETC / "yamcs.minisat.yaml").read_text(encoding="utf-8"))


def link(instance, name):
    return next(l for l in instance["dataLinks"] if l["name"] == name)


def test_ports_match_the_specification(spec, instance):
    assert link(instance, "tm-in")["port"] == spec.tm_port
    assert link(instance, "tc-out")["port"] == spec.tc_port


def test_telemetry_link_reads_the_spacecraft_clock_where_the_codec_writes_it(spec, instance):
    args = link(instance, "tm-in")["packetPreprocessorArgs"]
    assert args["timestampOffset"] == PRIMARY_HEADER_SIZE                 # right after the 6-byte primary header
    enc = args["timeEncoding"]
    assert (enc["epoch"], enc["type"], enc["size"], enc["multiplier"]) == ("UNIX", "FIXED", 8, 1)   # ms since 1970, 64 bit
    # and the codec really puts the 64-bit big-endian millisecond clock at that offset
    packet = encode_tm(spec, "Housekeeping", HK_VALUES, 1_792_800_000_123, 1)
    offset = args["timestampOffset"]
    assert int.from_bytes(packet[offset:offset + 8], "big") == 1_792_800_000_123 == decode_tm(spec, packet).sc_time_ms


def test_built_in_classes_only_no_custom_java(instance):
    assert link(instance, "tm-in")["packetPreprocessorClassName"] == "org.yamcs.tctm.GenericPacketPreprocessor"
    assert link(instance, "tc-out")["commandPostprocessorClassName"] == "org.yamcs.tctm.GenericCommandPostprocessor"
    assert not list((ROOT / "yamcs").rglob("*.java"))


def test_mission_database_file_exists_where_the_config_points(instance):
    file = instance["mdb"][0]["args"]["file"]
    assert (ETC.parent / file) == XTCE_PATH and XTCE_PATH.exists()
    assert instance["mdb"][0]["type"] == "xtce"


def test_instance_is_listed_in_the_server_config():
    server = yaml.safe_load((ETC / "yamcs.yaml").read_text(encoding="utf-8"))
    assert server["instances"] == ["minisat"] and (ETC / "yamcs.minisat.yaml").exists()
    http = next(s for s in server["services"] if s["class"] == "org.yamcs.http.HttpServer")
    assert http["args"]["address"] == "127.0.0.1"                         # no login configured: stay local


def test_alarm_checking_is_enabled_in_the_processor():
    proc = yaml.safe_load((ETC / "processor.yaml").read_text(encoding="utf-8"))
    assert proc["realtime"]["config"]["alarm"]["parameterCheck"] is True


def test_maven_project_is_wellformed_and_pins_the_yamcs_version():
    ns = {"m": "http://maven.apache.org/POM/4.0.0"}
    pom = ET.parse(ROOT / "yamcs" / "pom.xml").getroot()
    assert pom.find("m:properties/m:yamcsVersion", ns).text == "5.13.7"
    deps = {d.find("m:artifactId", ns).text for d in pom.findall("m:dependencies/m:dependency", ns)}
    assert deps == {"yamcs-core", "yamcs-web"}
