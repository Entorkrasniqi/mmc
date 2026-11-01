"""Command-line interface: ``minisat <command> ...`` (see ``minisat --help``)."""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path
from typing import List, Optional

from . import __version__
from .ccsds import PRIMARY_HEADER_SIZE, PacketError, iter_packets
from .codec import (decode_tm, enum_label, encode_tc, parse_text_value)
from .model import Orbit, Spacecraft
from .simulator import UdpSimulator
from .spec import Spec, SpecError, load_spec
from .xtce import generate_xtce

DEFAULT_SPEC = Path("spec/minisat.yaml")
DEFAULT_XTCE = Path("yamcs/src/main/yamcs/mdb/minisat.xml")


def _spec(args) -> Spec:
    return load_spec(args.spec)


def format_telemetry(spec: Spec, tm) -> str:
    """One readable line per packet: ``Housekeeping #12 t=... mode=NOMINAL cmd_accepted=0 ...``."""
    pkt = spec.tm_by_name(tm.packet)
    parts = []
    for f in pkt.fields:
        value = tm.values[f.name]
        if f.enum:
            label = enum_label(spec, f, value)
            parts.append(f"{f.name}={label if label else value}")
        elif f.type.kind == "float":
            parts.append(f"{f.name}={value:.3f}")
        else:
            parts.append(f"{f.name}={value}")
    stamp = time.strftime("%H:%M:%S", time.gmtime(tm.sc_time_ms / 1000.0))
    return f"{tm.packet:<12} #{tm.seq_count:<5} {stamp}Z  " + "  ".join(parts)


# ------------------------------------------------------------------------------------------------ sub-commands

def cmd_info(args) -> int:
    spec = _spec(args)
    print(f"{spec.mission_name}: {spec.description}")
    print(f"telemetry -> UDP port {spec.tm_port}, telecommands <- UDP port {spec.tc_port} (APID {spec.tc_apid})\n")
    for p in spec.tm_packets:
        print(f"TM {p.name}  APID {p.apid}  every {p.period_s:g} s  ({p.data_size + PRIMARY_HEADER_SIZE} bytes on the wire)")
        print("    (offsets from the start of the packet: +0 primary header, +6 spacecraft time, +14 first field)")
        offset = PRIMARY_HEADER_SIZE + 8
        for f in p.fields:
            extra = f" [{f.unit}]" if f.unit else ""
            extra += f" enum {f.enum}" if f.enum else ""
            print(f"    +{offset:<3} {f.type.name:<8} {f.name}{extra}")
            offset += f.type.size
    print()
    for c in spec.commands:
        sig = "  (vital)" if c.significance else ""
        arg_text = ", ".join(f"{a.name}:{a.type.name}" for a in c.args) or "no arguments"
        print(f"TC {c.name}  id {c.id}  {arg_text}  ({c.data_size + PRIMARY_HEADER_SIZE} bytes){sig}")
    return 0


def cmd_gen_xtce(args) -> int:
    xml = generate_xtce(_spec(args))
    out = Path(args.out)
    if args.check:
        if not out.exists() or out.read_text(encoding="utf-8") != xml:
            print(f"{out} is out of date - run 'minisat gen-xtce' and commit the result", file=sys.stderr)
            return 1
        print(f"{out} is up to date")
        return 0
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(xml, encoding="utf-8")
    print(f"wrote {out} ({len(xml.splitlines())} lines)")
    return 0


def cmd_simulate(args) -> int:
    spec = _spec(args)
    model = Spacecraft(orbit=Orbit(), seed=args.seed, soc=args.soc / 100.0)
    record = open(args.record, "wb") if args.record else None
    sim = UdpSimulator(spec, model, tm_addr=(args.tm_host, args.tm_port or spec.tm_port),
                       tc_bind=(args.tc_host, args.tc_port or spec.tc_port), speedup=args.speedup, record=record,
                       log=lambda msg: print(msg, flush=True))
    print(f"MiniSat simulator: telemetry -> {args.tm_host}:{args.tm_port or spec.tm_port}, "
          f"telecommands on {sim.tc_address[0]}:{sim.tc_address[1]}, speed x{args.speedup:g}, "
          f"battery starts at {args.soc:g} %. Ctrl-C to stop.")
    try:
        sim.run(duration_s=args.duration if args.duration > 0 else None)
    except KeyboardInterrupt:
        pass
    print(f"stopped after {sim.sim.packets_sent} telemetry packets")
    return 0


def cmd_listen(args) -> int:
    import socket
    spec = _spec(args)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port or spec.tm_port))
    sock.settimeout(args.timeout)
    print(f"listening for telemetry on {args.host}:{args.port or spec.tm_port} ...")
    seen = 0
    try:
        while args.count == 0 or seen < args.count:
            try:
                data, _ = sock.recvfrom(65535)
            except socket.timeout:
                print("(timeout: nothing received)")
                return 1
            try:
                print(format_telemetry(spec, decode_tm(spec, data)))
            except PacketError as exc:
                print(f"bad packet ({len(data)} bytes): {exc}")
            seen += 1
    except KeyboardInterrupt:
        pass
    return 0


