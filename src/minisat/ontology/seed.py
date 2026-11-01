"""Reference data: the spacecraft, the operators and the ground stations.

These are created by an administrator, not by actions (ontology.md, section 7), so seeding connects as the ``migrator`` role.
It is idempotent: running it twice changes nothing.
"""
from __future__ import annotations

from typing import Iterable, Optional, Sequence, Tuple

from ..spec import Spec

__all__ = ["DEMO_OPERATORS", "DEMO_STATIONS", "seed_reference_data", "parse_operator"]

HUMAN_ROLES = ("VIEWER", "OPERATOR", "SUPERVISOR")

# (operator_id, display name, role)
DEMO_OPERATORS = (("alice", "Alice", "OPERATOR"), ("bob", "Bob", "OPERATOR"), ("sam", "Sam", "SUPERVISOR"),
                  ("tina", "Tina", "SUPERVISOR"), ("vera", "Vera", "VIEWER"), ("helper", "Helper (AI agent)", "AGENT"))
# (station_id, name, latitude, longitude)
DEMO_STATIONS = (("HEL", "Helsinki", 60.2, 24.9),)


def parse_operator(text: str) -> Tuple[str, str, str]:
    """``id:Display Name:ROLE`` -> (id, name, role)."""
    parts = text.split(":")
    if len(parts) != 3 or not all(p.strip() for p in parts):
        raise ValueError(f"{text!r}: write operators as id:Display Name:ROLE, for example alice:Alice:OPERATOR")
    operator_id, name, role = (p.strip() for p in parts)
    if role not in HUMAN_ROLES + ("AGENT", "SYSTEM"):
        raise ValueError(f"{text!r}: role must be one of {', '.join(HUMAN_ROLES + ('AGENT', 'SYSTEM'))}")
    return operator_id, name, role


def _kind(role: str) -> str:
    return "HUMAN" if role in HUMAN_ROLES else role


def seed_reference_data(conn, spec: Spec, spacecraft_id: str = "MINISAT-1", operators: Iterable = (),
                        system_operator: str = "automation", stations: Sequence = (),
                        spacecraft_name: Optional[str] = None) -> dict:
    """Create what is missing. ``conn`` is a connection as the migrator role; the caller commits."""
    created = {"spacecraft": 0, "operators": 0, "stations": 0}

    def insert(query, params, key):
        created[key] += conn.execute(query, params).rowcount

    insert("INSERT INTO ops.spacecraft (spacecraft_id, name) VALUES (%s, %s) ON CONFLICT DO NOTHING",
           (spacecraft_id, spacecraft_name or f"{spec.mission_name} ({spacecraft_id})"), "spacecraft")
    people = [(system_operator, "Automation", "SYSTEM")] + list(operators)
    for operator_id, name, role in people:
        insert("INSERT INTO ops.operator (operator_id, display_name, kind, role) VALUES (%s, %s, %s, %s) "
               "ON CONFLICT DO NOTHING", (operator_id, name, _kind(role), role), "operators")
    for station_id, name, lat, lon in stations:
        insert("INSERT INTO ops.ground_station (station_id, name, latitude_deg, longitude_deg) VALUES (%s, %s, %s, %s) "
               "ON CONFLICT DO NOTHING", (station_id, name, lat, lon), "stations")
    return created
