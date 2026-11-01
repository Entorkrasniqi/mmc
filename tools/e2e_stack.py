#!/usr/bin/env python3
"""Start the whole stack on this machine, for the browser tests and for trying the dashboard by hand.

    python tools/e2e_stack.py                       # then open http://127.0.0.1:5173 and sign in with a token from .e2e/tokens.json
    python tools/e2e_stack.py --soc 30 --speedup 5  # a different story: a low battery that stays awake
    python tools/e2e_stack.py --dashboard-port 5174 # when something else already uses port 5173

What it starts, all on 127.0.0.1 and none of it touching your development database or your .env:

    PostgreSQL 16   through the project's own docker-compose.yml (project "minisat-e2e", its own volume and port), so the real
                    init script, the four roles and the lock-down are exercised; then alembic upgrade head and db-seed --demo
    simulator       minisat simulate           the satellite, on UDP ports 20015 / 20025 (not Yamcs' 10015 / 10025)
    ground station  minisat ground             stores telemetry, raises alarms, sends released commands
    API             minisat api                on port 18000, with random DEV-ONLY tokens (written to .e2e/tokens.json)
    dashboard       the Vite dev server        on port 5173, proxying /api to the API

Stop it with Ctrl-C: the processes are stopped and the database container and its volume are removed.
Logs are in .e2e/logs/. Everything in .e2e/ is git-ignored and may hold secrets; it is recreated on every start.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import signal
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from minisat.api.cli import DEMO_OPERATOR_IDS, make_dev_tokens  # noqa: E402

E2E = ROOT / ".e2e"
PROJECT = "minisat-e2e"


def log_file(name: str):
    (E2E / "logs").mkdir(parents=True, exist_ok=True)
    return open(E2E / "logs" / f"{name}.log", "wb")


class Stack:
    def __init__(self, args):
        self.args = args
        self.processes: list[tuple[str, subprocess.Popen]] = []
        self.compose_up = False
        self.env = dict(os.environ)

    # ------------------------------------------------------------------------------------------ helpers
    def run(self, command, **kw):
        return subprocess.run(command, check=True, **kw)

    def spawn(self, name, command, **kw):
        process = subprocess.Popen(command, stdout=log_file(name), stderr=subprocess.STDOUT, start_new_session=True, **kw)
        self.processes.append((name, process))
        self.remember()
        return process

    def wait_for(self, what, check, seconds=90.0):
        deadline = time.time() + seconds
        while time.time() < deadline:
            for name, process in self.processes:
                if process.poll() is not None:
                    raise SystemExit(f"{name} stopped with exit code {process.returncode}: see .e2e/logs/{name}.log")
            try:
                if check():
                    return
            except (urllib.error.URLError, OSError, ValueError):
                pass
            time.sleep(0.5)
        raise SystemExit(f"timed out waiting for {what}")

    # ------------------------------------------------------------------------------------------ steps
    def kill_leftovers(self):
        """A run that was killed (a test runner that gives its server no time to stop) leaves its services behind: stop them."""
        try:
            pids = json.loads((E2E / "pids.json").read_text())
        except (OSError, ValueError):
            return
        for pid in pids:
            try:
                os.killpg(pid, signal.SIGTERM)          # each service leads its own process group
            except (ProcessLookupError, PermissionError):
                pass
        time.sleep(1.0)

    def remember(self):
        (E2E / "pids.json").write_text(json.dumps([p.pid for _, p in self.processes]))

    def configure(self):
        self.kill_leftovers()
        shutil.rmtree(E2E, ignore_errors=True)
        (E2E / "run").mkdir(parents=True)          # the working directory of the services: it has no .env to pick up
        a = self.args
        passwords = {role: secrets.token_hex(16) for role in ("MIGRATOR", "RUNNER", "READER", "INGEST")}
        compose_env = {
            "POSTGRES_PASSWORD": secrets.token_hex(16), "MINISAT_DB_NAME": "minisat", "MINISAT_DB_PORT": str(a.db_port),
            **{f"MINISAT_DB_PASSWORD_{role}": value for role, value in passwords.items()},
        }
        (E2E / "compose.env").write_text("".join(f"{k}={v}\n" for k, v in compose_env.items()))
        (E2E / "compose.env").chmod(0o600)
        tokens_line = make_dev_tokens(DEMO_OPERATOR_IDS)
        tokens = dict(pair.split("=", 1) for pair in tokens_line.split("=", 1)[1].split(","))
        (E2E / "tokens.json").write_text(json.dumps(tokens, indent=2) + "\n")
        (E2E / "tokens.json").chmod(0o600)
        self.env.update({
            "MINISAT_DB_HOST": "127.0.0.1", "MINISAT_DB_PORT": str(a.db_port), "MINISAT_DB_NAME": "minisat",
            **{f"MINISAT_DB_PASSWORD_{role}": value for role, value in passwords.items()},
            "MINISAT_API_DEV_TOKENS": tokens_line.split("=", 1)[1], "MINISAT_API_URL": f"http://127.0.0.1:{a.api_port}",
            "PYTHONUNBUFFERED": "1", "MINISAT_DASHBOARD_PORT": str(a.dashboard_port),
        })
        for stale in ("MINISAT_API_CORS_ORIGINS", "MINISAT_API_LIVE_SOURCE"):
            self.env.pop(stale, None)

    def database(self):
        compose = ["docker", "compose", "--env-file", str(E2E / "compose.env"), "-p", PROJECT, "-f", str(ROOT / "docker-compose.yml")]
        subprocess.run(compose + ["down", "-v"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)   # a leftover of a crash
        self.run(compose + ["up", "-d", "--wait", "db"], cwd=ROOT, stdout=subprocess.DEVNULL)
        self.compose_up = True
        self.compose = compose
        self.run([sys.executable, "-m", "alembic", "upgrade", "head"], cwd=ROOT, env=self.env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.run([sys.executable, "-m", "minisat.cli", "--spec", str(ROOT / "spec" / "minisat.yaml"), "db-seed", "--demo"],
                 cwd=E2E / "run", env=self.env, stdout=subprocess.DEVNULL)

    def services(self):
        a = self.args
        spec = ["--spec", str(ROOT / "spec" / "minisat.yaml")]
        py = [sys.executable, "-m", "minisat.cli"] + spec
        cwd = E2E / "run"
        ports = ["--tm-port", str(a.tm_port), "--tc-port", str(a.tc_port)]
        self.spawn("ground", py + ["ground", "--port", str(a.tm_port), "--tc-port", str(a.tc_port)], cwd=cwd, env=self.env)
        self.spawn("api", py + ["api", "--port", str(a.api_port)] + (["--no-contact-check"] if a.no_contact_check else []), cwd=cwd, env=self.env)
        self.wait_for("the API", lambda: urllib.request.urlopen(f"http://127.0.0.1:{a.api_port}/health/live", timeout=2).status == 200)
        self.spawn("simulator", py + ["simulate", "--soc", str(a.soc), "--speedup", str(a.speedup), "--seed", str(a.seed)] + ports,
                   cwd=cwd, env=self.env)

        def ready():
            try:
                return urllib.request.urlopen(f"http://127.0.0.1:{a.api_port}/health/ready", timeout=2).status == 200
            except urllib.error.HTTPError:
                return False
        self.wait_for("telemetry to reach the database (/health/ready)", ready)
        npm = shutil.which("npm") or "npm"
        self.spawn("dashboard", [npm, "run", "dev"], cwd=ROOT, env=self.env)
        self.wait_for("the dashboard", lambda: urllib.request.urlopen(f"http://127.0.0.1:{a.dashboard_port}/", timeout=2).status == 200)

    def stop(self):
        for name, process in reversed(self.processes):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        for name, process in self.processes:
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
        if self.compose_up:
            subprocess.run(self.compose + ["down", "-v"], cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--soc", type=float, default=14.9, help="initial battery charge in percent (default 14.9: SAFE mode at once, "
                                                           "then a quick recovery in sunlight)")
    p.add_argument("--speedup", type=float, default=20.0, help="simulated seconds per wall-clock second (default 20)")
    p.add_argument("--seed", type=int, default=1)
    p.add_argument("--db-port", type=int, default=55433)
    p.add_argument("--api-port", type=int, default=18000)
    p.add_argument("--dashboard-port", type=int, default=5173, help="where the Vite dev server listens (the browser tests expect 5173)")
    p.add_argument("--tm-port", type=int, default=20015)
    p.add_argument("--tc-port", type=int, default=20025)
    p.add_argument("--no-contact-check", action="store_true", help="release commands without a planned contact window")
    args = p.parse_args()

    stack = Stack(args)
    signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
    try:
        stack.configure()
        print("starting PostgreSQL (docker compose) ...", flush=True)
        stack.database()
        print("starting the ground station, the API, the simulator and the dashboard ...", flush=True)
        stack.services()
        print(f"\nREADY  dashboard http://127.0.0.1:{args.dashboard_port}   API http://127.0.0.1:{args.api_port}/docs   tokens in .e2e/tokens.json\n"
              f"       simulator: soc {args.soc} %, speed-up {args.speedup:g}.  Ctrl-C stops everything and removes the database.", flush=True)
        while True:
            time.sleep(1)
            for name, process in stack.processes:
                if process.poll() is not None:
                    print(f"{name} stopped (exit {process.returncode}); see .e2e/logs/{name}.log", flush=True)
                    return 1
    except KeyboardInterrupt:
        return 0
    finally:
        print("stopping ...", flush=True)
        stack.stop()


if __name__ == "__main__":
    sys.exit(main())
