-- A5 replay, owner step 5 (design section 6): remove `replay_ro` once the replay is done.
-- WRITTEN BY THE LEAD, RUN ONLY BY THE OWNER, in the Supabase SQL editor (as `postgres`), after the job,
-- its secret and its service account are deleted (see the owner-steps doc).

-- 1. No replay session may still be open (expect zero rows; if not, wait for the job to finish).
SELECT pid, state, backend_start FROM pg_stat_activity WHERE usename = 'replay_ro';

BEGIN;

-- 2. FALLBACK only (if the create used the per-table policies instead of BYPASSRLS):
-- DO $$
-- DECLARE t record;
-- BEGIN
--   FOR t IN SELECT tablename FROM pg_policies WHERE schemaname = 'public' AND policyname = 'replay_ro_read' LOOP
--     EXECUTE format('DROP POLICY replay_ro_read ON public.%I', t.tablename);
--   END LOOP;
-- END $$;

-- 3. Take back what was granted, then remove the role.
REVOKE SELECT ON ALL TABLES IN SCHEMA public FROM replay_ro;
REVOKE USAGE ON SCHEMA public FROM replay_ro;
DROP ROLE replay_ro;

COMMIT;

-- CHECK: expect zero rows from both.
SELECT rolname FROM pg_roles WHERE rolname = 'replay_ro';
SELECT policyname FROM pg_policies WHERE policyname = 'replay_ro_read';
