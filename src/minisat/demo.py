"""An offline demo: run the satellite for several hours of simulated time in a second or two, with a scripted operator.

No sockets and no waiting - the :class:`~minisat.simulator.Simulator` is simply advanced in big steps and the packets
are decoded straight from the list. The result is a table (CSV) and, if matplotlib is installed, a picture that shows
how the power system reacts to the operator's commands.
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import List, Sequence, Tuple

from .codec import decode_tm, encode_tc
from .model import Orbit, Spacecraft
from .simulator import Simulator
from .spec import Spec

# (time in simulated hours, command name, arguments)
DEFAULT_SCRIPT: Tuple[Tuple[float, str, dict], ...] = (
    (1.0, "SetMode", {"mode": "PAYLOAD"}),       # start taking science data - and watch the battery pay for it
    (6.5, "SetMode", {"mode": "PAYLOAD"}),       # the operator tries again too early: the satellite refuses (battery low)
    (8.0, "SetMode", {"mode": "NOMINAL"}),       # the battery has recovered; go back to the safe routine
)


def run_scenario(spec: Spec, hours: float = 11.0, script: Sequence = DEFAULT_SCRIPT, seed: int = 1,
                 sample_s: float = 30.0, epoch_ms: int = 1_792_800_000_000, initial_soc: float = 0.55) -> List[dict]:
    """Simulate ``hours`` hours, executing the scripted commands; return one row per ``sample_s`` seconds.

    The satellite starts with a half-full battery (``initial_soc``), as if it had been busy for a while - that makes
    the interesting part of the story happen sooner.
    """
    packets: List[bytes] = []
    model = Spacecraft(orbit=Orbit(), seed=seed, soc=initial_soc)
    sim = Simulator(spec, model, packets.append, epoch_ms=epoch_ms)
    pending = sorted(script, key=lambda item: item[0])
    rows: List[dict] = []
    t_end = hours * 3600.0
    next_sample = 0.0
    while sim.t < t_end:
        while pending and pending[0][0] * 3600.0 <= sim.t + 1e-9:
            _, name, args = pending.pop(0)
            sim.handle_telecommand(encode_tc(spec, name, args))
        sim.advance(min(sample_s, t_end - sim.t) if sim.t > 0 else 0.0)
        if sim.t + 1e-9 >= next_sample:
            hk = [decode_tm(spec, p) for p in packets if decode_tm(spec, p).packet == "Housekeeping"][-1]
            row = {"hours": round(sim.t / 3600.0, 5)}
            row.update(hk.values)
            rows.append(row)
            next_sample += sample_s
        packets.clear()                                         # keep memory flat; the last HK was already used
        if sim.t == 0.0:
            sim.advance(1e-6)                                   # nudge past t = 0 so the loop makes progress
            packets.clear()
    return rows


def write_csv(rows: Sequence[dict], path) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
        writer.writeheader()
        for row in rows:
            writer.writerow({k: (f"{v:.4f}" if isinstance(v, float) else v) for k, v in row.items()})


def plot(rows: Sequence[dict], path, spec: Spec, script: Sequence = DEFAULT_SCRIPT) -> bool:
    """Draw the scenario. Returns False if matplotlib is not installed."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        return False

    hours = [r["hours"] for r in rows]
    colours = {"blue": "#0072B2", "orange": "#D55E00", "green": "#009E73", "pink": "#CC79A7", "grey": "#7B7B7B"}
    fig, axes = plt.subplots(4, 1, figsize=(10, 9), sharex=True, constrained_layout=True)

    # shade the eclipses and mark the commands on every panel
    def decorate(ax):
        in_shadow = [r["in_eclipse"] for r in rows]
        start = None
        for h, flag in zip(hours + [hours[-1]], in_shadow + [0]):
            if flag and start is None:
                start = h
            if not flag and start is not None:
                ax.axvspan(start, h, color="#999999", alpha=0.15, linewidth=0)
                start = None
        for t, name, args in script:
            ax.axvline(t, color=colours["pink"], linestyle="--", linewidth=1.2)
        ax.grid(alpha=0.25)

    ax = axes[0]
    ax.plot(hours, [r["battery_soc_pct"] for r in rows], color=colours["blue"], linewidth=1.8)
    last = hours[-1]
    for level, text, colour, dy in ((35, "warning 35 %", colours["orange"], 1.5), (20, "critical 20 %", "#B00000", 1.5),
                                    (15, "on-board protection 15 %", "black", -6.5)):
        ax.axhline(level, color=colour, linestyle=":")
        ax.text(last, level + dy, text, color=colour, fontsize=8, ha="right")
    ax.set_ylabel("battery charge (%)")
    ax.set_ylim(0, 105)
    row, previous = 0, None
    for t, name, args in script:
        # was this command refused? compare the rejected-command counter just before and just after it
        before = next((r for r in reversed(rows) if r["hours"] < t), rows[0])
        after = next((r for r in rows if r["hours"] > t + 0.003), rows[-1])
        verdict = " (rejected)" if after["cmd_rejected"] > before["cmd_rejected"] else ""
        # labels of commands that follow each other closely go on a second row so that they do not overlap
        row = 1 - row if previous is not None and t - previous < 2.5 else 0
        previous = t
        ax.text(t + 0.06, 97 - 11 * row, f"{name} {','.join(str(v) for v in args.values())}{verdict}",
                color=colours["pink"], fontsize=8, va="top")
    decorate(ax)

    ax = axes[1]
    ax.plot(hours, [r["battery_voltage"] for r in rows], color=colours["green"], linewidth=1.5)
    ax.axhline(6.8, color=colours["orange"], linestyle=":")
    ax.axhline(6.4, color="#B00000", linestyle=":")
    ax.set_ylabel("battery voltage (V)")
    decorate(ax)

    ax = axes[2]
    ax.plot(hours, [r["solar_current_a"] for r in rows], color=colours["orange"], linewidth=1.3, label="solar panels (in)")
    ax.plot(hours, [r["load_current_a"] for r in rows], color=colours["blue"], linewidth=1.3, label="satellite load (out)")
    ax.set_ylabel("current (A)")
    ax.set_ylim(-0.05, 1.65)
    ax.legend(loc="upper right", fontsize=8, ncol=2)
    decorate(ax)

    ax = axes[3]
    mode_names = {v: k for k, v in spec.enums["Mode"].items()}
    ax.step(hours, [r["mode"] for r in rows], where="post", color=colours["grey"], linewidth=1.8)
    ax.set_yticks(sorted(mode_names))
    ax.set_yticklabels([mode_names[k] for k in sorted(mode_names)])
    ax.set_ylabel("mode")
    ax.set_xlabel("simulated time (hours)")
    decorate(ax)

    fig.suptitle("MiniSat power system under a scripted operator (grey bands = eclipse, dashed lines = commands sent)",
                 fontsize=11)
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110)
    plt.close(fig)
    return True


def summarise(rows: Sequence[dict]) -> dict:
    """The key moments of a scenario run, as simulated hours (None if it never happened)."""
    def first(pred):
        return next((r["hours"] for r in rows if pred(r)), None)
    return {
        "first_warning_h": first(lambda r: r["battery_soc_pct"] < 35.0),
        "first_critical_h": first(lambda r: r["battery_soc_pct"] < 20.0),
        "first_safe_after_payload_h": next((r["hours"] for r in rows if r["mode"] == 0 and r["hours"] > 1.0), None),
        "min_soc_pct": min(r["battery_soc_pct"] for r in rows),
        "min_voltage_v": min(r["battery_voltage"] for r in rows),
        "final_cmd_accepted": rows[-1]["cmd_accepted"],
        "final_cmd_rejected": rows[-1]["cmd_rejected"],
    }
