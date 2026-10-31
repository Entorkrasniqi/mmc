import dataclasses

import pytest
import yaml

from minisat.ontology.definitions import NORMAL, VITAL, definitions_from_spec, load_definitions

from conftest import SPEC_PATH


@pytest.fixture(scope="module")
def defs():
    return load_definitions(SPEC_PATH)


@pytest.fixture(scope="module")
def raw_yaml():
    """The specification read straight from the file, without minisat.spec, as an independent reference."""
    return yaml.safe_load(SPEC_PATH.read_text(encoding="utf-8"))


def test_every_parameter_in_the_yaml_is_a_definition_in_wire_order(defs, raw_yaml):
    for packet in raw_yaml["telemetry"]["packets"]:
        expected = [f["name"] for f in packet["fields"]]
        assert [p.name for p in defs.packet_parameters(packet["apid"])] == expected
        assert list(defs.packet_type(packet["apid"]).parameter_names) == expected
    assert len(defs.parameters) == 12 + 3


def test_packet_sizes_are_counted_by_hand(defs):
    # primary header 6 + time 8 + Housekeeping fields 33 (1 + 3x2 + 4 + 5x4 + 1 + 1)  = 47, as in the README
    assert defs.packet_type(100).size_bytes == 47
    assert defs.packet_type(101).size_bytes == 6 + 8 + 3 * 4
    assert defs.packet_type(100).period_s == 1.0
    assert defs.packet_type(101).period_s == 5.0


def test_alarm_limits_are_carried_over_from_the_yaml(defs):
    soc = defs.parameter("battery_soc_pct")
    assert (soc.warning_low, soc.warning_high) == (35, None)
    assert (soc.critical_low, soc.critical_high) == (20, None)
    assert soc.unit == "%"
    voltage = defs.parameter("battery_voltage")
    assert (voltage.warning, voltage.critical) == ((6.8, 8.5), (6.4, 8.6))
    assert defs.parameter("solar_current_a").warning is None          # no limits given in the specification


@pytest.mark.parametrize("value, expected", [
    (90.0, None), (35.0, None),                       # the boundary itself is still fine ("minInclusive")
    (34.999, "WARNING"), (20.0, "WARNING"),
    (19.999, "CRITICAL"), (0.0, "CRITICAL"),
])
def test_severity_of_follows_the_xtce_meaning_of_the_ranges(defs, value, expected):
    assert defs.parameter("battery_soc_pct").severity_of(value) == expected


def test_severity_of_handles_both_sides(defs):
    t = defs.parameter("battery_temp_c")                  # warning [0, 35], critical [-5, 45]
    assert [t.severity_of(v) for v in (12, 36, 46, -1, -6)] == [None, "WARNING", "CRITICAL", "WARNING", "CRITICAL"]
    assert defs.parameter("solar_current_a").severity_of(1e9) is None


def test_enum_parameters_list_their_labels_in_value_order(defs):
    mode = defs.parameter("mode")
    assert mode.enum_name == "Mode"
    assert mode.enum_labels == (("SAFE", 0), ("NOMINAL", 1), ("PAYLOAD", 2))
    assert defs.parameter("heater").enum_labels == (("OFF", 0), ("ON", 1))        # the quoted-label (Norway) enum
    assert defs.parameter("battery_voltage").enum_labels is None


def test_commands_and_their_significance(defs):
    assert [c.name for c in defs.commands] == ["Noop", "SetMode", "SetHeater", "Reboot", "SetTmRate"]
    assert defs.command("Reboot").significance == VITAL and defs.command("Reboot").is_vital
    assert all(c.significance == NORMAL for c in defs.commands if c.name != "Reboot")
    assert defs.command(2) is defs.command("SetMode")


def test_command_arguments_carry_ranges_and_enums(defs):
    (arg,) = defs.command("SetTmRate").arguments
    assert (arg.name, arg.data_type, arg.unit) == ("period_s", "float32", "s")
    assert (arg.range_min, arg.range_max) == (0.1, 60)
    (mode_arg,) = defs.command("SetMode").arguments
    assert mode_arg.enum_labels == (("SAFE", 0), ("NOMINAL", 1), ("PAYLOAD", 2))
    assert defs.command("Noop").arguments == ()


def test_unknown_names_raise_key_error(defs):
    for lookup, arg in ((defs.parameter, "nope"), (defs.packet_type, 7), (defs.command, "Explode"), (defs.command, 99)):
        with pytest.raises(KeyError):
            lookup(arg)


def test_definitions_are_read_only(defs):
    with pytest.raises(dataclasses.FrozenInstanceError):
        defs.command("Reboot").significance = NORMAL
    with pytest.raises(dataclasses.FrozenInstanceError):
        defs.parameter("battery_soc_pct").warning = None
    assert isinstance(defs.parameters, tuple) and isinstance(defs.commands, tuple)


def test_built_from_a_spec_object_gives_the_same_result(spec, defs):
    assert definitions_from_spec(spec) == defs
