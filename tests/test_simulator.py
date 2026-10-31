import pytest

from minisat.ccsds import build_packet, TC
from minisat.codec import decode_tm, encode_tc
from minisat.model import MODE_PAYLOAD, Spacecraft
from minisat.simulator import Simulator

EPOCH = 1_792_800_000_000


def make(spec, **kw):
    packets, log = [], []
    sim = Simulator(spec, Spacecraft(**kw), packets.append, epoch_ms=EPOCH, log=log.append)
    return sim, packets, log


def decoded(spec, packets, name=None):
    tms = [decode_tm(spec, p) for p in packets]
    return [t for t in tms if name is None or t.packet == name]


def test_first_packets_are_sent_immediately_then_on_schedule(spec):
    sim, packets, _ = make(spec)
    sim.advance(10)
    hk, pos = decoded(spec, packets, "Housekeeping"), decoded(spec, packets, "Position")
    assert [t.sc_time_ms - EPOCH for t in hk] == [i * 1000 for i in range(11)]       # t = 0, 1, ... 10 s
    assert [t.sc_time_ms - EPOCH for t in pos] == [0, 5000, 10000]
    assert [t.seq_count for t in hk] == list(range(11)) and [t.seq_count for t in pos] == [0, 1, 2]
    assert sim.packets_sent == 14 == len(packets)


def test_each_apid_has_its_own_sequence_counter_and_it_wraps_at_14_bits(spec):
    sim, packets, _ = make(spec)
    sim._seq[100] = 16383
    sim.advance(2)
    assert [t.seq_count for t in decoded(spec, packets, "Housekeeping")] == [16383, 0, 1]
    assert [t.seq_count for t in decoded(spec, packets, "Position")] == [0]


def test_advancing_in_one_step_or_many_gives_the_same_telemetry(spec):
    one, p1, _ = make(spec, seed=5)
    many, p2, _ = make(spec, seed=5)
    one.advance(1200)
    for _ in range(1200):
        many.advance(1)
    assert [t.sc_time_ms for t in decoded(spec, p1)] == [t.sc_time_ms for t in decoded(spec, p2)]
    a, b = decoded(spec, p1, "Housekeeping")[-1], decoded(spec, p2, "Housekeeping")[-1]
    assert a.values["battery_soc_pct"] == pytest.approx(b.values["battery_soc_pct"], abs=1e-3)
    assert a.values["battery_temp_c"] == pytest.approx(b.values["battery_temp_c"], abs=0.2)


def test_time_inside_a_step_is_respected(spec):
    sim, packets, _ = make(spec)
    sim.advance(2.5)
    assert sim.t == pytest.approx(2.5)
    assert len(decoded(spec, packets, "Housekeeping")) == 3                          # 0, 1, 2 - not yet 3
    sim.advance(0.5)
    assert len(decoded(spec, packets, "Housekeeping")) == 4


def test_telemetry_reflects_the_model(spec):
    sim, packets, _ = make(spec, soc=0.42)
    sim.advance(1)
    hk = decoded(spec, packets, "Housekeeping")[-1].values
    assert hk["battery_soc_pct"] == pytest.approx(42.0, abs=0.1) and hk["mode"] == 1
    assert decoded(spec, packets, "Position")[-1].values["altitude_km"] == pytest.approx(560.0)


def test_accepted_command_changes_the_next_telemetry(spec):
    sim, packets, log = make(spec, soc=0.9)
    sim.advance(2)
    assert sim.handle_telecommand(encode_tc(spec, "SetMode", {"mode": "PAYLOAD"}))
    sim.advance(1)
    last = decoded(spec, packets, "Housekeeping")[-1].values
    assert (last["mode"], last["cmd_accepted"], last["last_cmd_id"]) == (MODE_PAYLOAD, 1, 2)
    assert any("ACCEPT SetMode" in line for line in log)


def test_rejected_command_is_counted_and_logged_with_a_reason(spec):
    sim, packets, log = make(spec, soc=0.1)
    assert not sim.handle_telecommand(encode_tc(spec, "SetMode", {"mode": "PAYLOAD"}))
    sim.advance(1)
    assert decoded(spec, packets, "Housekeeping")[-1].values["cmd_rejected"] == 1
    assert any("REJECT SetMode" in line and "battery too low" in line for line in log)


@pytest.mark.parametrize("garbage", [b"", b"\x00\x01\x02", b"\xff" * 40, build_packet(TC, 10, 0, b"\x00\x63"),
                                     build_packet(TC, 11, 0, b"\x00\x01"), build_packet(TC, 10, 0, b"\x00\x02")])
def test_garbage_never_crashes_the_simulator_and_counts_as_rejected(spec, garbage):
    sim, packets, log = make(spec)
    assert sim.handle_telecommand(garbage) is False
    assert sim.model.cmd_rejected == 1 and "malformed" in log[-1]


def test_changing_the_housekeeping_rate_takes_effect_at_once(spec):
    sim, packets, _ = make(spec)
    sim.advance(1)
    sim.handle_telecommand(encode_tc(spec, "SetTmRate", {"period_s": 10.0}))
    packets.clear()
    sim.advance(30)
    times = [t.sc_time_ms - EPOCH for t in decoded(spec, packets, "Housekeeping")]
    assert times[1:] == [times[0] + 10000 * k for k in range(1, len(times))]          # 10 s apart from now on
    assert 3 <= len(times) <= 4


def test_reboot_restarts_uptime_in_the_telemetry(spec):
    sim, packets, _ = make(spec)
    sim.advance(120)
    sim.handle_telecommand(encode_tc(spec, "Reboot"))
    sim.advance(3)
    uptimes = [t.values["uptime_s"] for t in decoded(spec, packets, "Housekeeping")]
    assert uptimes[119] >= 119 and uptimes[-1] <= 3 and decoded(spec, packets, "Housekeeping")[-1].values["mode"] == 0


def test_every_packet_the_simulator_emits_is_valid_for_the_codec(spec):
    sim, packets, _ = make(spec)
    sim.advance(3600)
    assert len(packets) > 3600 and all(len(p) in (47, 26) for p in packets)
