-- A5 replay, owner step 1 (design 3.4 layer 1): the read-only role `replay_ro`.
-- WRITTEN BY THE LEAD, RUN ONLY BY THE OWNER, on a fresh yes, in the Supabase SQL editor (as `postgres`).
-- Replace the password placeholder with a long random password; do not save the edited file anywhere.
--
-- What the role can do: log in, see the `public` schema, SELECT its tables. Nothing else is granted.
-- What it is NOT: no session-level read-only setting (the harness makes each TRANSACTION read only and
-- proves it); the role itself simply holds no write grant, so the database refuses any write.
--
-- BYPASSRLS: every public table has row-level security with service_role policies only, so a plain
-- SELECT-only role would read ZERO rows and the replay would compare nothing. BYPASSRLS lets it read
-- rows; it does not give any write. If Supabase refuses BYPASSRLS, use the FALLBACK block below instead.

BEGIN;

CREATE ROLE replay_ro WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION BYPASSRLS
    CONNECTION LIMIT 6
    PASSWORD 'REPLACE-WITH-A-LONG-RANDOM-PASSWORD';

GRANT USAGE ON SCHEMA public TO replay_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replay_ro;

-- A runaway statement stops on its own. (A per-statement limit, not a read-only switch.)
ALTER ROLE replay_ro SET statement_timeout = '10min';

COMMIT;

-- FALLBACK, only if CREATE ROLE ... BYPASSRLS was refused: run the CREATE ROLE without BYPASSRLS, the two
-- GRANTs and the ALTER above, then this block (a SELECT-only policy for replay_ro on every RLS table):
--
-- DO $$
-- DECLARE t record;
-- BEGIN
--   FOR t IN SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND rowsecurity LOOP
--     EXECUTE format('CREATE POLICY replay_ro_read ON public.%I FOR SELECT TO replay_ro USING (true)', t.tablename);
--   END LOOP;
-- END $$;

-- CHECK (paste the answers back to the lead): expect rolsuper false, rolbypassrls true (false on the
-- fallback), rolconnlimit 6, and ONE privilege row: SELECT.
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolconnlimit
  FROM pg_roles WHERE rolname = 'replay_ro';
SELECT privilege_type, count(*) AS tables
  FROM information_schema.role_table_grants WHERE grantee = 'replay_ro' GROUP BY privilege_type;
