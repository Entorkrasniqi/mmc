"""Command-line entry points of the ontology layer: ``minisat db-seed | ground | act | actions | status``.

They read the database settings from the environment (MINISAT_DB_*); for convenience a ``.env`` file in the current
directory is loaded first (variables already set in the environment win).
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from ..spec import load_spec

__all__ = ["cmd_db_seed", "cmd_ground", "cmd_act", "cmd_actions", "cmd_status"]


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def _stamp() -> str:
    return time.strftime("%H:%M:%S")


def _guard(func):
    """Turn a missing setting or an unreachable database into a message and an exit code, not a traceback."""
    def wrapper(args):
        _load_dotenv()
        from .dbconfig import ConfigError
        import psycopg
        try:
            return func(args)
        except ConfigError as exc:
            print(f"configuration error: {exc}", file=sys.stderr)
            return 2
        except psycopg.OperationalError as exc:
            print(f"cannot reach the database: {str(exc).strip()}\n(is 'docker compose up -d db' running, and the "
                  f"migrations applied with 'alembic upgrade head'?)", file=sys.stderr)
            return 1
    return wrapper


@_guard
def cmd_db_seed(args) -> int:
    from . import seed
    from .dbconfig import connect
    spec = load_spec(args.spec)
    try:
        operators = [seed.parse_operator(text) for text in args.operator]
    except ValueError as exc:
        print(exc, file=sys.stderr)
        return 2
    if args.demo:
        operators = list(seed.DEMO_OPERATORS) + operators
    with connect("migrator") as conn:
        created = seed.seed_reference_data(conn, spec, args.spacecraft, operators, args.system_operator,
                                           seed.DEMO_STATIONS if args.demo else ())
    print("created: " + ", ".join(f"{n} {k}" for k, n in created.items()) + "  (0 = it already existed)")
    return 0


@_guard
def cmd_ground(args) -> int:
    from .dbconfig import connect
    from .ground import build_ground_station
    spec = load_spec(args.spec)
    station = build_ground_station(
        spec, args.spacecraft, connect, tc_addr=(args.tc_host, args.tc_port or spec.tc_port),
        tm_bind=(args.host, args.port or spec.tm_port), system_operator=args.system_operator,
        log=lambda message: print(f"{_stamp()}  {message}", flush=True),
        notify=lambda payload: print(f"{_stamp()}  NOTIFY supervisors: {payload}", flush=True))
    print(f"ground station for {args.spacecraft}: telemetry on {station.tm_address[0]}:{station.tm_address[1]}, "
          f"telecommands to {args.tc_host}:{args.tc_port or spec.tc_port}. Ctrl-C to stop.")
    try:
        station.run(args.duration if args.duration > 0 else None)
    except KeyboardInterrupt:
        pass
    print(f"stopped after {station.packets} telemetry packets")
    return 0


@_guard
def cmd_act(args) -> int:
    from .actions import default_registry
    from .dbconfig import connect
    from .runner import ActionError, ActionRunner, RunnerConfig
    spec = load_spec(args.spec)
    try:
        params = json.loads(args.params) if args.params else {}
    except json.JSONDecodeError as exc:
        print(f"the parameters are not valid JSON: {exc}", file=sys.stderr)
        return 2
    if not isinstance(params, dict):
        print("the parameters must be a JSON object, e.g. '{\"execution_id\": \"...\"}'", file=sys.stderr)
        return 2
    runner = ActionRunner(lambda: connect("runner"), spec, default_registry(),
                          config=RunnerConfig(require_contact=not args.no_contact_check))
    try:
        result = runner.run(args.operator, args.action, params)
    except ActionError as exc:
        print(f"{exc.outcome}: {exc}  (audit #{exc.audit_id})", file=sys.stderr)
        return 2 if exc.outcome in ("DENIED", "INVALID") else 1
    print(json.dumps({"action": result.action, "audit_id": result.audit_id, "result": result.result,
                      "warnings": list(result.warnings)}, indent=2))
    return 0


def cmd_actions(args) -> int:
    from .actions import default_registry
    for action in default_registry():
        flags = ["agent may call it"] if action.agent_callable else []
        print(f"{action.name}   [{', '.join(sorted(action.roles))}]" + (f"   ({'; '.join(flags)})" if flags else ""))
        print(f"    {action.description}")
        schema = action.json_schema()
        required = set(schema.get("required", ()))
        for name, prop in schema.get("properties", {}).items():
            kind = prop.get("type") or "/".join(t.get("type", "?") for t in prop.get("anyOf", ()) if "type" in t)
            print(f"      {name}{'' if name in required else ' (optional)'}: {kind}")
    return 0


@_guard
def cmd_status(args) -> int:
    from .dbconfig import connect
    spec = load_spec(args.spec)
    mode_names = {v: k for k, v in spec.enums["Mode"].items()}
    with connect("reader") as conn:
        sc = conn.execute("SELECT * FROM ops.spacecraft WHERE spacecraft_id = %s", (args.spacecraft,)).fetchone()
        if sc is None:
            print(f"no spacecraft {args.spacecraft!r}: run 'minisat db-seed' first", file=sys.stderr)
            return 2
        v = sc["latest_values"]
        age = f"{(time.time() - sc['last_contact_at'].timestamp()):.0f} s ago" if sc["last_contact_at"] else "never"
        print(f"{sc['spacecraft_id']}  {sc['name']}  health: {sc['health_status']}  last contact: {age}")
        if v:
            fields = [
                ("mode", mode_names.get(v.get("mode"), v.get("mode"))),
                ("battery", f"{v.get('battery_soc_pct', 0):.1f} %"),
                ("voltage", f"{v.get('battery_voltage', 0):.2f} V"),
                ("temp", f"{v.get('battery_temp_c', 0):.1f} C"),
                ("eclipse", "yes" if v.get("in_eclipse") else "no"),
                ("heater", "on" if v.get("heater") else "off"),
                ("uptime", f"{v.get('uptime_s', 0)} s"),
                ("accepted/rejected", f"{v.get('cmd_accepted')}/{v.get('cmd_rejected')}"),
            ]
            print("  " + "   ".join(f"{k}: {val}" for k, val in fields))
        sections = [
            ("open alarms", "SELECT parameter_name, severity, state, trigger_value, limit_violated FROM ops.alarm "
                            "WHERE spacecraft_id = %s AND state <> 'CLEARED' ORDER BY raised_at",
             lambda r: (f"{r['severity']:<8} {r['parameter_name']} = {r['trigger_value']:.2f} "
                        f"({r['limit_violated']}) [{r['state']}]")),
            ("open anomalies", "SELECT title, severity, status FROM ops.anomaly WHERE spacecraft_id = %s "
                               "AND status <> 'RESOLVED' ORDER BY detected_at",
             lambda r: f"{r['severity']:<6} {r['title']} [{r['status']}]"),
            ("recent commands", "SELECT execution_id, command_name, status, proposed_by, reason FROM ops.command_execution "
                                "WHERE spacecraft_id = %s ORDER BY proposed_at DESC LIMIT 8",
             lambda r: (f"{str(r['execution_id'])[:8]}  {r['command_name']:<10} {r['status']:<17} "
                        f"by {r['proposed_by']}: {r['reason']}")),
            ("recent events", "SELECT occurred_at, event_type, details FROM ops.spacecraft_event WHERE spacecraft_id = %s "
                              "ORDER BY occurred_at DESC LIMIT 8",
             lambda r: f"{r['occurred_at'].astimezone():%H:%M:%S}  {r['event_type']:<17} {json.dumps(r['details'])}"),
        ]
        for title, query, fmt in sections:
            rows = conn.execute(query, (args.spacecraft,)).fetchall()
            print(f"{title}:" + (" none" if not rows else ""))
            for row in rows:
                print("  " + fmt(row))
    return 0
