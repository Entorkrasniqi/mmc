"""Prometheus metrics (protocols/observability-and-operations.md).

Two kinds. What the API itself sees (requests, actions by name and outcome, how long they took) is counted as it happens.
What the database knows (alarms by severity, commands by state, the age of the newest telemetry, the outbox backlog, packet
loss) is read at scrape time, so it is right even when the API was restarted.

Not here, because this process cannot see them: decode errors and packets per APID of the ground station (a separate
process; samples do not record the APID).
"""
from __future__ import annotations

import logging
from datetime import datetime
from typing import Callable, Iterable

import psycopg
from prometheus_client import CollectorRegistry, Counter, Histogram
from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily

from .store import Store

__all__ = ["ApiMetrics"]

log = logging.getLogger("minisat.api.metrics")
LATENCY_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0)


class _DatabaseCollector:
    def __init__(self, store: Store, clock: Callable[[], datetime]):
        self.store, self.clock = store, clock

    def collect(self) -> Iterable:
        up = GaugeMetricFamily("minisat_database_up", "1 if the API can read the database")
        try:
            families = self._read()
            up.add_metric([], 1)
        except psycopg.Error as exc:                     # the scrape still answers, and says the database is down
            log.warning("metrics: the database could not be read: %s", exc)
            families = []
            up.add_metric([], 0)
        yield up
        yield from families

    def _read(self):
        now = self.clock()
        with self.store.session() as conn:
            def rows(query):
                return conn.execute(query).fetchall()

            alarms = GaugeMetricFamily("minisat_alarms_open", "Alarms that are not cleared", labels=["spacecraft_id", "severity", "state"])
            for r in rows("SELECT spacecraft_id, severity, state, count(*) AS n FROM ops.alarm WHERE state <> 'CLEARED' "
                          "GROUP BY 1, 2, 3"):
                alarms.add_metric([r["spacecraft_id"], r["severity"], r["state"]], r["n"])

            commands = GaugeMetricFamily("minisat_commands", "Command executions by lifecycle state", labels=["spacecraft_id", "status"])
            for r in rows("SELECT spacecraft_id, status, count(*) AS n FROM ops.command_execution GROUP BY 1, 2"):
                commands.add_metric([r["spacecraft_id"], r["status"]], r["n"])

            verify = GaugeMetricFamily("minisat_command_time_to_verified_seconds", "Seconds from SENT to VERIFIED",
                                       labels=["statistic"])
            (v,) = rows("SELECT avg(extract(epoch FROM verified_at - sent_at)) AS mean, "
                        "max(extract(epoch FROM verified_at - sent_at)) AS worst FROM ops.command_execution "
                        "WHERE status = 'VERIFIED' AND sent_at IS NOT NULL")
            if v["mean"] is not None:
                verify.add_metric(["mean"], float(v["mean"]))
                verify.add_metric(["max"], float(v["worst"]))

            outbox = GaugeMetricFamily("minisat_outbox_pending", "Side effects waiting to be delivered")
            age = GaugeMetricFamily("minisat_outbox_oldest_pending_age_seconds", "Age of the oldest waiting side effect")
            (o,) = rows("SELECT count(*) AS n, min(created_at) AS oldest FROM ops.outbox WHERE processed_at IS NULL")
            outbox.add_metric([], o["n"])
            age.add_metric([], (now - o["oldest"]).total_seconds() if o["oldest"] else 0.0)

            telemetry = GaugeMetricFamily("minisat_telemetry_age_seconds", "Seconds since telemetry last arrived",
                                          labels=["spacecraft_id"])
            health = GaugeMetricFamily("minisat_spacecraft_health", "1 for the current derived health status",
                                       labels=["spacecraft_id", "status"])
            for r in rows("SELECT spacecraft_id, health_status, last_contact_at FROM ops.spacecraft"):
                if r["last_contact_at"]:
                    telemetry.add_metric([r["spacecraft_id"]], (now - r["last_contact_at"]).total_seconds())
                health.add_metric([r["spacecraft_id"], r["health_status"]], 1)

            lag = GaugeMetricFamily("minisat_telemetry_ingest_lag_seconds",
                                    "Receive time minus spacecraft time of the newest sample (clock or pipeline trouble)",
                                    labels=["spacecraft_id"])
            for r in rows("SELECT s.spacecraft_id, extract(epoch FROM t.received_at) - t.sc_time_ms / 1000.0 AS lag "
                          "FROM ops.spacecraft s CROSS JOIN LATERAL (SELECT received_at, sc_time_ms FROM ops.telemetry_samples "
                          "WHERE spacecraft_id = s.spacecraft_id AND parameter_name = 'mode' ORDER BY sc_time_ms DESC "
                          "LIMIT 1) t"):
                lag.add_metric([r["spacecraft_id"]], float(r["lag"]))

            lost = CounterMetricFamily("minisat_packets_lost", "Telemetry packets missing, from sequence-counter gaps",
                                       labels=["spacecraft_id"])
            for r in rows("SELECT spacecraft_id, coalesce(sum(CASE WHEN jsonb_typeof(details -> 'lost') = 'number' THEN "
                          "(details ->> 'lost')::numeric END), 0) AS n FROM ops.spacecraft_event "
                          "WHERE event_type = 'PACKET_LOSS' GROUP BY 1"):
                lost.add_metric([r["spacecraft_id"]], float(r["n"]))
        return [alarms, commands, verify, outbox, age, telemetry, health, lag, lost]


class ApiMetrics:
    def __init__(self, store: Store, clock: Callable[[], datetime]):
        self.registry = CollectorRegistry()
        self.requests = Counter("minisat_api_requests_total", "HTTP requests", ["method", "route", "status"],
                                registry=self.registry)
        self.request_seconds = Histogram("minisat_api_request_duration_seconds", "HTTP request latency", ["method", "route"],
                                         buckets=LATENCY_BUCKETS, registry=self.registry)
        self.actions = Counter("minisat_api_actions_total", "Actions run through the API", ["action", "outcome"],
                               registry=self.registry)
        self.action_seconds = Histogram("minisat_api_action_duration_seconds", "Action latency", ["action"],
                                        buckets=LATENCY_BUCKETS, registry=self.registry)
        self.registry.register(_DatabaseCollector(store, clock))