def cmd_send_tc(args) -> int:
    import socket
    spec = _spec(args)
    try:
        cmd = spec.command_by_name(args.command)
    except KeyError:
        print(f"unknown command {args.command!r}; known: {', '.join(c.name for c in spec.commands)}", file=sys.stderr)
        return 2
    given = {}
    for item in args.arguments:
        if "=" not in item:
            print(f"argument {item!r} must look like name=value", file=sys.stderr)
            return 2
        name, text = item.split("=", 1)
        field = next((a for a in cmd.args if a.name == name), None)
        if field is None:
            print(f"{cmd.name} has no argument {name!r}; arguments: {', '.join(a.name for a in cmd.args) or '(none)'}",
                  file=sys.stderr)
            return 2
        try:
            given[name] = parse_text_value(spec, field, text)
        except PacketError as exc:
            print(exc, file=sys.stderr)
            return 2
    try:
        packet = encode_tc(spec, cmd.name, given)
    except PacketError as exc:
        print(exc, file=sys.stderr)
        return 2
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.sendto(packet, (args.host, args.port or spec.tc_port))
    print(f"sent {cmd.name} {given} ({len(packet)} bytes: {packet.hex(' ')}) to {args.host}:{args.port or spec.tc_port}")
    return 0


def cmd_decode(args) -> int:
    spec = _spec(args)
    data = sys.stdin.buffer.read() if args.file == "-" else Path(args.file).read_bytes()
    count = 0
    try:
        for raw in iter_packets(data):
            print(format_telemetry(spec, decode_tm(spec, raw)))
            count += 1
    except PacketError as exc:
        print(f"error after {count} packets: {exc}", file=sys.stderr)
        return 1
    print(f"{count} packets decoded")
    return 0


def cmd_demo(args) -> int:
    from . import demo
    spec = _spec(args)
    rows = demo.run_scenario(spec, hours=args.hours)
    out = Path(args.out)
    demo.write_csv(rows, out / "scenario.csv")
    print(f"wrote {out / 'scenario.csv'} ({len(rows)} rows)")
    for key, value in demo.summarise(rows).items():
        print(f"  {key}: {value if value is None or isinstance(value, int) else round(value, 3)}")
    if demo.plot(rows, out / "scenario.png", spec):
        print(f"wrote {out / 'scenario.png'}")
    else:
        print("matplotlib is not installed - skipped the picture (pip install matplotlib)")
    return 0


# ------------------------------------------------------------------------------------------------ ontology layer
# These need the database dependencies (pip install -e ".[db]"), so they are imported only when used.

def _need_db_extra(name):
    def run(args):
        try:
            from .ontology import cli as ontology_cli
            return getattr(ontology_cli, name)(args)
        except ModuleNotFoundError as exc:
            print(f"this command needs the database dependencies ({exc.name} is missing): "
                  f"pip install -e \".[db]\"", file=sys.stderr)
            return 2
    return run


def _need_api_extra(name):
    def run(args):
        try:
            from .api import cli as api_cli
            return getattr(api_cli, name)(args)
        except ModuleNotFoundError as exc:
            print(f"this command needs the API dependencies ({exc.name} is missing): pip install -e \".[db,api]\"",
                  file=sys.stderr)
            return 2
    return run


# ------------------------------------------------------------------------------------------------ entry point

