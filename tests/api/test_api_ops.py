"""Operating the API (protocols/observability-and-operations.md): health, metrics, correlation IDs, structured logs, CORS, and
what happens when the database goes away."""
import json
import logging
import uuid
from datetime import timedelta
from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("psycopg")
pytest.importorskip("alembic")

import psycopg  # noqa: E402
from prometheus_client.parser import text_string_to_metric_families  # noqa: E402

from apihelpers import TOKENS, Api  # noqa: E402
from minisat.api.health import EXPECTED_SCHEMA_REVISION  # noqa: E402
from minisat.api.logs import JsonFormatter, correlation_id_var  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SC = "/api/spacecraft/MINISAT-1"
ALLOWED_ORIGIN = "http://127.0.0.1:5173"


def refuse_to_connect():
    raise psycopg.OperationalError("connection to server at 127.0.0.1, port 5432 failed: password authentication failed "
                                   "for user app_reader (password: hunter2)")


def metrics_of(api, operator="vera"):
    """The /metrics text parsed into {(name, frozenset(labels)): value}."""
    response = api.get(operator, "/metrics")
    assert response.status_code == 200 and response.headers["content-type"].startswith("text/plain")
    samples = {}
    for family in text_string_to_metric_families(response.text):
        for s in family.samples:
            samples[(s.name, frozenset(s.labels.items()))] = s.value
    return samples


def labels(**kw):
    return frozenset(kw.items())


# ------------------------------------------------------------------------------------------------ the migration the code expects

def test_the_revision_the_api_expects_is_the_newest_migration():
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    assert ScriptDirectory.from_config(cfg).get_current_head() == EXPECTED_SCHEMA_REVISION == "0003"


# ------------------------------------------------------------------------------------------------ liveness and readiness

def test_live_answers_even_when_the_database_is_gone(world):
    api = Api(world, connect_reader=refuse_to_connect, connect_runner=refuse_to_connect)
    response = api.client.get("/health/live")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


def test_ready_when_everything_works(world, ground):
    api = Api(world, live_source=True)
    ground().run(2)
    response = api.client.get("/health/ready")
    body = response.json()
    assert response.status_code == 200 and body["status"] == "ready"
    assert {k: v["ok"] for k, v in body["checks"].items()} == {"database_reader": True, "migrations": True,
                                                                "database_runner": True, "telemetry": True}
    assert "revision 0003" in body["checks"]["migrations"]["detail"]


def test_ready_wants_telemetry_no_older_than_three_housekeeping_periods(world, ground):
    api = Api(world, live_source=True)
    ground().run(2)
    world.clock.advance(3.0)
    assert api.client.get("/health/ready").status_code == 200                       # 3 s is still fine
    world.clock.advance(0.5)
    stale = api.client.get("/health/ready")
    assert stale.status_code == 503 and stale.json()["status"] == "not ready"
    assert stale.json()["checks"]["telemetry"]["ok"] is False and "3.5 s old (limit 3 s)" in stale.json()["checks"]["telemetry"]["detail"]
    assert stale.json()["checks"]["database_reader"]["ok"] is True                  # only the telemetry check failed


def test_ready_without_any_telemetry_ever_is_not_ready_unless_there_is_no_live_source(world):
    wants = Api(world, live_source=True).client.get("/health/ready")
    assert wants.status_code == 503 and "ever been received" in wants.json()["checks"]["telemetry"]["detail"]
    without = Api(world, live_source=False).client.get("/health/ready")
    assert without.status_code == 200 and "skipped" in without.json()["checks"]["telemetry"]["detail"]


def test_ready_says_not_ready_when_the_database_is_down_and_leaks_nothing(world):
    api = Api(world, connect_reader=refuse_to_connect, connect_runner=refuse_to_connect)
    response = api.client.get("/health/ready")
    assert response.status_code == 503 and response.json()["checks"]["database_reader"]["ok"] is False
    text = response.text
    for secret in ("hunter2", "app_reader", "5432", "127.0.0.1", "password"):
        assert secret not in text, f"the readiness answer leaked {secret!r}"


def test_ready_notices_that_the_runner_role_cannot_connect(world):
    api = Api(world, connect_runner=refuse_to_connect)
    body = api.client.get("/health/ready").json()
    assert body["checks"]["database_runner"]["ok"] is False and body["checks"]["database_reader"]["ok"] is True
    assert "hunter2" not in json.dumps(body)


def test_ready_notices_a_database_on_another_revision(world):
    api = Api(world)
    world.db.commit("migrator", "UPDATE public.alembic_version SET version_num = '0002'")
    body = api.client.get("/health/ready").json()
    assert body["checks"]["migrations"]["ok"] is False
    assert "revision 0002" in body["checks"]["migrations"]["detail"] and "alembic upgrade head" in body["checks"]["migrations"]["detail"]


