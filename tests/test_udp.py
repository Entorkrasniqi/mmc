"""End-to-end test over real UDP sockets on the loopback interface: a simulator, a fake ground station, a command."""
import socket
import threading
import time

import pytest

from minisat.codec import decode_tm, encode_tc
from minisat.model import Spacecraft
from minisat.simulator import UdpSimulator


def receiver():
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind(("127.0.0.1", 0))
    sock.settimeout(0.5)
    return sock


def test_telemetry_flows_out_and_a_command_flows_in(spec, tmp_path):
    rx = receiver()
    record = open(tmp_path / "tm.bin", "wb")
    sim = UdpSimulator(spec, Spacecraft(soc=0.9), tm_addr=rx.getsockname(), tc_bind=("127.0.0.1", 0), speedup=20.0,
                       record=record)
    thread = threading.Thread(target=sim.run, kwargs={"duration_s": 6.0}, daemon=True)
    thread.start()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    seen, heater_on = [], False
    deadline = time.monotonic() + 5.0
    sent = False
    try:
        while time.monotonic() < deadline and not heater_on:
            try:
                data, _ = rx.recvfrom(4096)
            except socket.timeout:
                continue
            tm = decode_tm(spec, data)
            seen.append(tm)
            if not sent and tm.packet == "Housekeeping" and tm.seq_count >= 3:
                tx.sendto(encode_tc(spec, "SetHeater", {"state": "ON"}), sim.tc_address)
                sent = True
            if tm.packet == "Housekeeping" and tm.values["heater"] == 1:
                heater_on = True
    finally:
        sim.stop()
        thread.join(timeout=5)
        rx.close()
        tx.close()
    assert sent and heater_on, "the heater-on command never showed up in telemetry"
    hk_counts = [t.seq_count for t in seen if t.packet == "Housekeeping"]
    assert hk_counts == list(range(hk_counts[0], hk_counts[0] + len(hk_counts)))    # nothing lost or reordered on loopback
    assert seen[-1].values.get("cmd_accepted", 1) >= 1
    assert not thread.is_alive()
    assert (tmp_path / "tm.bin").stat().st_size >= 47 * len(hk_counts)               # the recording holds what was sent


def test_speedup_must_be_positive(spec):
    with pytest.raises(ValueError):
        UdpSimulator(spec, Spacecraft(), tm_addr=("127.0.0.1", 9), tc_bind=("127.0.0.1", 0), speedup=0)


def test_simulated_time_follows_the_wall_clock_times_speedup(spec):
    rx = receiver()
    sim = UdpSimulator(spec, Spacecraft(), tm_addr=rx.getsockname(), tc_bind=("127.0.0.1", 0), speedup=100.0)
    started = time.monotonic()
    sim.run(duration_s=0.5)
    rx.close()
    wall = time.monotonic() - started
    # about 50 simulated seconds in half a second; generous margins so that a busy CI machine does not make this flaky
    assert 25 <= sim.sim.t <= 100 * wall + 5


def test_garbage_datagram_does_not_stop_the_simulator(spec):
    rx = receiver()
    log = []
    sim = UdpSimulator(spec, Spacecraft(), tm_addr=rx.getsockname(), tc_bind=("127.0.0.1", 0), speedup=10.0, log=log.append)
    thread = threading.Thread(target=sim.run, kwargs={"duration_s": 1.5}, daemon=True)
    thread.start()
    tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    tx.sendto(b"definitely not a CCSDS packet", sim.tc_address)
    tx.sendto(encode_tc(spec, "Noop"), sim.tc_address)
    thread.join(timeout=5)
    tx.close(), rx.close()
    assert not thread.is_alive()
    assert sim.sim.model.cmd_rejected == 1 and sim.sim.model.cmd_accepted == 1
    assert any("malformed" in line for line in log)
