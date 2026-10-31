-- Per-database setup, run once as a superuser while connected to the application database (after db/roles.sql).
-- Used by the Docker init script (db/init/01-roles.sh) and by the database tests. Idempotent.
--
--   psql -v ON_ERROR_STOP=1 -d <database> -f database.sql
--
-- * the migrator owns the database, so it (and only it) can create the schema;
-- * only the four application roles may connect at all;
-- * nobody but the migrator may create objects in the "public" schema (PostgreSQL before 15 lets every role).

SELECT format('ALTER DATABASE %I OWNER TO migrator', current_database()) \gexec
SELECT format('REVOKE ALL ON DATABASE %I FROM PUBLIC', current_database()) \gexec
SELECT format('GRANT CONNECT ON DATABASE %I TO migrator, app_runner, app_reader, ingest', current_database()) \gexec

REVOKE CREATE ON SCHEMA public FROM PUBLIC;
GRANT CREATE ON SCHEMA public TO migrator;      -- alembic keeps its version table there
