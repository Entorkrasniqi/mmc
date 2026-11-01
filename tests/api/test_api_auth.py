"""Who may call the API, and what the API lets each role do (protocols/security-and-threat-model.md, threats 3 and 4).

The role rules live in the action runner; these tests prove the HTTP layer neither bypasses nor hides them: the right status code,
an audit row for every refused attempt, and no route that is open by accident.
"""
import re

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("httpx")
pytest.importorskip("psycopg")

from apihelpers import TOKENS, Api  # noqa: E402
from minisat.api.routes_actions import exposed_actions, slug  # noqa: E402

# the roles allowed to run each action over HTTP, written out by hand from ontology.md sections 3 and 7
# (the actions only the SYSTEM may run are not exposed over HTTP at all)
EXPOSED_ROLES = {
    "Propose Command": {"OPERATOR", "SUPERVISOR", "AGENT"},
    "Approve Command": {"OPERATOR", "SUPERVISOR"},
    "Release Command": {"OPERATOR", "SUPERVISOR"},
    "Cancel Command": {"OPERATOR", "SUPERVISOR", "AGENT"},
    "Acknowledge Alarm": {"OPERATOR", "SUPERVISOR"},
    "Open Anomaly": {"OPERATOR", "SUPERVISOR", "AGENT"},
    "Update Anomaly": {"OPERATOR", "SUPERVISOR"},
    "Plan Contact": {"SUPERVISOR"},
}
PEOPLE_AND_AGENT = {"VIEWER": "vera", "OPERATOR": "alice", "SUPERVISOR": "sam", "AGENT": "helper"}
PUBLIC_PATHS = {"/health/live", "/health/ready"}


def test_the_exposed_actions_are_exactly_the_ones_a_person_or_the_agent_may_run(api):
    names = {a.name for a in exposed_actions(api.world.runner.registry)}
    assert names == set(EXPOSED_ROLES), "an action was added or its roles changed: decide whether HTTP exposes it"
    system_only = {a.name for a in api.world.runner.registry} - names
    assert system_only == {"Record Command Sent", "Record Command Outcome", "Raise Alarm", "Update Alarm", "Clear Alarm",
                           "Record Spacecraft Event", "Set Health Status"}


def test_the_system_actions_have_no_route_at_all(api):
    for name in ("Raise Alarm", "Record Command Sent", "Set Health Status"):
        response = api.act("sam", name, spacecraft_id="MINISAT-1")
        assert response.status_code in (404, 405), name
    assert api.world.audit() == [], "nothing was even attempted"


# ------------------------------------------------------------------------------------------------ who is calling

def test_no_route_is_open_by_accident(api):
    """Every route except the two probes needs a caller. The routes come from the API's own OpenAPI document, so a route
    added later is covered without anyone remembering to list it here."""
    checked = 0
    for template, operations in api.app.openapi()["paths"].items():
        if template in PUBLIC_PATHS:
            continue
        path = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", template)
        for method in operations:
            response = api.client.request(method.upper(), path, json={})
            assert response.status_code == 401, f"{method.upper()} {template} answered {response.status_code} without a token"
            assert response.headers["www-authenticate"] == "Bearer"
            checked += 1
    assert checked >= 30, "the walk found suspiciously few routes (35 when this was written)"


def test_the_probes_need_no_token(api):
    assert api.client.get("/health/live").status_code == 200
    assert api.client.get("/health/ready").status_code in (200, 503)


@pytest.mark.parametrize("header", [
    "Bearer wrong-token-wrong-token-wrong", "Bearer ", "Bearer", "Basic " + TOKENS["alice"], TOKENS["alice"],
    "Bearer " + TOKENS["alice"][:-1], "Bearer " + TOKENS["alice"] + "x", "Bearer " + TOKENS["alice"].upper(),
])
def test_a_wrong_or_malformed_credential_is_refused(api, header):
    response = api.client.get("/api/me", headers={"Authorization": header})
    assert response.status_code == 401


def test_a_token_works_only_for_its_own_operator(api):
    assert api.ok(api.get("alice", "/api/me"))["operator_id"] == "alice"
    assert api.ok(api.get("sam", "/api/me"))["operator_id"] == "sam"
    assert TOKENS["alice"] != TOKENS["sam"]


