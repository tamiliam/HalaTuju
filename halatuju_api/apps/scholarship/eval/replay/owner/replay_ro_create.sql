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
--
-- TWO PLACEHOLDERS to replace before running: the password, and the expiry date
-- (REPLACE-WITH-RUN-DATE-PLUS-7-DAYS: the planned run date plus 7 days, written like 2026-11-27).

-- PRE-CHECK (run first, paste the answer back): the Postgres version, and whether `postgres` itself has
-- BYPASSRLS. A role can only hand out BYPASSRLS if it has it. If rolbypassrls is false here (or the
-- CREATE ROLE below is refused), BYPASSRLS cannot be granted: use the per-table read policy fallback
-- at the end of this file instead.
SELECT version() AS postgres_version, rolsuper, rolbypassrls
  FROM pg_roles WHERE rolname = 'postgres';

BEGIN;

CREATE ROLE replay_ro WITH LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION BYPASSRLS
    CONNECTION LIMIT 6
    VALID UNTIL 'REPLACE-WITH-RUN-DATE-PLUS-7-DAYS'
    PASSWORD 'REPLACE-WITH-A-LONG-RANDOM-PASSWORD';

GRANT USAGE ON SCHEMA public TO replay_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO replay_ro;

-- A runaway statement stops on its own. (A per-statement limit, not a read-only switch.)
ALTER ROLE replay_ro SET statement_timeout = '10min';

COMMIT;

-- FALLBACK (the per-table read policy fallback), only if BYPASSRLS cannot be granted: run the CREATE ROLE
-- without BYPASSRLS, the two
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
-- fallback), rolconnlimit 6, rolvaliduntil the expiry date, and ONE privilege row: SELECT.
SELECT rolname, rolsuper, rolcreaterole, rolcreatedb, rolbypassrls, rolconnlimit, rolvaliduntil
  FROM pg_roles WHERE rolname = 'replay_ro';
SELECT privilege_type, count(*) AS tables
  FROM information_schema.role_table_grants WHERE grantee = 'replay_ro' GROUP BY privilege_type;
-- Expect false: replay_ro cannot create objects in the public schema.
SELECT has_schema_privilege('replay_ro', 'public', 'CREATE') AS can_create_in_public;
-- SECURITY DEFINER functions replay_ro can execute (they run with their OWNER's rights). Expect the list
-- to be read by the lead before the run; the harness's statement filter refuses any function outside its
-- small allow-list, but this shows what the database itself would allow.
SELECT n.nspname AS schema_name, p.proname AS function_name, pg_get_userbyid(p.proowner) AS owner
  FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
 WHERE p.prosecdef AND has_function_privilege('replay_ro', p.oid, 'EXECUTE')
   AND n.nspname NOT IN ('pg_catalog', 'information_schema')
 ORDER BY 1, 2;
