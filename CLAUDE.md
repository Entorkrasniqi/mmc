# mini-mission-control: notes for AI assistants

A fictional satellite simulator (CCSDS packets over UDP), the XTCE database generated from one YAML specification, and an
ontology layer (PostgreSQL) for building a mission-control app on top. Read first: [README.md](README.md),
[ontology.md](ontology.md) (the domain model), [PLAN.md](PLAN.md) (what is done and next) and
[protocols/](protocols/README.md) (the rules; the full version of this page is
[protocols/ai-assisted-development.md](protocols/ai-assisted-development.md)).

## Commands

```bash
python3.12 -m venv .venv && . .venv/bin/activate && pip install -e ".[dev,db]"   # Python 3.10+
pytest -q                                   # simulator, codec, XTCE, ontology definitions; database tests skip themselves
minisat gen-xtce --check                    # the generated database must match spec/minisat.yaml
# database tests need a THROW-AWAY PostgreSQL superuser URL and the psql program. Never the dev database: the tests reset the
# server-wide roles' passwords (they refuse a server that has a database called "minisat")
docker run --rm -d --name minisat-test-pg -e POSTGRES_PASSWORD=test -p 127.0.0.1:55432:5432 postgres:16
MINISAT_REQUIRE_DB=1 MINISAT_TEST_ADMIN_URL=postgresql://postgres:test@127.0.0.1:55432/postgres pytest -q tests/db
# dev database: cp .env.example .env; docker compose up -d db; set -a; . ./.env; set +a; alembic upgrade head
minisat db-seed --demo; minisat ground; minisat act alice "Propose Command" '{...}'; minisat status   # see README 3.6
python tools/mutation_check.py              # with MINISAT_TEST_ADMIN_URL set it also mutates the SQL, the runner logic and the HTTP API
# API (pip install -e ".[dev,db,api]"): minisat dev-tokens > put the line in .env; minisat api --no-contact-check
# dashboard (root package.json; node_modules is installed there): npm run typecheck | test | build | dev ; npm run e2e needs Docker and
# runs the REAL stack (tools/e2e_stack.py: its own database container on port 55433, never your dev database). Stop a hand-started
# stack with Ctrl-C or SIGTERM, never SIGKILL (it would leave the services running)
python tools/dump_action_schemas.py         # after changing an action's parameters (the dashboard's tests read it)
```

## Rules that matter most

- `spec/minisat.yaml` is the single source of truth. Never edit `yamcs/src/main/yamcs/mdb/minisat.xml` by hand: change the
  YAML and run `minisat gen-xtce`. A spec change also changes packet sizes in several tests.
- Definitions (parameters, packet types, commands) come from the spec and are read-only
  ([ADR 0001](protocols/adr/0001-two-layer-ontology.md)). Only operations data lives in the database.
- Operations tables are written only by the `app_runner` role, through `ActionRunner` (`src/minisat/ontology/runner.py`); add a business
  operation as an `Action` in `actions/` (typed parameters, roles, handler), never as a direct INSERT. Telemetry ingestion uses the narrower
  `ingest` role; automations act as the SYSTEM operator through the runner. Do not grant a role more than the matrix in
  `tests/db/test_privileges.py`, and add every new action to `ROLE_MATRIX` in `tests/db/test_runner.py`: those tests must be updated deliberately.
- Commands are delivered at most once and one command is in flight per spacecraft: do not add a retry, and do not weaken the lifecycle
  rules in `actions/commands.py` without reading `protocols/command-safety-protocol.md`.
- Never weaken or skip a test to make it pass. Expected values in tests are worked out independently, not copied from the code.
- Say "verified" only for what you ran. Yamcs has never been started with this configuration; the README says so.
- The API (`src/minisat/api/`) never writes except through `ActionRunner`; reads go through `store.py` as `app_reader`, with query parameters only. A new
  action is exposed over HTTP automatically unless it is system-only: add it to `EXPOSED_ROLES` in `tests/api/test_api_auth.py` as well as to `ROLE_MATRIX`.
  Authentication is a DEV-ONLY static token per operator: do not present it as real login, and do not make it listen beyond localhost.
- Dashboard: the server decides, the browser only shows (`util/commands.ts` disables buttons the runner would refuse, and says why). Never
  `dangerouslySetInnerHTML`; keep the token in `sessionStorage` only. A UI bug found in the browser gets a unit test where the logic can be tested.
- No secrets in the repository (`.env` and `.e2e/` are ignored). Do not commit or push unless asked.
