import copy

import pytest
import yaml

from minisat.spec import SpecError, load_spec, parse_spec

from conftest import SPEC_PATH


@pytest.fixture()
def raw():
    """A fresh, mutable copy of the real specification as a plain dict."""
    return copy.deepcopy(yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8")))


def test_real_spec_loads_with_expected_shape(spec):
    assert spec.mission_name == "MiniSat"
    assert [p.name for p in spec.tm_packets] == ["Housekeeping", "Position"]
    assert [c.name for c in spec.commands] == ["Noop", "SetMode", "SetHeater", "Reboot", "SetTmRate"]
    assert (spec.tm_port, spec.tc_port, spec.tc_apid) == (10015, 10025, 10)
    assert spec.enums["OnOff"] == {"OFF": 0, "ON": 1}        # quoted in the YAML: see the Norway-problem test below


def test_derived_sizes_match_a_hand_count(spec):
    # Housekeeping data field: 8 (time) + mode 1 + 3 x uint16 (6) + uptime 4 + 5 x float32 (20) + eclipse 1 + heater 1 = 41
    assert spec.tm_by_name("Housekeeping").data_size == 41
    assert spec.tm_by_name("Position").data_size == 8 + 3 * 4
    assert spec.command_by_name("Noop").data_size == 2
    assert spec.command_by_name("SetTmRate").data_size == 2 + 4


def test_lookup_helpers(spec):
    assert spec.tm_by_apid(101).name == "Position"
    assert spec.tm_by_apid(5) is None
    assert spec.command_by_id(4).name == "Reboot"
    assert spec.command_by_id(99) is None
    with pytest.raises(KeyError):
        spec.tm_by_name("Nope")


def test_limits_are_parsed(spec):
    soc = next(f for f in spec.all_tm_fields() if f.name == "battery_soc_pct")
    assert soc.limits.warning == (35, None)
    assert soc.limits.critical == (20, None)


def test_yaml_norway_problem_is_detected_with_a_helpful_message(raw):
    # Unquoted ON/OFF are turned into booleans by YAML 1.1; simulate exactly that.
    bad = yaml.safe_load("OnOff: {OFF: 0, ON: 1}")
    assert list(bad["OnOff"]) == [False, True]
    raw["enums"]["OnOff"] = bad["OnOff"]
    with pytest.raises(SpecError, match="quotes"):
        parse_spec(raw)


def mutate(raw, fn):
    fn(raw)
    return raw


@pytest.mark.parametrize("name,change,message", [
    ("missing section", lambda r: r.pop("enums"), "missing section 'enums'"),
    ("bad mission name", lambda r: r["mission"].update(name="Mini Sat"), "identifier"),
    ("same ports", lambda r: r["links"].update(tc_udp_port=10015), "must differ"),
    ("port range", lambda r: r["links"].update(tm_udp_port=70000), "between 1 and 65535"),
    ("duplicate apid", lambda r: r["telemetry"]["packets"][1].update(apid=100), "already used"),
    ("reserved apid", lambda r: r["telemetry"]["packets"][1].update(apid=2045), "reserved"),
    ("tc apid clashes with tm", lambda r: r["telecommand"].update(apid=100), "already used"),
    ("zero period", lambda r: r["telemetry"]["packets"][0].update(period_s=0), "positive"),
    ("unknown type", lambda r: r["telemetry"]["packets"][0]["fields"][0].update(type="uint7"), "unknown type"),
    ("unknown enum", lambda r: r["telemetry"]["packets"][0]["fields"][0].update(enum="Nope"), "unknown enum"),
    ("enum does not fit", lambda r: r["enums"]["Mode"].update(HUGE=300), "does not fit"),
    ("float enum", lambda r: r["telemetry"]["packets"][0]["fields"][5].update(enum="Mode"), "integer type"),
    ("duplicate enum value", lambda r: r["enums"]["Mode"].update(OTHER=0), "used twice"),
    ("duplicate field name across packets", lambda r: r["telemetry"]["packets"][1]["fields"][0].update(name="mode"),
     "unique across ALL packets"),
    ("reserved field name", lambda r: r["telemetry"]["packets"][1]["fields"][0].update(name="sc_time_ms"), "reserved"),
    ("limits inverted", lambda r: r["telemetry"]["packets"][0]["fields"][5].update(limits={"warning": [9, 8]}),
     "smaller than maximum"),
    ("critical inside warning", lambda r: r["telemetry"]["packets"][0]["fields"][5].update(
        limits={"warning": [6.0, 8.0], "critical": [6.5, 7.5]}), "must contain"),
    ("range on telemetry", lambda r: r["telemetry"]["packets"][0]["fields"][5].update(range=[0, 1]), "only makes sense"),
    ("limits on command arg", lambda r: r["telecommand"]["commands"][4]["args"][0].update(limits={"warning": [1, 2]}),
     "only make sense"),
    ("duplicate command id", lambda r: r["telecommand"]["commands"][1].update(id=1), "used twice"),
    ("command id zero", lambda r: r["telecommand"]["commands"][0].update(id=0), "1..65535"),
    ("bad significance", lambda r: r["telecommand"]["commands"][3].update(significance="scary"), "significance"),
    ("duplicate argument", lambda r: r["telecommand"]["commands"][1]["args"].append(
        {"name": "mode", "type": "uint8"}), "unique within a command"),
    ("no commands", lambda r: r["telecommand"].update(commands=[]), "at least one command"),
    ("packet without fields", lambda r: r["telemetry"]["packets"][1].update(fields=[]), "at least one field"),
])
def test_invalid_specifications_are_rejected_with_a_clear_message(raw, name, change, message):
    change(raw)
    with pytest.raises(SpecError, match=message):
        parse_spec(raw, source="test.yaml")


def test_error_messages_say_where_the_problem_is(raw):
    raw["telemetry"]["packets"][0]["fields"][0]["type"] = "uint7"
    with pytest.raises(SpecError) as info:
        parse_spec(raw, source="my.yaml")
    assert "my.yaml" in str(info.value) and "Housekeeping" in str(info.value)


def test_invalid_yaml_text_is_reported(tmp_path):
    f = tmp_path / "bad.yaml"
    f.write_text("mission: [unclosed", encoding="utf-8")
    with pytest.raises(SpecError, match="not valid YAML"):
        load_spec(f)
