"""Settings, dev tokens and logging set-up of the API. No database and no web framework needed."""
import json
import logging

import pytest

from minisat.api.cli import DEMO_OPERATOR_IDS, make_dev_tokens
from minisat.api.logs import JsonFormatter, configure_logging
from minisat.api.settings import DEFAULT_CORS_ORIGINS, MIN_TOKEN_LENGTH, ApiSettings, parse_dev_tokens
from minisat.cli import main
from minisat.ontology.dbconfig import ConfigError

GOOD = "x" * MIN_TOKEN_LENGTH


def test_tokens_parse_into_operator_token_pairs():
    assert parse_dev_tokens("") == () and parse_dev_tokens(" , ,") == ()
    assert parse_dev_tokens(f"alice={GOOD}") == (("alice", GOOD),)
    other = "y" * 20
    assert parse_dev_tokens(f" alice = {GOOD} , sam={other} ") == (("alice", GOOD), ("sam", other))
    assert parse_dev_tokens("alice=" + "a=b=" * 5) == (("alice", "a=b=" * 5),)           # only the first '=' separates


@pytest.mark.parametrize("text, message", [
    ("alice", "must look like"), ("alice=", "must look like"), ("=" + GOOD, "must look like"),
    (f"alice={'x' * (MIN_TOKEN_LENGTH - 1)}", "shorter than 16"),
    (f"alice={GOOD},alice={'y' * 20}", "same operator twice"), (f"alice={GOOD},sam={GOOD}", "same token to two operators"),
])
def test_bad_token_settings_are_refused_with_a_reason(text, message):
    with pytest.raises(ConfigError, match=message):
        parse_dev_tokens(text)


def test_the_defaults_let_nobody_in_and_allow_only_the_local_dashboard():
    settings = ApiSettings.from_env({})
    assert settings.dev_tokens == () and settings.cors_origins == DEFAULT_CORS_ORIGINS
    assert settings.live_source is True and settings.docs is True
    assert all(o.startswith("http://127.0.0.1") or o.startswith("http://localhost") for o in DEFAULT_CORS_ORIGINS)


def test_settings_are_read_from_the_environment():
    settings = ApiSettings.from_env({"MINISAT_API_DEV_TOKENS": f"alice={GOOD}", "MINISAT_API_LIVE_SOURCE": "0",
                                     "MINISAT_API_DOCS": "false", "MINISAT_API_CORS_ORIGINS": "https://a.example, https://b.example"})
    assert settings.dev_tokens == (("alice", GOOD),) and settings.live_source is False and settings.docs is False
    assert settings.cors_origins == ("https://a.example", "https://b.example")


@pytest.mark.parametrize("env, message", [
    ({"MINISAT_API_CORS_ORIGINS": "*"}, "not '\\*'"), ({"MINISAT_API_CORS_ORIGINS": "http://a, *"}, "not '\\*'"),
    ({"MINISAT_API_LIVE_SOURCE": "maybe"}, "must be 1 or 0"), ({"MINISAT_API_DOCS": "2"}, "must be 1 or 0"),
])
def test_wrong_settings_are_refused(env, message):
    with pytest.raises(ConfigError, match=message):
        ApiSettings.from_env(env)


# ------------------------------------------------------------------------------------------------ minisat dev-tokens

def test_generated_tokens_are_long_random_distinct_and_accepted_by_the_parser():
    line = make_dev_tokens(["alice", "sam", "tina"])
    assert line.startswith("MINISAT_API_DEV_TOKENS=")
    pairs = parse_dev_tokens(line.split("=", 1)[1])
    assert [o for o, _ in pairs] == ["alice", "sam", "tina"]
    assert len({t for _, t in pairs}) == 3 and all(len(t) >= 43 for _, t in pairs)         # 32 random bytes in base64
    assert make_dev_tokens(["alice"]) != make_dev_tokens(["alice"])                         # new every time


@pytest.mark.parametrize("operators", [["bad id"], ["a,b"], ["x=y"], ["alice", "alice"], [""]])
def test_dev_tokens_refuses_ids_it_could_not_parse_back(operators):
    with pytest.raises(ValueError):
        make_dev_tokens(operators)


def test_the_dev_tokens_command_defaults_to_the_demo_operators(capsys):
    assert main(["dev-tokens"]) == 0
    out = capsys.readouterr().out
    assert "DEV ONLY" in out
    pairs = parse_dev_tokens(out.strip().splitlines()[-1].split("=", 1)[1])
    assert tuple(o for o, _ in pairs) == DEMO_OPERATOR_IDS == ("alice", "bob", "sam", "tina", "vera", "helper")


def test_the_dev_tokens_command_reports_a_bad_id(capsys):
    assert main(["dev-tokens", "not valid"]) == 2
    assert "not a usable operator id" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------ minisat api

def test_the_api_refuses_to_listen_beyond_this_machine_with_dev_tokens(capsys, monkeypatch, tmp_path):
    pytest.importorskip("uvicorn")
    pytest.importorskip("fastapi")
    pytest.importorskip("psycopg")
    monkeypatch.chdir(tmp_path)                                    # no .env here
    for host in ("0.0.0.0", "192.168.1.20", "example.com", "::"):
        assert main(["api", "--host", host]) == 2
        assert "refusing to listen" in capsys.readouterr().err


# ------------------------------------------------------------------------------------------------ logging set-up

@pytest.fixture()
def restore_logging():
    names = ("minisat", "uvicorn.error", "uvicorn.access")
    saved = {n: (logging.getLogger(n).handlers[:], logging.getLogger(n).propagate, logging.getLogger(n).level,
                 logging.getLogger(n).disabled) for n in names}
    yield
    for n, (handlers, propagate, level, disabled) in saved.items():
        logger = logging.getLogger(n)
        logger.handlers[:], logger.propagate, logger.disabled = handlers, propagate, disabled
        logger.setLevel(level)


def test_configure_logging_writes_json_to_standard_output(capsys, restore_logging):
    configure_logging(logging.INFO)
    logging.getLogger("minisat.api.test").info("hello %s", "world")
    logging.getLogger("minisat.api.test").debug("not shown at INFO")
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 1
    data = json.loads(lines[0])
    assert (data["level"], data["message"], data["logger"]) == ("INFO", "hello world", "minisat.api.test")
    assert isinstance(logging.getLogger("minisat").handlers[0].formatter, JsonFormatter)
    assert logging.getLogger("uvicorn.access").disabled is True                # the API logs its own requests
