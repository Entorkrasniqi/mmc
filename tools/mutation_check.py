#!/usr/bin/env python3
"""Does the test suite actually notice mistakes? Inject known bugs one at a time and see.

    python tools/mutation_check.py            # takes a couple of minutes (14 copies, 14 test runs)
    MINISAT_TEST_ADMIN_URL=postgresql://postgres:...@localhost:5432/postgres python tools/mutation_check.py
                                              # also injects 37 more bugs: database grants and constraints, the audit
                                              # trigger, and the rules of the runner, the lifecycle and the automations

For each entry in MUTATIONS the script copies the project to a temporary directory, changes ONE thing (a "mutation":
a deliberately wrong byte order, an off-by-one, a disabled safety check ...), optionally regenerates the XTCE database like a
developer would, and runs the test suite, stopping at the first failure. A mutation that makes no test fail is a hole in
the tests. The real working tree is never touched.

Exit code 0 if every mutation was caught, 1 otherwise.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

CODEC, XTCE, CCSDS, MODEL, SPEC = ("src/minisat/codec.py", "src/minisat/xtce.py", "src/minisat/ccsds.py",
                                   "src/minisat/model.py", "spec/minisat.yaml")
APID_ROW = 'parameterRef="CCSDS_Packet_ID/APID")'
HDR_ROW = 'parameterRef="CCSDS_Packet_ID/SecHdrFlag")'

# (description, file, text to find (must occur once or more), replacement, regenerate the XTCE database afterwards?)
MUTATIONS = [
    ("time field written little-endian", CODEC, 'struct.pack(">Q", sc_time_ms)', 'struct.pack("<Q", sc_time_ms)', False),
    ("floats written little-endian", CODEC, 'struct.pack(">" + t.fmt, float(value))',
     'struct.pack("<" + t.fmt, float(value))', False),
    ("XTCE: command length = bytes instead of bytes - 1", XTCE, "cmd.data_size - 1)", "cmd.data_size)", True),
    ("wrong sequence-flag value", CCSDS, "STANDALONE = 3 ", "STANDALONE = 1 ", False),
    ("sequence count field shifted", CCSDS, "word2 = (h.seq_flags << 14) | h.seq_count",
     "word2 = (h.seq_flags << 13) | h.seq_count", False),
    ("XTCE: warning and critical ranges swapped", XTCE,
     '(("WarningRange", limits.warning), ("CriticalRange", limits.critical))',
     '(("WarningRange", limits.critical), ("CriticalRange", limits.warning))', True),
    ("XTCE: APID restriction off by one", XTCE, "value=pkt.apid, " + APID_ROW, "value=pkt.apid + 1, " + APID_ROW, True),
    ("XTCE: wrong secondary-header restriction", XTCE, 'value="Present", ' + HDR_ROW,
     'value="NotPresent", ' + HDR_ROW, True),
    ("command id off by one", CODEC, 'body = struct.pack(">H", cmd.id)', 'body = struct.pack(">H", cmd.id + 1)', False),
    ("eclipse logic inverted", MODEL, "return math.cos(theta) < threshold", "return math.cos(theta) > threshold", False),
    ("on-board protection (FDIR) disabled", MODEL, "if self.soc < SOC_FDIR and self.mode != MODE_SAFE:", "if False:", False),
    ("on-board range check of SetTmRate disabled", MODEL, "if not (low <= period <= high):", "if False:", False),
    # a description is in the XTCE but asserted by no other test, so only the freshness check can notice it
    ("specification changed, XTCE database not regenerated", SPEC, "Current drawn by the satellite",
     "Current drawn by the whole satellite", False),
    ("field type changed in the specification, XTCE not regenerated", SPEC, "{name: heater,          type: uint8,",
     "{name: heater,          type: uint16,", False),
]

MIGRATION, DATABASE_SQL = "migrations/versions/0001_operations_schema.py", "db/database.sql"
ONT = "src/minisat/ontology/"
COMMANDS, RECORDS, RUNNER = ONT + "actions/commands.py", ONT + "actions/records.py", ONT + "runner.py"
FUNCTIONS, AUTOMATION, INGEST, WORKER = ONT + "functions.py", ONT + "automation.py", ONT + "ingest.py", ONT + "worker.py"
ADMIN_URL_ENV = "MINISAT_TEST_ADMIN_URL"

# Rules the database enforces by itself (protocols/action-runner-and-audit.md). They need a PostgreSQL server,
# so they run only when MINISAT_TEST_ADMIN_URL is set (see tests/dbfixtures.py); otherwise they are listed as skipped.
DB_MUTATIONS = [
    ("runner may DELETE rows", MIGRATION, '"GRANT INSERT, UPDATE ON ops.contact_window, ops.anomaly',
     '"GRANT INSERT, UPDATE, DELETE ON ops.contact_window, ops.anomaly', False),
    ("runner may UPDATE the audit log", MIGRATION,
     '"GRANT INSERT ON ops.anomaly_command_execution, ops.spacecraft_event, ops.audit_log TO',
     '"GRANT INSERT, UPDATE ON ops.anomaly_command_execution, ops.spacecraft_event, ops.audit_log TO', False),
    ("audit log trigger no longer refuses DELETE", MIGRATION, "BEFORE UPDATE OR DELETE ON ops.audit_log",
     "BEFORE UPDATE ON ops.audit_log", False),
    ("reader may write", MIGRATION, '"GRANT SELECT ON ALL TABLES IN SCHEMA ops TO app_reader"',
     '"GRANT ALL ON ALL TABLES IN SCHEMA ops TO app_reader"', False),
    ("ingest may update any spacecraft column", MIGRATION,
     "GRANT UPDATE (latest_values, last_contact_at) ON ops.spacecraft TO ingest",
     "GRANT UPDATE ON ops.spacecraft TO ingest", False),
    ("any role may connect to the database", DATABASE_SQL, "REVOKE ALL ON DATABASE %I FROM PUBLIC",
     "GRANT ALL ON DATABASE %I TO PUBLIC", False),
    ("two-person rule removed", MIGRATION, "CHECK (approved_by IS NULL OR NOT vital OR approved_by <> proposed_by),",
     "CHECK (true),", False),
    ("an agent may approve a command", MIGRATION,
     "FOREIGN KEY (approved_by, approved_by_kind) REFERENCES ops.operator (operator_id, kind),", "", False),
    ("an agent may acknowledge an alarm", MIGRATION,
     "FOREIGN KEY (acknowledged_by, acknowledged_by_kind) REFERENCES ops.operator (operator_id, kind),", "", False),
    ("a command may be sent without an approver", MIGRATION,
     "CHECK (status IN ('PROPOSED', 'CANCELLED') OR approved_by IS NOT NULL),", "CHECK (true),", False),
    ("several open alarms per parameter", MIGRATION, "CREATE UNIQUE INDEX alarm_one_open_per_parameter",
     "CREATE INDEX alarm_one_open_per_parameter", False),
    ("an anomaly may be resolved without a root cause", MIGRATION,
     "CHECK (status <> 'RESOLVED' OR length(btrim(coalesce(root_cause, ''))) > 0),", "CHECK (true),", False),
    ("overlapping contacts on one station", MIGRATION,
     "EXCLUDE USING gist (station_id WITH =, tstzrange(start_at, end_at) WITH &&) WHERE (status <> 'MISSED')",
     "CHECK (true)", False),
    ("an idempotency key may be reused", MIGRATION, "CREATE UNIQUE INDEX audit_log_idempotency",
     "CREATE INDEX audit_log_idempotency", False),
    # ---- the Python rules of the action runner, the command lifecycle and the automations (phases 2 and 3)
    ("any role may run any action", RUNNER, "if operator.role not in action.roles:", "if False:", False),
    ("the same idempotency key with other parameters is accepted", RUNNER, 'row["parameters"] != normalized', "False",
     False),
    ("two-person rule not checked by the runner", COMMANDS, "if op.operator_id == row[\"proposed_by\"]:", "if False:",
     False),
    ("an operator may approve a vital command", COMMANDS,
     'ctx.deny("a VITAL command must be approved by a supervisor")', "pass", False),
    ("an expired proposal can still be approved", COMMANDS, 'if ctx.now >= row["expires_at"]:', "if False:", False),
    ("a predicted rejection does not stop an operator approving", COMMANDS,
     'if op.role != "SUPERVISOR" or _blank(p.note):', "if False:", False),
    ("two commands may be in flight together", COMMANDS, "    if busy:", "    if False:", False),
    ("release without a contact window is allowed", COMMANDS,
     "if contact is None and ctx.config.require_contact:", "if False:", False),
    ("an operator may override the contact requirement", COMMANDS,
     'ctx.deny("only a supervisor may release a command without a contact window")', "pass", False),
    ("an agent may cancel other people's proposals", COMMANDS,
     'if op.role in ("AGENT", "SYSTEM") and not own and not expired_sweep:', "if False:", False),
    ("any outcome may follow any status", COMMANDS, 'if row["status"] not in OUTCOME_FROM[p.outcome]:', "if False:", False),
    ("a failure needs no reason", COMMANDS,
     'if p.outcome in ("REJECTED_ONBOARD", "FAILED") and _blank(p.reason):', "if False:", False),
    ("an anomaly can be resolved without a root cause (checked by the runner)", RECORDS,
     'if _blank(p.root_cause) and _blank(row["root_cause"]):', "if False:", False),
    ("an unplanned SAFE mode is never reported as an FDIR event", FUNCTIONS, '== "SAFE" and not commanded:',
     '== "SAFE" and False:', False),
    ("SAFE mode commanded by SetMode is reported as FDIR", FUNCTIONS, '== "SAFE" and not commanded:', '== "SAFE":', False),
    ("SAFE mode does not show in the health status", FUNCTIONS,
     'if mode_value is not None and mode_label(spec, mode_value) == "SAFE":', "if False:", False),
    ("the sequence counter wrap is ignored", FUNCTIONS, "gap = (seq_count - last - 1) % self.MODULUS",
     "gap = (seq_count - last - 1)", False),
    ("no anomaly for an unplanned SAFE mode", AUTOMATION, "if fdir_events:", "if False:", False),
    ("a command is verified without looking at its effect", AUTOMATION,
     'if effects_met(row["expected_effect"], baseline, current):', "if True:", False),
    ("expired proposals are never cancelled", AUTOMATION, "AND expires_at <= %s\", (sc, now))",
     "AND expires_at <= %s\", (sc, now.replace(year=2000)))", False),
    ("a repeated packet is stored and acted on again", INGEST, "duplicate = stored == 0", "duplicate = False", False),
    ("an old packet overwrites the newest values", INGEST,
     "out_of_order = newest is not None and tm.sc_time_ms < newest", "out_of_order = False", False),
    ("the worker sends a command that is no longer released", WORKER,
     "            self._finish(message, str(exc))\n            return\n", "            self._finish(message, str(exc))\n",
     False),
]


def run_one(description, file, old, new, regenerate, env):
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "project"
        skip = shutil.ignore_patterns(".git", "__pycache__", "*.egg-info", ".pytest_cache", "build", "target", "demo_out",
                                      ".venv", "venv")
        shutil.copytree(ROOT, work, ignore=skip)
        target = work / file
        text = target.read_text(encoding="utf-8")
        if old not in text:
            return None, f"pattern not found in {file} - the mutation list is out of date"
        target.write_text(text.replace(old, new, 1), encoding="utf-8")
        run_env = dict(env, PYTHONPATH=str(work / "src"))
        if regenerate:
            subprocess.run([sys.executable, "-m", "minisat.cli", "gen-xtce"], cwd=work, env=run_env, check=True,
                           stdout=subprocess.DEVNULL)
        command = [sys.executable, "-m", "pytest", "-q", "-x", "-p", "no:cacheprovider", "tests"]
        result = subprocess.run(command, cwd=work, env=run_env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        failed = [line for line in result.stdout.splitlines() if line.startswith("FAILED")]
        return result.returncode != 0, (failed[0][7:110] if failed else "no test failed")


def main() -> int:
    env = dict(os.environ)
    missed = 0
    mutations = list(MUTATIONS)
    if env.get(ADMIN_URL_ENV):
        mutations += DB_MUTATIONS
    else:
        print(f"({len(DB_MUTATIONS)} database mutations skipped: set {ADMIN_URL_ENV} to a PostgreSQL superuser URL)\n")
    for description, file, old, new, regenerate in mutations:
        caught, detail = run_one(description, file, old, new, regenerate, env)
        if caught is None:
            print(f"ERROR   {description}: {detail}")
            missed += 1
        elif caught:
            print(f"caught  {description}\n          by {detail}")
        else:
            print(f"MISSED  {description}")
            missed += 1
    print(f"\n{len(mutations) - missed} of {len(mutations)} mutations caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
