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
# database tests need a PostgreSQL superuser URL (and the psql program):
MINISAT_TEST_ADMIN_URL=postgresql://postgres:...@localhost:5432/postgres pytest -q tests/db
# dev database: cp .env.example .env; docker compose up -d db; set -a; . ./.env; set +a; alembic upgrade head
```

## Rules that matter most

- `spec/minisat.yaml` is the single source of truth. Never edit `yamcs/src/main/yamcs/mdb/minisat.xml` by hand: change the
  YAML and run `minisat gen-xtce`. A spec change also changes packet sizes in several tests.
- Definitions (parameters, packet types, commands) come from the spec and are read-only
  ([ADR 0001](protocols/adr/0001-two-layer-ontology.md)). Only operations data lives in the database.
- Operations tables are written only by the `app_runner` role, through the action runner (not built yet). Do not grant a role more
  than the matrix in `tests/db/test_privileges.py`; that test must be updated deliberately.
- Never weaken or skip a test to make it pass. Expected values in tests are worked out independently, not copied from the code.
- Say "verified" only for what you ran. Yamcs has never been started with this configuration; the README says so.
- No secrets in the repository (`.env` is ignored). Do not commit or push unless asked.
