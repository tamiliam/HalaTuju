-- Audit A1.9b (TD-549 / SEC-14): an explicit service_role policy on the 15 RLS tables that have none.
--
-- *** NOT APPLIED. *** This is the owner's live step (Supabase SQL editor). Run the three parts in
-- order: 1. the read-only pre-check, 2. the change (one transaction), 3. the read-back. Nothing in
-- this file has touched the live project.
--
-- WHY. These tables have row level security ON and no policy at all, so the Security Advisor flags
-- each one ("RLS enabled, no policy"). Nothing fails today: the API connects as `postgres`, which
-- OWNS every one of them and has BYPASSRLS, and RLS is not forced on any of them. service_role has
-- BYPASSRLS too, so these policies change no one's access today. They state the intent (the server
-- only, never a browser) and keep the server working if it ever moves to service_role.
--
-- WHAT IT DOES NOT DO. It grants nothing and adds no policy for `anon` or `authenticated`: a browser
-- key still reads and writes NOTHING in these tables (RLS on, no policy for them = deny all).
--
-- LIVE READ-BACK, 2026-11-07 (read-only, project pbrrlyoyyiftckqvzvvo): the pre-check below returned
-- exactly these 15 tables, all owned by postgres, relrowsecurity = true, relforcerowsecurity = false:
--   bank_accounts, bursary_agreements, contract_clauses, contract_payment_schedule_rows,
--   contract_templates, course_data_status, disbursements, django_cache, interview_messages,
--   org_request_attachments, org_requests, payment_run_items, payment_runs, usage_events,
--   whatsapp_messages
--   The app's role: postgres, rolbypassrls = true (production.py DB_USER defaults to 'postgres').
--
-- If the pre-check lists a DIFFERENT set, stop: a new table was added or one gained a policy since
-- this file was written. Add or remove lines in part 2 to match before running it.
--
-- ORDER with the SEC-11 file (2026-11-07-sec11-partner-organisations-read-policy.sql): independent;
-- either may go first. Suggested: this file, then SEC-11.


-- ── 1. PRE-CHECK (read-only) ────────────────────────────────────────────────────────────────────
-- Expect 15 rows, the list above, owner postgres, force_rls false.
SELECT c.relname AS table_name,
       pg_get_userbyid(c.relowner) AS owner,
       c.relrowsecurity AS rls,
       c.relforcerowsecurity AS force_rls
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public'
   AND c.relkind = 'r'
   AND c.relrowsecurity
   AND NOT EXISTS (SELECT 1 FROM pg_policies p
                    WHERE p.schemaname = 'public' AND p.tablename = c.relname)
 ORDER BY c.relname;

-- Expect postgres | true (the app bypasses RLS, so nothing below can lock it out).
SELECT rolname, rolbypassrls FROM pg_roles WHERE rolname IN ('postgres', 'service_role');


-- ── 2. THE CHANGE (one transaction) ─────────────────────────────────────────────────────────────
BEGIN;
SET LOCAL lock_timeout = '5s';

CREATE POLICY "service_role all" ON public.bank_accounts                  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.bursary_agreements             FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.contract_clauses               FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.contract_payment_schedule_rows FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.contract_templates             FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.course_data_status             FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.disbursements                  FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.django_cache                   FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.interview_messages             FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.org_request_attachments        FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.org_requests                   FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.payment_run_items              FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.payment_runs                   FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.usage_events                   FOR ALL TO service_role USING (true) WITH CHECK (true);
CREATE POLICY "service_role all" ON public.whatsapp_messages              FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMIT;
-- Any error above (a lock wait over 5 s, a policy of that name already there) aborts the whole
-- transaction and nothing changes; the COMMIT then reports ROLLBACK. Fix and run part 2 again.


-- ── 3. READ-BACK ────────────────────────────────────────────────────────────────────────────────
-- Expect 15 rows: each table, "service_role all", roles {service_role}, cmd ALL, qual true, with_check true.
SELECT tablename, policyname, roles, cmd, qual, with_check
  FROM pg_policies
 WHERE schemaname = 'public' AND policyname = 'service_role all'
 ORDER BY tablename;

-- Expect 0 rows: no RLS table is left without a policy.
SELECT c.relname
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relkind = 'r' AND c.relrowsecurity
   AND NOT EXISTS (SELECT 1 FROM pg_policies p
                    WHERE p.schemaname = 'public' AND p.tablename = c.relname);

-- Then: Security Advisor no longer lists the 15 under "RLS enabled, no policy"; the app works as
-- before (sign in to the admin console and open one application as a smoke test).


-- ── ROLLBACK (only if needed) ───────────────────────────────────────────────────────────────────
-- BEGIN;
-- SET LOCAL lock_timeout = '5s';
-- DROP POLICY IF EXISTS "service_role all" ON public.bank_accounts;
-- DROP POLICY IF EXISTS "service_role all" ON public.bursary_agreements;
-- DROP POLICY IF EXISTS "service_role all" ON public.contract_clauses;
-- DROP POLICY IF EXISTS "service_role all" ON public.contract_payment_schedule_rows;
-- DROP POLICY IF EXISTS "service_role all" ON public.contract_templates;
-- DROP POLICY IF EXISTS "service_role all" ON public.course_data_status;
-- DROP POLICY IF EXISTS "service_role all" ON public.disbursements;
-- DROP POLICY IF EXISTS "service_role all" ON public.django_cache;
-- DROP POLICY IF EXISTS "service_role all" ON public.interview_messages;
-- DROP POLICY IF EXISTS "service_role all" ON public.org_request_attachments;
-- DROP POLICY IF EXISTS "service_role all" ON public.org_requests;
-- DROP POLICY IF EXISTS "service_role all" ON public.payment_run_items;
-- DROP POLICY IF EXISTS "service_role all" ON public.payment_runs;
-- DROP POLICY IF EXISTS "service_role all" ON public.usage_events;
-- DROP POLICY IF EXISTS "service_role all" ON public.whatsapp_messages;
-- COMMIT;
