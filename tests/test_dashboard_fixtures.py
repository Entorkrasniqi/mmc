"""The dashboard's test fixture of action schemas must match the actions the API exposes (testing-and-verification.md, rule 10:
generated files are tested for freshness). Regenerate with:  python tools/dump_action_schemas.py"""
import importlib.util
from pathlib import Path

import pytest

pytest.importorskip("pydantic")

ROOT = Path(__file__).resolve().parent.parent


def test_the_action_schemas_in_the_dashboard_tests_are_current(capsys):
    spec = importlib.util.spec_from_file_location("dump_action_schemas", ROOT / "tools" / "dump_action_schemas.py")
    tool = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tool)
    on_disk = tool.TARGET.read_text(encoding="utf-8")
    assert on_disk == tool.current(), "dashboard/src/test/action-schemas.json is out of date: run python tools/dump_action_schemas.py"
