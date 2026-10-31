"""Alembic environment: always connects as the ``migrator`` role (the owner of the schema)."""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

from minisat.ontology.dbconfig import database_url

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)


def run_migrations_online() -> None:
    # tests pass the URL explicitly; normally it is built from the MINISAT_DB_* environment variables
    url = config.get_main_option("sqlalchemy.url") or database_url("migrator")
    section = {"sqlalchemy.url": url}
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=None)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    raise SystemExit("offline mode is not supported: the migration checks that the database roles exist")
run_migrations_online()
