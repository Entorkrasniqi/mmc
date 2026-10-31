-- The four database roles of protocols/action-runner-and-audit.md. Idempotent: safe to run again, which also
-- applies a changed password. Used by the Docker init script (db/init/01-roles.sh) and by the database tests.
--
--   psql -v ON_ERROR_STOP=1 -v migrator_pw=... -v runner_pw=... -v reader_pw=... -v ingest_pw=... -f roles.sql
--
-- Only the roles are created here. What each role may do is granted by the migrations (they own the tables).
-- The roles are deliberately plain: no superuser, no createdb, no createrole, no replication.

SELECT format('CREATE ROLE %I LOGIN', r)
  FROM (VALUES ('migrator'), ('app_runner'), ('app_reader'), ('ingest')) AS roles(r)
 WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = r) \gexec

SELECT format('ALTER ROLE %I NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION PASSWORD %L', r, pw)
  FROM (VALUES ('migrator', :'migrator_pw'), ('app_runner', :'runner_pw'),
               ('app_reader', :'reader_pw'), ('ingest', :'ingest_pw')) AS roles(r, pw) \gexec