def _percent(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"{text!r} is not a number") from None
    if not 0.0 <= value <= 100.0:
        raise argparse.ArgumentTypeError(f"{text} is not between 0 and 100")
    return value


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="minisat", description="Satellite-bus simulator and Yamcs helper tools.")
    parser.add_argument("--version", action="version", version=f"minisat {__version__}")
    parser.add_argument("--spec", default=str(DEFAULT_SPEC), help="mission specification (default: spec/minisat.yaml)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("info", help="print the telemetry/telecommand interface in a readable form").set_defaults(func=cmd_info)

    p = sub.add_parser("gen-xtce", help="generate the XTCE database for Yamcs from the specification")
    p.add_argument("--out", default=str(DEFAULT_XTCE))
    p.add_argument("--check", action="store_true", help="do not write; fail if the file on disk differs")
    p.set_defaults(func=cmd_gen_xtce)

    p = sub.add_parser("simulate", help="run the satellite simulator (UDP telemetry out, UDP telecommands in)")
    p.add_argument("--tm-host", default="127.0.0.1")
    p.add_argument("--tm-port", type=int, default=0, help="default: from the specification")
    p.add_argument("--tc-host", default="127.0.0.1")
    p.add_argument("--tc-port", type=int, default=0, help="default: from the specification")
    p.add_argument("--speedup", type=float, default=1.0, help="simulated seconds per wall-clock second")
    p.add_argument("--duration", type=float, default=0.0, help="stop after this many wall-clock seconds (0 = run forever)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--soc", type=_percent, default=90.0,
                   help="initial battery charge in percent (default 90; try 30 or 18 to see alarms at once)")
    p.add_argument("--record", help="also write every telemetry packet to this file (decode it with 'minisat decode')")
    p.set_defaults(func=cmd_simulate)

    p = sub.add_parser("listen", help="a tiny ground station: print decoded telemetry arriving on a UDP port")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=0)
    p.add_argument("--count", type=int, default=0, help="stop after this many packets (0 = forever)")
    p.add_argument("--timeout", type=float, default=10.0)
    p.set_defaults(func=cmd_listen)

    p = sub.add_parser("send-tc", help="send one telecommand, e.g.  minisat send-tc SetMode mode=PAYLOAD")
    p.add_argument("command")
    p.add_argument("arguments", nargs="*", help="name=value pairs")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=0)
    p.set_defaults(func=cmd_send_tc)

    p = sub.add_parser("decode", help="decode a recording of telemetry packets ('-' reads standard input)")
    p.add_argument("file")
    p.set_defaults(func=cmd_decode)

    p = sub.add_parser("demo", help="offline scenario: simulate hours in a second and write a CSV + picture")
    p.add_argument("--hours", type=float, default=11.0)
    p.add_argument("--out", default="demo_out")
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("db-seed", help="create the spacecraft, the automation account and (with --demo) sample operators")
    p.add_argument("--spacecraft", default="MINISAT-1")
    p.add_argument("--system-operator", default="automation", help="the account the automations act as")
    p.add_argument("--operator", action="append", default=[], metavar="ID:NAME:ROLE",
                   help="add an operator, e.g. alice:Alice:OPERATOR (roles: VIEWER OPERATOR SUPERVISOR AGENT)")
    p.add_argument("--demo", action="store_true",
                   help="add alice, bob, sam, tina, vera, an AI helper and a Helsinki station")
    p.set_defaults(func=_need_db_extra("cmd_db_seed"))

    p = sub.add_parser("ground", help="the ground station: store telemetry, run the automations, send released commands")
    p.add_argument("--spacecraft", default="MINISAT-1")
    p.add_argument("--system-operator", default="automation")
    p.add_argument("--host", default="127.0.0.1", help="where to listen for telemetry")
    p.add_argument("--port", type=int, default=0, help="default: from the specification")
    p.add_argument("--tc-host", default="127.0.0.1", help="where the satellite listens for telecommands")
    p.add_argument("--tc-port", type=int, default=0, help="default: from the specification")
    p.add_argument("--duration", type=float, default=0.0, help="stop after this many seconds (0 = run forever)")
    p.set_defaults(func=_need_db_extra("cmd_ground"))

    p = sub.add_parser("act", help="run an action as an operator, e.g. minisat act alice 'Propose Command' '{...json...}'")
    p.add_argument("operator")
    p.add_argument("action")
    p.add_argument("params", nargs="?", help="the parameters as a JSON object")
    p.add_argument("--no-contact-check", action="store_true",
                   help="release commands without a planned contact window (for the simulator, which is always in contact)")
    p.set_defaults(func=_need_db_extra("cmd_act"))

    sub.add_parser("actions", help="list the actions, who may run them and their parameters").set_defaults(
        func=_need_db_extra("cmd_actions"))

    p = sub.add_parser("status", help="the spacecraft's health, open alarms and anomalies, recent commands and events")
    p.add_argument("--spacecraft", default="MINISAT-1")
    p.set_defaults(func=_need_db_extra("cmd_status"))

    p = sub.add_parser("api", help="the HTTP API of the ontology (needs the api extra): objects, links, series, actions")
    p.add_argument("--host", default="127.0.0.1", help="where to listen (anything but this machine needs --allow-remote)")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--allow-remote", action="store_true",
                   help="listen on a non-loopback address although the only login is a DEV-ONLY static token")
    p.add_argument("--no-contact-check", action="store_true",
                   help="release commands without a planned contact window (for the simulator, which is always in contact)")
    p.add_argument("--log-level", default="INFO", choices=["DEBUG", "INFO", "WARNING", "ERROR"])
    p.set_defaults(func=_need_api_extra("cmd_api"))

    p = sub.add_parser("dev-tokens", help="make DEV-ONLY API tokens: prints the MINISAT_API_DEV_TOKENS line for .env")
    p.add_argument("operators", nargs="*", help="operator ids (default: the demo operators of 'db-seed --demo')")
    p.set_defaults(func=_need_api_extra("cmd_dev_tokens"))
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except SpecError as exc:
        print(f"specification error: {exc}", file=sys.stderr)
        return 2
    except FileNotFoundError as exc:
        print(f"file not found: {exc.filename}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
