import socket
import threading
import time

import pytest

from minisat.cli import main
from minisat.codec import decode_tc, decode_tm, encode_tm
from minisat.xtce import generate_xtce

from conftest import SPEC_PATH, XTCE_PATH
from test_codec import HK_VALUES


def run(capsys, *argv):
    code = main(["--spec", str(SPEC_PATH), *argv])
    out = capsys.readouterr()
    return code, out.out, out.err


def free_udp_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_info_describes_the_interface(capsys):
    code, out, _ = run(capsys, "info")
    assert code == 0
    assert "MiniSat" in out and "Housekeeping  APID 100" in out and "battery_soc_pct" in out
    assert "TC Reboot  id 4" in out and "(vital)" in out and "SetTmRate" in out and "period_s:float32" in out


def test_version(capsys):
    with pytest.raises(SystemExit) as stop:
        main(["--version"])
    assert stop.value.code == 0 and capsys.readouterr().out.startswith("minisat ")


def test_gen_xtce_writes_a_file_and_check_notices_staleness(capsys, tmp_path):
    out = tmp_path / "deep" / "db.xml"
    assert run(capsys, "gen-xtce", "--out", str(out))[0] == 0
    assert out.read_text(encoding="utf-8") == XTCE_PATH.read_text(encoding="utf-8")
    assert run(capsys, "gen-xtce", "--out", str(out), "--check")[0] == 0
    out.write_text(out.read_text(encoding="utf-8").replace("MiniSat", "Other", 1), encoding="utf-8")
    code, _, err = run(capsys, "gen-xtce", "--out", str(out), "--check")
    assert code == 1 and "out of date" in err
    assert run(capsys, "gen-xtce", "--out", str(tmp_path / "missing.xml"), "--check")[0] == 1


def test_committed_xtce_passes_the_check_through_the_cli(capsys):
    assert run(capsys, "gen-xtce", "--out", str(XTCE_PATH), "--check")[0] == 0


def test_send_tc_puts_the_right_bytes_on_the_wire(capsys, spec):
    rx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx.bind(("127.0.0.1", 0))
    rx.settimeout(2)
    port = rx.getsockname()[1]
    code, out, _ = run(capsys, "send-tc", "SetMode", "mode=PAYLOAD", "--port", str(port))
    data, _ = rx.recvfrom(100)
    rx.close()
    assert code == 0 and "sent SetMode" in out
    cmd, args, _ = decode_tc(spec, data)
    assert cmd.name == "SetMode" and args == {"mode": 2}


@pytest.mark.parametrize("argv,message", [
    (["send-tc", "Explode"], "unknown command"),
    (["send-tc", "SetMode"], "missing argument"),
    (["send-tc", "SetMode", "mode"], "name=value"),
    (["send-tc", "SetMode", "mood=SAFE"], "no argument"),
    (["send-tc", "SetMode", "mode=WARP"], "not one of"),
    (["send-tc", "SetTmRate", "period_s=0.01"], "outside the allowed range"),
    (["send-tc", "SetTmRate", "period_s=soon"], "not a number"),
    (["send-tc", "Noop", "x=1"], "no argument"),
])
def test_send_tc_reports_mistakes_with_exit_code_2_and_sends_nothing(capsys, argv, message):
    code, out, err = run(capsys, *argv, "--port", str(free_udp_port()))
    assert code == 2 and message in err and "sent" not in out


def test_decode_reads_a_recording_and_reports_damage(capsys, spec, tmp_path):
    packets = [encode_tm(spec, "Housekeeping", HK_VALUES, 1_792_800_000_000 + i * 1000, i) for i in range(3)]
    packets.append(encode_tm(spec, "Position", dict(latitude_deg=1.5, longitude_deg=-2.5, altitude_km=560), 0, 0))
    recording = tmp_path / "tm.bin"
    recording.write_bytes(b"".join(packets))
    code, out, _ = run(capsys, "decode", str(recording))
    assert code == 0 and "4 packets decoded" in out and "mode=NOMINAL" in out and "heater=ON" in out
    assert "latitude_deg=1.500" in out and "in_eclipse=NO" in out
    recording.write_bytes(b"".join(packets) + packets[0][:-5])
    code, out, err = run(capsys, "decode", str(recording))
    assert code == 1 and "truncated" in err and "error after 4 packets" in err