def test_the_answer_does_not_reveal_why_a_token_failed(api):
    api2 = Api(api.world, tokens={**TOKENS, "ghost": "dev-token-of-ghost-0123456789"})        # not an operator in the database
    bad = api2.client.get("/api/me", headers={"Authorization": "Bearer nonsense-nonsense-nonsense"})
    ghost = api2.client.get("/api/me", headers={"Authorization": "Bearer dev-token-of-ghost-0123456789"})
    system = api2.client.get("/api/me", headers=api2.headers("automation"))
    assert bad.status_code == ghost.status_code == system.status_code == 401
    assert bad.json()["detail"] == ghost.json()["detail"] == system.json()["detail"]


def test_the_automation_account_cannot_log_in_over_http(api):
    assert api.get("automation", "/api/spacecraft").status_code == 401
    assert api.act("automation", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x").status_code == 401
    assert api.world.audit() == []


def test_with_no_tokens_configured_nobody_gets_in_but_the_probes_work(world):
    closed = Api(world, tokens={})
    assert closed.client.get("/health/live").status_code == 200
    for path in ("/api/me", "/api/spacecraft", "/api/definitions", "/metrics"):
        assert closed.client.get(path).status_code == 401


def test_the_role_is_read_from_the_database_on_every_request(api):
    assert api.ok(api.get("vera", "/api/me"))["role"] == "VIEWER"
    assert api.act("vera", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x").status_code == 403
    api.world.db.commit("migrator", "UPDATE ops.operator SET kind = 'HUMAN', role = 'OPERATOR' WHERE operator_id = 'vera'")
    assert api.ok(api.get("vera", "/api/me"))["role"] == "OPERATOR"
    assert api.act("vera", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x").status_code == 200


# ------------------------------------------------------------------------------------------------ roles

@pytest.mark.parametrize("action", sorted(EXPOSED_ROLES))
def test_exact_role_matrix_over_http(api, action):
    """An empty body: a role that may not run the action gets 403 (DENIED); one that may gets as far as validation (422,
    INVALID). Either way there is exactly one audit row, with that outcome and that operator."""
    for role, operator in PEOPLE_AND_AGENT.items():
        before = len(api.world.audit())
        response = api.act(operator, action)
        allowed = role in EXPOSED_ROLES[action]
        expected_status, expected_outcome = (422, "INVALID") if allowed else (403, "DENIED")
        assert response.status_code == expected_status, f"{role} on {action}: {response.status_code} {response.text}"
        body = response.json()
        assert body["outcome"] == expected_outcome and body["action"] == action
        rows = api.world.audit()[before:]
        assert len(rows) == 1 and rows[0]["outcome"] == expected_outcome and rows[0]["operator_id"] == operator
        assert rows[0]["audit_id"] == body["audit_id"]


def test_a_viewer_can_read_everything_and_change_nothing(api):
    assert api.ok(api.get("vera", "/api/spacecraft"))["items"][0]["spacecraft_id"] == "MINISAT-1"
    for action in EXPOSED_ROLES:
        assert api.act("vera", action, spacecraft_id="MINISAT-1", command="Noop", reason="x").status_code == 403
    for table in ("command_execution", "alarm", "anomaly", "contact_window"):
        assert api.world.row(f"SELECT count(*) AS n FROM ops.{table}")["n"] == 0
    assert {r["outcome"] for r in api.world.audit()} == {"DENIED"}


def test_the_agent_may_propose_but_not_approve_release_or_acknowledge(api):
    proposed = api.result("helper", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="link check")
    eid = proposed["execution_id"]
    for action in ("Approve Command", "Release Command"):
        assert api.act("helper", action, execution_id=eid).status_code == 403
    assert api.act("helper", "Acknowledge Alarm", alarm_id=eid).status_code == 403
    assert api.world.execution(eid)["status"] == "PROPOSED"


def test_the_two_person_rule_shows_through_http(api):
    eid = api.result("sam", "Propose Command", spacecraft_id="MINISAT-1", command="Reboot", reason="clear a fault")["execution_id"]
    own = api.act("sam", "Approve Command", execution_id=eid)
    assert own.status_code == 403 and "two-person rule" in own.json()["detail"]
    assert api.act("alice", "Approve Command", execution_id=eid).status_code == 403          # an operator cannot approve VITAL
    approved = api.ok(api.act("tina", "Approve Command", execution_id=eid))
    assert approved["result"]["status"] == "APPROVED"
    assert api.world.execution(eid)["approved_by"] == "tina"


# ------------------------------------------------------------------------------------------------ requests

def test_a_refused_request_is_audited_with_its_parameters_and_the_caller(api):
    response = api.act("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Explode", reason="x")
    assert response.status_code == 422 and "unknown command" in response.json()["detail"]
    (row,) = api.world.audit(audit_id=response.json()["audit_id"])
    assert (row["outcome"], row["operator_id"], row["action"]) == ("INVALID", "alice", "Propose Command")
    assert row["parameters"]["command"] == "Explode"


def test_unknown_fields_are_refused_not_ignored(api):
    response = api.act("alice", "Propose Command", spacecraft_id="MINISAT-1", command="Noop", reason="x", force=True)
    assert response.status_code == 422 and "force" in response.json()["detail"]


@pytest.mark.parametrize("body", [[], "text", 5])
def test_a_body_that_is_not_a_json_object_is_refused_before_the_runner(api, body):
    response = api.client.post("/api/actions/propose-command", json=body, headers=api.headers("alice"))
    assert response.status_code == 422
    assert api.world.audit() == []


def test_a_request_without_a_body_is_still_an_attempt_and_is_audited(api):
    response = api.client.post("/api/actions/propose-command", headers=api.headers("alice"))
    assert response.status_code == 422 and response.json()["outcome"] == "INVALID"
    assert len(api.world.audit()) == 1


def test_an_idempotency_key_makes_a_retry_harmless(api):
    body = dict(spacecraft_id="MINISAT-1", command="Noop", reason="link check")
    first = api.ok(api.act("alice", "Propose Command", headers={"Idempotency-Key": "k-1"}, **body))
    again = api.ok(api.act("alice", "Propose Command", headers={"Idempotency-Key": "k-1"}, **body))
    assert first["replayed"] is False and again["replayed"] is True
    assert again["result"]["execution_id"] == first["result"]["execution_id"] and again["audit_id"] == first["audit_id"]
    assert api.world.row("SELECT count(*) AS n FROM ops.command_execution")["n"] == 1
    other = api.act("alice", "Propose Command", headers={"Idempotency-Key": "k-1"}, **{**body, "reason": "something else"})
    assert other.status_code == 422 and "different parameters" in other.json()["detail"]


def test_the_actions_listing_follows_the_registry_and_the_callers_role(api):
    listing = {a["name"]: a for a in api.items("sam", "/api/actions")}
    assert set(listing) == set(EXPOSED_ROLES)
    for name, roles in EXPOSED_ROLES.items():
        item = listing[name]
        assert set(item["roles"]) == roles and item["path"] == f"/api/actions/{slug(name)}"
        assert item["allowed_for_me"] == ("SUPERVISOR" in roles)
        assert item["schema"]["type"] == "object" and "properties" in item["schema"]
    viewer = {a["name"]: a["allowed_for_me"] for a in api.items("vera", "/api/actions")}
    assert not any(viewer.values())
    assert {n for n, a in listing.items() if a["agent_callable"]} == {"Propose Command", "Cancel Command", "Open Anomaly"}
    assert listing["Propose Command"]["schema"]["required"] == ["spacecraft_id", "command", "reason"]


def test_the_openapi_document_describes_every_action_body(api):
    document = api.client.get("/openapi.json").json()
    for name in EXPOSED_ROLES:
        operation = document["paths"][f"/api/actions/{slug(name)}"]["post"]
        schema = operation["requestBody"]["content"]["application/json"]["schema"]
        assert schema["properties"], name
        assert "security" in operation or "HTTPBearer" in str(document["components"]["securitySchemes"])
