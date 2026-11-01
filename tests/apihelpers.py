"""Helpers for the API tests (tests/api): a client that knows the demo operators' tokens, and a ground station driven by hand.

Everything underneath is real: a PostgreSQL database, the action runner, the ingestor and the automations, the outbox worker,
and the satellite model. Only time is fake (the clock moves when the test says so) and the UDP sockets are replaced by direct calls.
"""
from __future__ import annotations

from typing import Optional

from minisat.api.app import create_app
from minisat.api.routes_actions import slug
from minisat.api.settings import ApiSettings
from minisat.codec import decode_tm
from minisat.model import Spacecraft
from minisat.ontology.automation import AutomationEngine
from minisat.ontology.ingest import Ingestor
from minisat.ontology.worker import OutboxWorker
from minisat.simulator import Simulator

OPERATORS = ("alice", "bob", "sam", "tina", "vera", "helper", "automation")
TOKENS = {operator: f"dev-token-of-{operator}-0123456789" for operator in OPERATORS}
MODE = {"SAFE": 0, "NOMINAL": 1, "PAYLOAD": 2}


class Api:
    """A running API (in process) on the world's database, with one token per seeded operator."""

    def __init__(self, world, live_source: bool = False, tokens=None, cors=None, connect_reader=None, connect_runner=None,
                 raise_server_exceptions=True, **app_options):
        from fastapi.testclient import TestClient
        self.world = world
        extra = {"cors_origins": tuple(cors)} if cors else {}
        settings = ApiSettings(dev_tokens=tuple((tokens or TOKENS).items()), live_source=live_source, **extra)
        self.app = create_app(settings, world.spec, connect_reader or world.db.connect_factory("reader"),
                              connect_runner or world.db.connect_factory("runner"), clock=world.clock, **app_options)
        self.client = TestClient(self.app, raise_server_exceptions=raise_server_exceptions)

    @staticmethod
    def headers(operator: Optional[str], extra=None) -> dict:
        headers = dict(extra or {})
        if operator:
            headers["Authorization"] = f"Bearer {TOKENS[operator]}"
        return headers

    def get(self, operator, path, **params):
        return self.client.get(path, params={k: v for k, v in params.items() if v is not None},
                               headers=self.headers(operator))

    def post(self, operator, path, json=None, headers=None):
        return self.client.post(path, json=json, headers=self.headers(operator, headers))

    def act(self, operator, action, headers=None, **params):
        return self.post(operator, f"/api/actions/{slug(action)}", json=params, headers=headers)

    def ok(self, response, status=200):
        assert response.status_code == status, f"{response.request.method} {response.request.url}: " \
                                               f"{response.status_code} {response.text}"
        return response.json()

    def result(self, operator, action, **params) -> dict:
        """Run an action and return its result (the test fails if the API refused it)."""
        return self.ok(self.act(operator, action, **params))["result"]

    def items(self, operator, path, **params) -> list:
        return self.ok(self.get(operator, path, **params))["items"]


class SimLink:
    """The worker's link, wired straight to the in-process satellite."""

    def __init__(self, ground: "Ground"):
        self.ground = ground

    def send(self, data: bytes) -> None:
        self.ground.sim.handle_telecommand(data)


class Ground:
    """A simulated satellite, the ingestor, the automations and the outbox worker, driven by hand.

    The spacecraft's clock starts at the world's clock, so spacecraft time and wall time agree (events carry spacecraft time).
    """

    def __init__(self, world, soc=0.9, mode=None, start_t=0.0):
        self.world, self.spec = world, world.spec
        self.epoch_ms = int(world.clock.now.timestamp() * 1000) - int(start_t * 1000)
        model = Spacecraft(soc=soc, t=start_t, **({"mode": MODE[mode]} if mode else {}))
        self.packets = []
        self.sim = Simulator(self.spec, model, self.packets.append, epoch_ms=self.epoch_ms)
        self.ingestor = Ingestor(self.spec, world.db.connect_factory("ingest"), "MINISAT-1", clock=world.clock)
        self.engine = AutomationEngine(self.spec, world.runner, world.db.connect_factory("runner"), clock=world.clock)
        self.worker = OutboxWorker(world.db.connect_factory("runner"), world.runner, SimLink(self), clock=world.clock)

    def run(self, seconds: int, lose=()) -> None:
        """Advance the satellite second by second. ``lose`` = indices (0-based, within this call) of seconds whose
        Housekeeping packet never reaches the ground."""
        for second in range(int(seconds)):
            self.packets.clear()
            self.sim.advance(1.0)
            self.world.clock.advance(1.0)
            for data in list(self.packets):
                if second in lose and decode_tm(self.spec, data).packet == "Housekeeping":
                    continue
                result = self.ingestor.ingest(data)
                self.engine.on_telemetry(result)

    def send_released(self) -> int:
        """What the ground station's timer does: hand released commands to the link."""
        return self.worker.run_once()

    def close(self) -> None:
        for part in (self.ingestor, self.engine, self.worker):
            part.close()
