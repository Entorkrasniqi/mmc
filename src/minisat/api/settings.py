"""Settings of the HTTP API. Read from environment variables, never from code (protocols/security-and-threat-model.md).

    MINISAT_API_DEV_TOKENS    DEV ONLY. "alice=<token>,sam=<token>": one static bearer token per operator. Unset = nobody can log in.
    MINISAT_API_CORS_ORIGINS  the dashboard origin(s), comma separated (default: the Vite dev server on this machine)
    MINISAT_API_LIVE_SOURCE   1 (default): /health/ready also wants fresh telemetry; 0: the stack has no live telemetry source
    MINISAT_API_DOCS          1 (default): serve /docs and /openapi.json; 0 turns them off
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Optional, Tuple

from ..ontology.dbconfig import ConfigError

__all__ = ["ApiSettings", "DEFAULT_CORS_ORIGINS", "MIN_TOKEN_LENGTH", "parse_dev_tokens"]

DEFAULT_CORS_ORIGINS = ("http://127.0.0.1:5173", "http://localhost:5173")
MIN_TOKEN_LENGTH = 16


def parse_dev_tokens(text: str) -> Tuple[Tuple[str, str], ...]:
    """``alice=tok1,bob=tok2`` -> (("alice", "tok1"), ("bob", "tok2")). A token that is short or shared is refused."""
    pairs = []
    for item in (part.strip() for part in text.split(",")):
        if not item:
            continue
        operator_id, separator, token = item.partition("=")
        operator_id, token = operator_id.strip(), token.strip()
        if not separator or not operator_id or not token:
            raise ConfigError("MINISAT_API_DEV_TOKENS must look like alice=<token>,sam=<token> (see 'minisat dev-tokens')")
        if len(token) < MIN_TOKEN_LENGTH:
            raise ConfigError(f"the token of {operator_id!r} is shorter than {MIN_TOKEN_LENGTH} characters: "
                              f"even a development token must not be guessable ('minisat dev-tokens' makes good ones)")
        pairs.append((operator_id, token))
    if len({o for o, _ in pairs}) != len(pairs):
        raise ConfigError("MINISAT_API_DEV_TOKENS names the same operator twice")
    if len({t for _, t in pairs}) != len(pairs):
        raise ConfigError("MINISAT_API_DEV_TOKENS gives the same token to two operators")
    return tuple(pairs)


def _flag(env: Mapping[str, str], name: str, default: bool) -> bool:
    value = env.get(name)
    if value is None or value == "":
        return default
    if value in ("1", "true", "yes"):
        return True
    if value in ("0", "false", "no"):
        return False
    raise ConfigError(f"{name} must be 1 or 0, got {value!r}")


@dataclass(frozen=True)
class ApiSettings:
    dev_tokens: Tuple[Tuple[str, str], ...] = ()               # (operator_id, token); DEV ONLY
    cors_origins: Tuple[str, ...] = DEFAULT_CORS_ORIGINS
    live_source: bool = True
    docs: bool = True

    @classmethod
    def from_env(cls, env: Optional[Mapping[str, str]] = None) -> "ApiSettings":
        import os
        env = os.environ if env is None else env
        origins = tuple(o.strip() for o in env.get("MINISAT_API_CORS_ORIGINS", "").split(",") if o.strip())
        if "*" in origins:
            raise ConfigError("MINISAT_API_CORS_ORIGINS must name the dashboard, not '*'")
        return cls(dev_tokens=parse_dev_tokens(env.get("MINISAT_API_DEV_TOKENS", "")),
                   cors_origins=origins or DEFAULT_CORS_ORIGINS,
                   live_source=_flag(env, "MINISAT_API_LIVE_SOURCE", True), docs=_flag(env, "MINISAT_API_DOCS", True))