def test_unreadable_inputs_give_exit_code_2(capsys, tmp_path):
    assert run(capsys, "decode", str(tmp_path / "nope.bin"))[0] == 2
    code = main(["--spec", str(tmp_path / "nope.yaml"), "info"])
    assert code == 2 and "file not found" in capsys.readouterr().err
    bad = tmp_path / "bad.yaml"
    bad.write_text("mission: {name: X}\n", encoding="utf-8")
    code = main(["--spec", str(bad), "info"])
    assert code == 2 and "specification error" in capsys.readouterr().err


def test_listen_prints_decoded_telemetry(capsys, spec):
    port = free_udp_port()
    packet = encode_tm(spec, "Housekeeping", HK_VALUES, 1_792_800_000_000, 5)

    def send_later():
        tx = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        for _ in range(40):                                    # keep sending until the listener is up and has taken one
            tx.sendto(packet, ("127.0.0.1", port))
            tx.sendto(b"junk", ("127.0.0.1", port))
            time.sleep(0.05)
        tx.close()

    t = threading.Thread(target=send_later, daemon=True)
    t.start()
    code, out, _ = run(capsys, "listen", "--port", str(port), "--count", "2", "--timeout", "3")
    t.join()
    assert code == 0 and "Housekeeping" in out and "#5" in out and "battery_soc_pct=81.250" in out


def test_listen_times_out_politely(capsys):
    code, out, _ = run(capsys, "listen", "--port", str(free_udp_port()), "--timeout", "0.2")
    assert code == 1 and "timeout" in out


def test_simulate_records_telemetry_that_decode_understands(capsys, tmp_path):
    rec = tmp_path / "rec.bin"
    sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sink.bind(("127.0.0.1", 0))
    code, out, _ = run(capsys, "simulate", "--tm-port", str(sink.getsockname()[1]), "--tc-port", str(free_udp_port()),
                       "--speedup", "200", "--duration", "0.6", "--record", str(rec))
    sink.close()
    assert code == 0 and "stopped after" in out
    code, out, _ = run(capsys, "decode", str(rec))
    assert code == 0 and "packets decoded" in out and "Housekeeping" in out


def test_simulate_starts_with_the_requested_battery_charge(capsys, spec, tmp_path):
    rec = tmp_path / "rec.bin"
    sink = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sink.bind(("127.0.0.1", 0))
    code, out, _ = run(capsys, "simulate", "--tm-port", str(sink.getsockname()[1]), "--tc-port", str(free_udp_port()),
                       "--duration", "0.3", "--soc", "18", "--record", str(rec))
    sink.close()
    assert code == 0 and "battery starts at 18 %" in out
    from minisat.ccsds import iter_packets
    first = decode_tm(spec, next(iter_packets(rec.read_bytes())))
    assert first.values["battery_soc_pct"] == pytest.approx(18.0, abs=0.01)


@pytest.mark.parametrize("bad", ["-1", "101", "full"])
def test_simulate_rejects_a_battery_charge_outside_0_to_100(capsys, bad):
    with pytest.raises(SystemExit) as stop:
        main(["--spec", str(SPEC_PATH), "simulate", "--soc", bad])
    assert stop.value.code == 2 and "--soc" in capsys.readouterr().err


def test_demo_writes_csv(capsys, tmp_path):
    code, out, _ = run(capsys, "demo", "--hours", "1.5", "--out", str(tmp_path))
    assert code == 0 and (tmp_path / "scenario.csv").exists() and "first_warning_h" in out


def test_generator_output_is_independent_of_the_working_directory(spec, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert generate_xtce(spec) == XTCE_PATH.read_text(encoding="utf-8")
