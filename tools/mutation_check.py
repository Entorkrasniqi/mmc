#!/usr/bin/env python3
"""Does the test suite actually notice mistakes? Inject known bugs one at a time and see.

    python tools/mutation_check.py            # takes a couple of minutes (14 copies, 14 test runs)

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
    ("specification changed, XTCE database not regenerated", SPEC, "period_s: 5.0", "period_s: 4.0", False),
    ("field type changed in the specification, XTCE not regenerated", SPEC, "{name: heater,          type: uint8,",
     "{name: heater,          type: uint16,", False),
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
    for description, file, old, new, regenerate in MUTATIONS:
        caught, detail = run_one(description, file, old, new, regenerate, env)
        if caught is None:
            print(f"ERROR   {description}: {detail}")
            missed += 1
        elif caught:
            print(f"caught  {description}\n          by {detail}")
        else:
            print(f"MISSED  {description}")
            missed += 1
    print(f"\n{len(MUTATIONS) - missed} of {len(MUTATIONS)} mutations caught")
    return 1 if missed else 0


if __name__ == "__main__":
    sys.exit(main())
