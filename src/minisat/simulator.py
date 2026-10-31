"""The simulator: runs the spacecraft model in time, emits telemetry packets and obeys telecommands.

Two layers, so the logic can be tested without any network:

* :class:`Simulator` - pure logic. ``advance(seconds)`` moves simulated time forward and hands every due telemetry packet
  to a ``send_tm`` callback; ``handle_telecommand(bytes)`` processes one command packet.
* :class:`UdpSimulator` - the real-time wrapper: sends telemetry as UDP datagrams, listens for telecommands on a UDP port,
  and paces simulated time against the wall clock (optionally faster with ``speedup``).
"""
from __future__ import annotations

import socket
import threading
import time
from typing import BinaryIO, Callable, Dict, Optional

from .ccsds import PacketError
from .codec import decode_tc, encode_tm
from .model import Spacecraft
from .spec import Spec

__all__ = ["Simulator", "UdpSimulator"]

MAX_STEP_S = 1.0     # physics is stepped in slices no longer than this


class Simulator:
    def __init__(self, spec: Spec, model: Spacecraft, send_tm: Callable[[bytes], None], epoch_ms: int,
                 log: Optional[Callable[[str], None]] = None):
        self.spec = spec
        self.model = model
        self.send_tm = send_tm
        self.epoch_ms = epoch_ms                      # spacecraft clock at simulated t = 0 (ms since 1970)
        self.log = log or (lambda msg: None)
        self.t = model.t
        self._seq: Dict[int, int] = {}                # next sequence count per APID
        self._next_due = {p.name: self.t for p in spec.tm_packets}    # everything is due immediately at start
        self.packets_sent = 0

    # ---------------------------------------------------------------- telemetry

    def _period(self, name: str) -> float:
        if name == "Housekeeping":                    # the only packet whose rate a command can change
            return self.model.hk_period_s
        return self.spec.tm_by_name(name).period_s

    def _emit(self, name: str) -> None:
        pkt = self.spec.tm_by_name(name)
        values = self.model.housekeeping() if name == "Housekeeping" else self.model.position()
        count = self._seq.get(pkt.apid, 0)
        self._seq[pkt.apid] = (count + 1) & 0x3FFF   # 14-bit counter wraps around
        sc_time_ms = self.epoch_ms + int(round(self.t * 1000.0))
        self.send_tm(encode_tm(self.spec, name, values, sc_time_ms, count))
        self.packets_sent += 1

    def advance(self, dt: float) -> None:
        """Move simulated time forward by ``dt`` seconds, emitting every packet that falls due on the way."""
        end = self.t + dt
        while True:
            # packets that are due right now (this also sends the very first ones at t = start)
            for pkt in self.spec.tm_packets:
                if self._next_due[pkt.name] <= self.t + 1e-9:
                    self._emit(pkt.name)
                    self._next_due[pkt.name] = max(self._next_due[pkt.name] + self._period(pkt.name),
                                                   self.t + 1e-6)
            if self.t >= end - 1e-9:
                break
            step_to = min(end, self.t + MAX_STEP_S, min(self._next_due.values()))
            self.model.step(step_to - self.t)
            self.t = step_to

    # ---------------------------------------------------------------- telecommands

    def handle_telecommand(self, packet: bytes) -> bool:
        """Process one telecommand packet. Returns True if the command was accepted."""
        try:
            cmd, args, _ = decode_tc(self.spec, packet)
        except PacketError as exc:
            self.model.reject()
            self.log(f"t={self.t:8.1f}s  REJECT malformed telecommand: {exc}")
            return False
        accepted, reason = self.model.handle_command(cmd, args)
        self.log(f"t={self.t:8.1f}s  {'ACCEPT' if accepted else 'REJECT'} {cmd.name} {args}  ({reason})")
        if accepted and cmd.name == "SetTmRate":
            self._next_due["Housekeeping"] = min(self._next_due["Housekeeping"], self.t + self.model.hk_period_s)
        return accepted


class UdpSimulator:
    """Real-time wrapper around :class:`Simulator` using UDP sockets (no connection set-up: each packet is a datagram)."""

    def __init__(self, spec: Spec, model: Spacecraft, tm_addr, tc_bind, speedup: float = 1.0,
                 record: Optional[BinaryIO] = None, log: Optional[Callable[[str], None]] = None,
                 epoch_ms: Optional[int] = None):
        if speedup <= 0:
            raise ValueError("speedup must be positive")
        self.speedup = speedup
        self.record = record
        self._tm_addr = tm_addr
        self._tm_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._tc_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._tc_socket.bind(tc_bind)
        self._tc_socket.settimeout(0.1)
        self.tc_address = self._tc_socket.getsockname()        # useful when binding to port 0 (tests)
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._tc_thread: Optional[threading.Thread] = None
        self.sim = Simulator(spec, model, self._send_tm, epoch_ms if epoch_ms is not None else int(time.time() * 1000),
                             log=log)

    def _send_tm(self, packet: bytes) -> None:
        self._tm_socket.sendto(packet, self._tm_addr)
        if self.record is not None:
            self.record.write(packet)

    def _tc_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _ = self._tc_socket.recvfrom(4096)
            except socket.timeout:
                continue
            except OSError:
                return                                           # socket closed during shutdown
            with self._lock:
                self.sim.handle_telecommand(data)

    def run(self, duration_s: Optional[float] = None) -> None:
        """Run until ``duration_s`` WALL-CLOCK seconds have passed (forever if None) or :meth:`stop` is called.

        Simulated time follows the wall clock multiplied by ``speedup``; the loop wakes every few milliseconds,
        works out how far simulated time is behind, and advances the simulation to catch up.
        """
        self._tc_thread = threading.Thread(target=self._tc_loop, name="tc-listener", daemon=True)
        self._tc_thread.start()
        started = time.monotonic()
        sim_start = self.sim.t
        try:
            while not self._stop.is_set():
                elapsed = time.monotonic() - started
                if duration_s is not None and elapsed >= duration_s:
                    break
                with self._lock:
                    behind = sim_start + elapsed * self.speedup - self.sim.t
                    if behind > 0:
                        self.sim.advance(behind)
                time.sleep(0.005)
        finally:
            self.close()

    def stop(self) -> None:
        self._stop.set()

    def close(self) -> None:
        self._stop.set()
        if self._tc_thread is not None:
            self._tc_thread.join(timeout=1.0)
        self._tm_socket.close()
        self._tc_socket.close()
        if self.record is not None:
            self.record.flush()