def test_ready_cannot_show_a_current_schema_if_the_revision_cannot_be_read(world):
    api = Api(world)
    world.db.commit("migrator", "REVOKE SELECT ON public.alembic_version FROM app_reader")
    check = api.client.get("/health/ready").json()["checks"]["migrations"]
    assert check["ok"] is False and "cannot be read" in check["detail"]


# ------------------------------------------------------------------------------------------------ metrics

def test_metrics_report_what_the_database_knows(world, ground):
    api = Api(world)
    g = ground(soc=0.30)
    g.run(1)
    g.run(30, lose={4, 5, 20})                                                    # two gaps: 2 packets, then 1 packet
    api.act("sam", "Plan Contact", spacecraft_id="MINISAT-1", station_id="HEL",
            start_at=(world.clock.now - timedelta(minutes=1)).isoformat(), end_at=(world.clock.now + timedelta(minutes=9)).isoformat())
    cancelled = api.result("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")["execution_id"]
    api.result("alice", "Cancel Command", execution_id=cancelled, reason="changed my mind")
    api.result("alice", "Propose Command", spacecraft_id="MINISAT-1", command="SetHeater", arguments={"state": "ON"}, reason="warm")
    world.clock.advance(2.5)

    m = metrics_of(api)
    assert m[("minisat_database_up", labels())] == 1
    assert m[("minisat_alarms_open", labels(spacecraft_id="MINISAT-1", severity="WARNING", state="ACTIVE"))] == 1
    assert m[("minisat_commands", labels(spacecraft_id="MINISAT-1", status="CANCELLED"))] == 1
    assert m[("minisat_commands", labels(spacecraft_id="MINISAT-1", status="PROPOSED"))] == 1
    assert m[("minisat_spacecraft_health", labels(spacecraft_id="MINISAT-1", status="WARNING"))] == 1
    assert m[("minisat_telemetry_age_seconds", labels(spacecraft_id="MINISAT-1"))] == pytest.approx(2.5)
    assert m[("minisat_packets_lost_total", labels(spacecraft_id="MINISAT-1"))] == 3          # 2 + 1, chosen above
    assert m[("minisat_outbox_pending", labels())] == 0
    assert abs(m[("minisat_telemetry_ingest_lag_seconds", labels(spacecraft_id="MINISAT-1"))]) < 1.0      # clocks agree here


def test_metrics_count_actions_by_name_and_outcome_and_requests_by_route_template(api):
    api.result("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")
    api.result("alice", "Propose Command", spacecraft_id="MINISAT-1", command="SetHeater", arguments={"state": "ON"}, reason="y")
    api.act("vera", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="z")           # denied
    api.act("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Explode", reason="z")       # invalid
    api.get("vera", SC)
    api.get("vera", SC)
    api.client.get("/no/such/place")
    api.client.get("/api/me")                                                                          # no token
    m = metrics_of(api)
    for outcome, count in (("OK", 2), ("DENIED", 1), ("INVALID", 1)):
        assert m[("minisat_api_actions_total", labels(action="Propose Command", outcome=outcome))] == count
    assert m[("minisat_api_action_duration_seconds_count", labels(action="Propose Command"))] == 4
    assert m[("minisat_api_requests_total", labels(method="GET", route="/api/spacecraft/{spacecraft_id}", status="200"))] == 2
    assert m[("minisat_api_requests_total", labels(method="GET", route="/api/me", status="401"))] == 1
    assert m[("minisat_api_requests_total", labels(method="GET", route="unmatched", status="404"))] == 1
    assert not [k for k in m if "MINISAT-1" in str(k) and k[0].startswith("minisat_api_requests")], \
        "an id in the URL must never become a label value (unbounded cardinality)"


