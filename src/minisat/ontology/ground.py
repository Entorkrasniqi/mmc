"""The ground side, assembled: listen for telemetry on UDP, store it, react to it, and deliver queued telecommands.

    UDP telemetry -> Ingestor (ingest role) -> AutomationEngine (SYSTEM operator via the action runner)
    outbox -> OutboxWorker -> UdpLink -> UDP telecommands

Two threads: one receives and processes telemetry, one runs the outbox worker and the time-based automations. A problem
with one packet or one database call is logged and does not stop the station.
"""
from __future__ import annotations

import socket
import threading
from typing import Callable, Optional

import psycopg

from ..ccsds import PacketError
from ..spec import Spec
from .actions import default_registry
from .automation import AutomationConfig, AutomationEngine
from .ingest import Ingestor, UnknownSpacecraft
from .runner import ActionRunner, RunnerConfig, utcnow
from .worker import OutboxWorker, UdpLink

__all__ = ["GroundStation", "build_ground_station"]


class GroundStation:
    def __init__(self, spec: Spec, spacecraft_id: str, ingestor: Ingestor, engine: AutomationEngine, worker: OutboxWorker,
                 tm_bind=("127.0.0.1", 0), tick_s: float = 0.25, log: Optional[Callable[[str], None]] = None):
        self.spec, self.spacecraft_id = spec, spacecraft_id
        self.ingestor, self.engine, self.worker = ingestor, engine, worker
        self.tick_s = tick_s
        self.log = log or (lambda message: None)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.bind(tm_bind)
        self._socket.settimeout(0.1)
        self.tm_address = self._socket.getsockname()           # useful when binding to port 0 (tests)
        self._stop = threading.Event()
        self._threads = []
        self.packets = 0

    # ---------------------------------------------------------------------------------------------- one packet
    def process(self, data: bytes) -> None:
        """Store one telemetry packet and let the automations react. Never raises for bad data or a database hiccup."""
        try:
            result = self.ingestor.ingest(data)
            self.engine.on_telemetry(result)
            self.packets += 1
        except PacketError as exc:
            self.log(f"ground: bad packet ({len(data)} bytes): {exc}")
        except UnknownSpacecraft as exc:
            self.log(f"ground: {exc}")
        except psycopg.Error as exc:
            self.log(f"ground: database problem while processing a packet: {exc}")

    # ---------------------------------------------------------------------------------------------- threads
    def _receive_loop(self) -> None:
        while not self._stop.is_set():
            try:
                data, _ = self._socket.recvfrom(65535)
            except socket.timeout:
                continue
            except OSError:
                return                                          # socket closed during shutdown
            self.process(data)

    def _timer_loop(self) -> None:
        while not self._stop.wait(self.tick_s):
            try:
                self.worker.run_once()
                self.engine.tick(self.spacecraft_id)
            except psycopg.Error as exc:
                self.log(f"ground: database problem in the timer loop: {exc}")

    def start(self) -> None:
        self._threads = [threading.Thread(target=self._receive_loop, name="telemetry", daemon=True),
                         threading.Thread(target=self._timer_loop, name="timers", daemon=True)]
        for t in self._threads:
            t.start()

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2.0)
        self._socket.close()
        for part in (self.ingestor, self.engine, self.worker):
            part.close()
        close = getattr(self.worker.link, "close", None)
        if close:
            close()

    def run(self, duration_s: Optional[float] = None) -> None:
        """Run until ``duration_s`` seconds have passed (forever if None) or :meth:`stop` is called from another thread."""
        self.start()
        try:
            self._stop.wait(duration_s)
        finally:
            self.stop()


def build_ground_station(spec: Spec, spacecraft_id: str, connect: Callable[[str], object], tc_addr, tm_bind=("127.0.0.1", 0),
                         system_operator: str = "automation", clock=utcnow, runner_config: Optional[RunnerConfig] = None,
                         automation_config: Optional[AutomationConfig] = None,
                         log: Optional[Callable[[str], None]] = None, notify=None) -> GroundStation:
    """Wire everything together. ``connect(role)`` opens a connection as ``"runner"`` or ``"ingest"``."""
    log = log or (lambda message: None)
    runner = ActionRunner(lambda: connect("runner"), spec, default_registry(), config=runner_config, clock=clock)
    ingestor = Ingestor(spec, lambda: connect("ingest"), spacecraft_id, clock=clock)
    engine = AutomationEngine(spec, runner, lambda: connect("runner"), system_operator, clock, automation_config, log)
    worker = OutboxWorker(lambda: connect("runner"), runner, UdpLink(*tc_addr), system_operator, notify, clock, log)
    return GroundStation(spec, spacecraft_id, ingestor, engine, worker, tm_bind=tm_bind, log=log)
