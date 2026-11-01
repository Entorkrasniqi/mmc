import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tests"))      # for the xtce_interp helper
sys.path.insert(0, str(ROOT / "tools"))      # for validate_xtce

from minisat.spec import load_spec  # noqa: E402
# fixtures of the PostgreSQL tests in tests/db; they skip themselves when no database server is configured
from dbfixtures import (admin_conninfo, clock, database_factory, db, fresh_db, roles_ready, run,  # noqa: E402,F401
                        template_db, world)
# fixtures of the API tests in tests/api
from apifixtures import api, ground  # noqa: E402,F401

SPEC_PATH = ROOT / "spec" / "minisat.yaml"
XTCE_PATH = ROOT / "yamcs" / "src" / "main" / "yamcs" / "mdb" / "minisat.xml"


@pytest.fixture(scope="session")
def spec():
    return load_spec(SPEC_PATH)