def test_metrics_time_from_sent_to_verified(api, ground):
    g = ground()
    g.run(3)
    now = api.world.clock.now
    api.result("sam", "Plan Contact", spacecraft_id="MINISAT-1", station_id="HEL", start_at=(now - timedelta(minutes=1)).isoformat(),
               end_at=(now + timedelta(minutes=9)).isoformat())
    eid = api.result("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="link")["execution_id"]
    api.result("bob", "Approve Command", execution_id=eid)
    api.result("bob", "Release Command", execution_id=eid)
    assert m_pending(api) == 1                                                    # waiting for the worker
    g.send_released()
    g.run(2)
    assert m_pending(api) == 0
    m = metrics_of(api)
    assert m[("minisat_commands", labels(spacecraft_id="MINISAT-1", status="VERIFIED"))] == 1
    assert m[("minisat_command_time_to_verified_seconds", labels(statistic="mean"))] == pytest.approx(1.0, abs=0.01)   # a Noop: the next packet


def m_pending(api):
    return metrics_of(api)[("minisat_outbox_pending", labels())]


def test_metrics_still_answer_when_the_database_is_down_and_say_so(world):
    api = Api(world)
    healthy_metrics = metrics_of(api)
    assert healthy_metrics[("minisat_database_up", labels())] == 1
    broken = Api(world, connect_reader=lambda: _reader_that_works_once(world))
    assert broken.client.get("/metrics", headers=broken.headers("vera")).status_code == 200      # auth used the first connection
    m = metrics_of(broken)
    assert m[("minisat_database_up", labels())] == 0
    assert not any(name == "minisat_alarms_open" for name, _ in m)


_calls = {"n": 0}


def _reader_that_works_once(world):
    """A reader that connects for the caller's identity lookup and then fails: the metrics scrape must survive that."""
    _calls["n"] += 1
    if _calls["n"] % 2 == 0:
        raise psycopg.OperationalError("the server closed the connection unexpectedly")
    return world.db.connect_factory("reader")()


# ------------------------------------------------------------------------------------------------ correlation ids and logs

def test_every_response_has_a_correlation_id_and_a_valid_one_from_the_caller_is_kept(api):
    mine = str(uuid.uuid4())
    response = api.client.get("/api/me", headers={**api.headers("alice"), "X-Correlation-ID": mine})
    assert response.headers["x-correlation-id"] == mine
    for bad in ("not-a-uuid", "", "1" * 500, "'; DROP TABLE ops.audit_log; --"):
        response = api.client.get("/api/me", headers={**api.headers("alice"), "X-Correlation-ID": bad})
        assert uuid.UUID(response.headers["x-correlation-id"]) and response.headers["x-correlation-id"] != bad
    assert uuid.UUID(api.client.get("/health/live").headers["x-correlation-id"])
    assert uuid.UUID(api.client.get("/no/such/place").headers["x-correlation-id"])


def test_the_correlation_id_links_the_request_the_response_and_the_audit_row(api):
    mine = uuid.uuid4()
    response = api.act("alice", "Propose Command", headers={"X-Correlation-ID": str(mine)}, spacecraft_id="MINISAT-1",
                       command="Noop", reason="trace me")
    assert response.headers["x-correlation-id"] == response.json()["correlation_id"] == str(mine)
    (row,) = api.world.audit(audit_id=response.json()["audit_id"])
    assert row["correlation_id"] == mine
    refused = api.act("vera", "Propose Command", headers={"X-Correlation-ID": str(mine)}, spacecraft_id="MINISAT-1",
                      command="Noop", reason="x")
    assert refused.json()["correlation_id"] == str(mine) and api.world.audit(audit_id=refused.json()["audit_id"])[0]["correlation_id"] == mine


def test_a_request_is_logged_as_one_json_line_with_the_correlation_id_and_no_token(api, caplog):
    mine = str(uuid.uuid4())
    caplog.set_level(logging.DEBUG, logger="minisat")
    api.client.get(SC, headers={**api.headers("alice"), "X-Correlation-ID": mine})
    api.act("alice", "Propose Command", headers={"X-Correlation-ID": mine}, spacecraft_id="MINISAT-1", command="Noop", reason="x")
    formatter = JsonFormatter()
    lines = [json.loads(formatter.format(r)) for r in caplog.records if r.name.startswith("minisat.api")]
    for r in caplog.records:
        assert "\n" not in formatter.format(r), "one event per line"
    request = next(x for x in lines if x["message"] == "request" and x["path"] == SC)
    assert (request["method"], request["status"], request["operator"], request["level"]) == ("GET", 200, "alice", "INFO")
    assert request["correlationId"] == mine and request["ts"].endswith("+00:00") and request["durationMs"] >= 0
    action = next(x for x in lines if x["message"] == "action")
    assert (action["action"], action["outcome"], action["operator"]) == ("Propose Command", "OK", "alice")
    assert action["correlationId"] == mine and isinstance(action["auditId"], int)
    everything = " ".join(json.dumps(x) for x in lines)
    assert TOKENS["alice"] not in everything and "Bearer" not in everything


def test_probes_and_scrapes_are_logged_quietly(api, caplog):
    caplog.set_level(logging.INFO, logger="minisat")
    api.client.get("/health/live")
    metrics_of(api)
    assert not [r for r in caplog.records if r.name == "minisat.api" and r.getMessage() == "request"
                and r.fields["path"] in ("/health/live", "/metrics")]


def test_failed_logins_are_logged_with_a_reason_but_never_the_token(api, caplog):
    caplog.set_level(logging.INFO, logger="minisat")
    api.client.get("/api/me", headers={"Authorization": "Bearer this-is-a-secret-looking-token"})
    api.client.get("/api/me")
    formatter = JsonFormatter()
    lines = [json.loads(formatter.format(r)) for r in caplog.records if r.name == "minisat.api.auth"]
    assert [x["reason"] for x in lines] == ["unknown token", "no token"] and all(x["level"] == "WARNING" for x in lines)
    assert "secret-looking" not in " ".join(json.dumps(x) for x in lines)


def test_the_json_formatter_marks_exceptions_and_only_adds_a_correlation_id_when_there_is_one():
    formatter = JsonFormatter()
    record = logging.LogRecord("minisat.test", logging.ERROR, __file__, 1, "something broke: %s", ("details",), None)
    assert "correlationId" not in json.loads(formatter.format(record))
    token = correlation_id_var.set("abc")
    try:
        try:
            raise ValueError("boom")
        except ValueError:
            import sys
            record.exc_info = sys.exc_info()
        data = json.loads(formatter.format(record))
    finally:
        correlation_id_var.reset(token)
    assert data["message"] == "something broke: details" and data["correlationId"] == "abc"
    assert "ValueError: boom" in data["exception"] and data["level"] == "ERROR"


def test_responses_are_not_cacheable_and_not_sniffable(api):
    for response in (api.get("alice", SC), api.client.get("/health/live"), api.act("vera", "Propose Command")):
        assert response.headers["cache-control"] == "no-store" and response.headers["x-content-type-options"] == "nosniff"


# ------------------------------------------------------------------------------------------------ failures

def test_an_unexpected_error_is_a_500_with_a_correlation_id_and_no_internals(world, caplog):
    api = Api(world, raise_server_exceptions=False)

    @api.app.get("/boom")
    def boom():
        raise RuntimeError("internal detail: table ops.secret_stuff")
    caplog.set_level(logging.ERROR, logger="minisat")
    response = api.client.get("/boom")
    assert response.status_code == 500 and "ops.secret_stuff" not in response.text
    assert response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert any("ops.secret_stuff" in (r.exc_text or "") or r.exc_info for r in caplog.records), "the details go to the server log"


def test_with_the_database_down_reads_are_503_and_nothing_is_changed(world):
    api = Api(world, connect_reader=refuse_to_connect, connect_runner=refuse_to_connect)
    for response in (api.get("alice", "/api/me"), api.get("alice", SC),
                     api.act("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")):
        assert response.status_code == 503 and "unavailable" in response.json()["detail"]
        assert "hunter2" not in response.text and response.json()["correlation_id"] == response.headers["x-correlation-id"]
    assert world.audit() == [] and world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 0


def test_with_only_the_runner_role_broken_actions_fail_closed_and_reads_still_work(world):
    api = Api(world, connect_runner=refuse_to_connect)
    assert api.get("alice", SC).status_code == 200
    response = api.act("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x")
    assert response.status_code == 503 and world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 0
    api.client.get("/health/live")
    assert metrics_of(api)[("minisat_api_actions_total", labels(action="Propose Command", outcome="UNAVAILABLE"))] == 1


# ------------------------------------------------------------------------------------------------ CORS

def test_the_dashboard_origin_may_call_with_credentials_headers_and_others_may_not(world):
    api = Api(world, cors=[ALLOWED_ORIGIN])
    preflight = api.client.options("/api/actions/propose-command", headers={
        "Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type,idempotency-key,x-correlation-id"})
    assert preflight.status_code == 200 and preflight.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "POST" in preflight.headers["access-control-allow-methods"]
    for header in ("authorization", "idempotency-key", "x-correlation-id"):
        assert header in preflight.headers["access-control-allow-headers"].lower()

    evil = api.client.options("/api/actions/propose-command", headers={
        "Origin": "https://evil.example", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "authorization"})
    assert evil.status_code == 400 and "access-control-allow-origin" not in evil.headers

    allowed = api.client.get("/api/me", headers={**api.headers("alice"), "Origin": ALLOWED_ORIGIN})
    assert allowed.headers["access-control-allow-origin"] == ALLOWED_ORIGIN
    assert "x-correlation-id" in allowed.headers["access-control-expose-headers"].lower()
    other = api.client.get("/api/me", headers={**api.headers("alice"), "Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in other.headers
    assert "access-control-allow-credentials" not in allowed.headers            # tokens travel in a header, never in a cookie


def test_other_methods_are_not_offered_to_the_browser(world):
    api = Api(world, cors=[ALLOWED_ORIGIN])
    for method in ("DELETE", "PUT", "PATCH"):
        response = api.client.options("/api/me", headers={"Origin": ALLOWED_ORIGIN, "Access-Control-Request-Method": method})
        assert response.status_code == 400, method
