"""The outbox worker: delivers the side effects that actions queued (protocols/action-runner-and-audit.md).

Telecommands are delivered AT MOST ONCE, deliberately. The worker first claims a message, then records the command as SENT
(an audited action, which also completes the message), and only then puts the bytes on the link. If the worker dies in
between, the command is shown as SENT but never went out and ends up FAILED when no answer comes; nothing re-sends it.
A command must never be sent twice by accident, least of all a vital one (protocols/command-safety-protocol.md): an operator
decides whether to propose it again.
"""
from __future__ import annotations

import socket
from datetime import datetime, timedelta
from typing import Callable, Optional

from .ingest import SharedConnection
from .runner import ActionError, ActionRunner, utcnow

__all__ = ["UdpLink", "OutboxWorker"]

TOPICS = ("send_telecommand", "notify_supervisors")


class UdpLink:
    """Sends each telecommand as one UDP datagram (the way the simulator and Yamcs expect them)."""

    def __init__(self, host: str, port: int):
        self.address = (host, port)
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

    def send(self, data: bytes) -> None:
        self._socket.sendto(data, self.address)

    def close(self) -> None:
        self._socket.close()


class OutboxWorker:
    def __init__(self, connect: Callable, runner: ActionRunner, link, system_operator: str = "automation",
                 notify: Optional[Callable[[dict], None]] = None, clock: Callable[[], datetime] = utcnow,
                 log: Optional[Callable[[str], None]] = None, lease_s: float = 60.0):
        self._db = SharedConnection(connect)
        self.runner = runner
        self.link = link
        self.operator = system_operator
        self.notify = notify or (lambda payload: None)
        self.clock = clock
        self.log = log or (lambda message: None)
        self.lease = timedelta(seconds=lease_s)

    def close(self) -> None:
        self._db.close()

    def run_once(self) -> int:
        """Handle every message that is due. Returns how many were handled."""
        handled = 0
        while True:
            message = self._claim()
            if message is None:
                return handled
            handled += 1
            if message["topic"] == "send_telecommand":
                self._send(message)
            else:
                self._notify(message)

    def _claim(self) -> Optional[dict]:
        """Take one due message. Its availability is pushed forward (a lease) so that no other worker takes it as well."""
        now = self.clock()
        with self._db as conn:
            with conn.transaction():
                return conn.execute(
                    "UPDATE ops.outbox SET attempts = attempts + 1, available_at = %s WHERE outbox_id = ("
                    "SELECT outbox_id FROM ops.outbox WHERE processed_at IS NULL AND available_at <= %s "
                    "AND topic = ANY(%s) ORDER BY outbox_id LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *",
                    (now + self.lease, now, list(TOPICS))).fetchone()

    def _finish(self, message: dict, error: Optional[str] = None) -> None:
        with self._db as conn:
            conn.execute("UPDATE ops.outbox SET processed_at = %s, last_error = %s WHERE outbox_id = %s",
                         (self.clock(), error, message["outbox_id"]))

    def _send(self, message: dict) -> None:
        payload = message["payload"]
        try:                                                    # marks the command SENT and completes the message
            self.runner.run(self.operator, "Record Command Sent",
                            {"execution_id": payload["execution_id"], "outbox_id": message["outbox_id"]},
                            correlation_id=message["correlation_id"])
        except ActionError as exc:                              # for example it is no longer RELEASED: do not send
            self.log(f"worker: not sending {payload['command']} ({payload['execution_id']}): {exc}")
            self._finish(message, str(exc))
            return
        try:
            self.link.send(bytes.fromhex(payload["raw_bytes_hex"]))
            self.log(f"worker: sent {payload['command']} ({payload['execution_id']})")
        except OSError as exc:                                  # SENT in the books, never left: it will fail on timeout
            self.log(f"worker: the link refused {payload['command']} ({payload['execution_id']}): {exc}")
            with self._db as conn:
                conn.execute("UPDATE ops.outbox SET last_error = %s WHERE outbox_id = %s", (str(exc), message["outbox_id"]))

    def _notify(self, message: dict) -> None:
        try:
            self.notify(message["payload"])
            self._finish(message)
        except Exception as exc:                                # noqa: BLE001 - a broken notifier must not stop commanding
            self.log(f"worker: notification failed: {exc}")
            self._finish(message, f"{type(exc).__name__}: {exc}")
