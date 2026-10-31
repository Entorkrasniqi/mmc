import pytest

from minisat.ontology.dbconfig import ConfigError, ROLES, database_url

ENV = {
    "MINISAT_DB_PASSWORD_MIGRATOR": "m", "MINISAT_DB_PASSWORD_RUNNER": "r",
    "MINISAT_DB_PASSWORD_READER": "d", "MINISAT_DB_PASSWORD_INGEST": "i",
}


def test_each_role_connects_as_its_own_database_user():
    assert database_url("migrator", ENV) == "postgresql+psycopg://migrator:m@localhost:5432/minisat"
    assert database_url("runner", ENV) == "postgresql+psycopg://app_runner:r@localhost:5432/minisat"
    assert database_url("reader", ENV) == "postgresql+psycopg://app_reader:d@localhost:5432/minisat"
    assert database_url("ingest", ENV) == "postgresql+psycopg://ingest:i@localhost:5432/minisat"
    assert set(ROLES) == {"migrator", "runner", "reader", "ingest"}


def test_host_port_and_name_can_be_overridden():
    env = dict(ENV, MINISAT_DB_HOST="db.internal", MINISAT_DB_PORT="6543", MINISAT_DB_NAME="other")
    assert database_url("reader", env) == "postgresql+psycopg://app_reader:d@db.internal:6543/other"


def test_passwords_with_special_characters_are_url_encoded():
    env = dict(ENV, MINISAT_DB_PASSWORD_RUNNER="p@ss/w:rd %1")
    assert database_url("runner", env) == "postgresql+psycopg://app_runner:p%40ss%2Fw%3Ard%20%251@localhost:5432/minisat"


@pytest.mark.parametrize("missing", sorted(ENV))
def test_a_missing_password_is_an_error_that_names_the_variable(missing):
    env = {k: v for k, v in ENV.items() if k != missing}
    role = missing.rsplit("_", 1)[1].lower()
    with pytest.raises(ConfigError, match=missing):
        database_url(role, env)


def test_an_empty_password_is_refused():
    with pytest.raises(ConfigError):
        database_url("runner", dict(ENV, MINISAT_DB_PASSWORD_RUNNER=""))


def test_unknown_role_and_bad_port_are_refused():
    with pytest.raises(ConfigError, match="unknown database role"):
        database_url("postgres", ENV)
    with pytest.raises(ConfigError, match="MINISAT_DB_PORT"):
        database_url("reader", dict(ENV, MINISAT_DB_PORT="five"))
