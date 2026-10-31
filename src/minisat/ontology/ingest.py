"""Telemetry ingestion (ontology.md, TelemetrySample): decode a packet, store every value as a sample, refresh the
spacecraft's newest values. This runs as the ``ingest`` database role, which can do exactly that and nothing else: it cannot
raise alarms or record events. Reacting to telemetry is the job of ``automation.py``, which acts through the action runner
like a person.
"""
from __future__ import annotations

import math
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from ..codec import decode_tm
from ..spec import Spec
from .functions import SequenceTracker
from .runner import utcnow

__all__ = ["IngestResult", "Ingestor", "UnknownSpacecraft", "SharedConnection"]


class UnknownSpacecraft(ValueError):
    """Telemetry arrived for a spacecraft that has not been created (reference data is created by an administrator)."""


class SharedConnection:
    """One long-lived autocommit connection, opened on first use and reopened after a connection error.

    Opening a connection per packet would not keep up with a sped-up simulation. It is used with ``with shared as conn``,
    which also serialises use between threads.
    """

    def __init__(self, connect: Callable[[], Any]):
        self._connect = connect
        self._conn = None
        self._lock = threading.RLock()

    def __enter__(self):
        self._lock.acquire()
        try:
            if self._conn is None or self._conn.closed:
                self._conn = self._connect()
                self._conn.row_factory = dict_row
                self._conn.autocommit = True
            return self._conn
        except BaseException:
            self._lock.release()
            raise

    def __exit__(self, exc_type, exc, tb):
        try:
            if exc_type is not None and issubclass(exc_type, psycopg.OperationalError) and self._conn is not None:
                self._conn.close()                      # the next use reconnects
                self._conn = None
        finally:
            self._lock.release()
        return False

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


@dataclass(frozen=True)
class IngestResult:
    spacecraft_id: str
    packet: str
    apid: int
    seq_count: int
    sc_time_ms: int
    received_at: datetime
    values: Dict[str, float]                 # the values of THIS packet (enum fields as integers)
    previous: Dict[str, float]               # the spacecraft's newest values before this packet
    lost: int = 0                            # packets missing before this one (from the sequence counter)
    duplicate: bool = False                  # this packet was seen before: nothing was stored
    out_of_order: bool = False               # older than a packet already seen: samples kept, newest values left alone
    extra: Dict[str, Any] = field(default_factory=dict)

    @property
    def current(self) -> Dict[str, float]:
        """The spacecraft's newest values after this packet."""
        return self.previous if (self.duplicate or self.out_of_order) else {**self.previous, **self.values}


class Ingestor:
    """Stores the telemetry of one spacecraft. Not thread-safe: feed it from one thread."""

    def __init__(self, spec: Spec, connect: Callable[[], Any], spacecraft_id: str,
                 clock: Callable[[], datetime] = utcnow):
        self.spec = spec
        self.spacecraft_id = spacecraft_id
        self.clock = clock
        self.tracker = SequenceTracker()
        self._db = SharedConnection(connect)
        self._newest_ms: Dict[int, int] = {}

    def close(self) -> None:
        self._db.close()

    def ingest(self, data: bytes) -> IngestResult:
        """Decode and store one packet. A damaged or foreign packet raises ``PacketError`` and stores nothing."""
        tm = decode_tm(self.spec, data)
        received_at = self.clock()
        lost = self.tracker.update(tm.apid, tm.seq_count)
        newest = self._newest_ms.get(tm.apid)
        out_of_order = newest is not None and tm.sc_time_ms < newest
        if not out_of_order:
            self._newest_ms[tm.apid] = tm.sc_time_ms

        rows = [(self.spacecraft_id, name, tm.sc_time_ms, received_at, float(value), tm.seq_count)
                for name, value in tm.values.items()]
        with self._db as conn:
            with conn.transaction():
                row = conn.execute("SELECT latest_values FROM ops.spacecraft WHERE spacecraft_id = %s",
                                   (self.spacecraft_id,)).fetchone()
                if row is None:
                    raise UnknownSpacecraft(f"no spacecraft {self.spacecraft_id!r}; create it with 'minisat db-seed'")
                with conn.cursor() as cur:
                    cur.executemany(
                        "INSERT INTO ops.telemetry_samples (spacecraft_id, parameter_name, sc_time_ms, received_at, value, "
                        "packet_seq_count) VALUES (%s, %s, %s, %s, %s, %s) ON CONFLICT DO NOTHING", rows)
                    stored = cur.rowcount
                duplicate = stored == 0
                # NaN and infinity are valid float32 telemetry but not valid JSON: they stay in the samples only
                finite = {k: v for k, v in tm.values.items() if math.isfinite(v)}
                if duplicate or out_of_order:
                    conn.execute("UPDATE ops.spacecraft SET last_contact_at = %s WHERE spacecraft_id = %s",
                                 (received_at, self.spacecraft_id))
                else:
                    conn.execute("UPDATE ops.spacecraft SET latest_values = latest_values || %s, last_contact_at = %s "
                                 "WHERE spacecraft_id = %s", (Jsonb(finite), received_at, self.spacecraft_id))
        return IngestResult(self.spacecraft_id, tm.packet, tm.apid, tm.seq_count, tm.sc_time_ms, received_at,
                            dict(tm.values), dict(row["latest_values"]), lost, duplicate, out_of_order)
