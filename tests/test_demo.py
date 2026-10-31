import pytest

from minisat import demo


def test_scenario_tells_the_intended_story(spec):
    rows = demo.run_scenario(spec)
    s = demo.summarise(rows)
    # 1 h: PAYLOAD command -> the battery drains through warning (35 %) and critical (20 %) until the on-board
    # protection (15 %) forces SAFE mode; the 6.5 h PAYLOAD command is refused; 8 h NOMINAL is accepted.
    assert 1.0 < s["first_warning_h"] < s["first_critical_h"] < s["first_safe_after_payload_h"] < 6.5
    assert s["min_soc_pct"] < 15.0                                    # it did dip below the protection threshold
    assert s["min_voltage_v"] < 6.4                                   # voltage reached the critical alarm too
    assert (s["final_cmd_accepted"], s["final_cmd_rejected"]) == (2, 1)
    assert rows[-1]["mode"] == 1 and rows[-1]["battery_soc_pct"] > 40   # recovered to NOMINAL with a healthy battery


def test_scenario_is_reproducible(spec):
    a, b = demo.run_scenario(spec, hours=2.0), demo.run_scenario(spec, hours=2.0)
    assert a == b


def test_scenario_rows_are_evenly_spaced_and_complete(spec):
    rows = demo.run_scenario(spec, hours=1.0, sample_s=60.0)
    assert len(rows) in (60, 61)
    assert rows[1]["hours"] - rows[0]["hours"] == pytest.approx(60 / 3600, abs=1e-4)
    assert {"hours", "mode", "battery_soc_pct", "in_eclipse"} <= set(rows[0])


def test_csv_and_plot_are_written(spec, tmp_path):
    rows = demo.run_scenario(spec, hours=1.5)
    demo.write_csv(rows, tmp_path / "sub" / "x.csv")
    lines = (tmp_path / "sub" / "x.csv").read_text().splitlines()
    assert lines[0].startswith("hours,mode,") and len(lines) == len(rows) + 1
    try:
        import matplotlib  # noqa: F401
    except ImportError:
        assert demo.plot(rows, tmp_path / "p.png", spec) is False
    else:
        assert demo.plot(rows, tmp_path / "p.png", spec) is True
        assert (tmp_path / "p.png").read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"
