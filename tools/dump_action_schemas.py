#!/usr/bin/env python3
"""Write (or check) dashboard/src/test/action-schemas.json: the JSON Schemas of the actions the API exposes.

    python tools/dump_action_schemas.py           # regenerate after changing an action's parameters
    python tools/dump_action_schemas.py --check   # fail if the file on disk differs (tests/test_dashboard_fixtures.py does this)

The dashboard builds its forms from these schemas (GET /api/actions), and its unit tests read this file, so the tests see exactly
the shapes pydantic writes instead of shapes someone typed in by hand.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TARGET = ROOT / "dashboard" / "src" / "test" / "action-schemas.json"


def current() -> str:
    from minisat.ontology.actions import default_registry
    data = {a.name: {"slug": a.name.lower().replace(" ", "-"), "schema": a.json_schema()}
            for a in default_registry() if a.roles - {"SYSTEM"}}        # what minisat.api.routes_actions.exposed_actions exposes
    return json.dumps(data, indent=2, sort_keys=True) + "\n"


def main() -> int:
    text = current()
    if "--check" in sys.argv:
        if not TARGET.exists() or TARGET.read_text(encoding="utf-8") != text:
            print(f"{TARGET.relative_to(ROOT)} is out of date: run 'python tools/dump_action_schemas.py'", file=sys.stderr)
            return 1
        print(f"{TARGET.relative_to(ROOT)} is up to date")
        return 0
    TARGET.write_text(text, encoding="utf-8")
    print(f"wrote {TARGET.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
