-- Audit A1.9b (TD-520 / SEC-11): remove the "Allow public read" policy on partner_organisations.
--
-- *** NOT APPLIED. *** This is the owner's live step (Supabase SQL editor). Run the three parts in
-- order: 1. the read-only pre-check, 2. the change (one transaction), 3. the read-back. Nothing in
-- this file has touched the live project.
--
-- WHY. The policy "Allow public read" (PERMISSIVE, roles {public}, FOR SELECT, USING true) lets ANY
-- holder of the browser (anon) key read every row through Supabase's REST API, and the table holds
-- each organisation's contact_person, contact_email and phone (Security Advisor 0012). Nothing needs
-- it: the web never reads this table through Supabase (no halatuju-web reference); only the Django
-- model `courses.PartnerOrganisation` (db_table 'partner_organisations') reads it, as `postgres`.
--
-- WHAT IT DOES. Drops "Allow public read". RLS stays ON, so anon and authenticated then read NOTHING
-- (no policy for them = deny all). Adds the same explicit service_role policy as the SEC-14 file, so
-- the table does not become one more "RLS enabled, no policy" advisor finding. It grants nothing and
-- adds nothing for anon or authenticated. It does NOT revoke the table grants (anon and authenticated
-- hold full grants, as on every public table Supabase creates); RLS is what stops them.
--
-- THE APP KEEPS WORKING. The API connects as `postgres`, which owns the table and has BYPASSRLS, and
-- RLS is not forced on it, so no policy here can affect the API (organisation themes, referral links,
-- the partner admin pages all read through Django).
--
-- LIVE READ-BACK, 2026-11-07 (read-only, project pbrrlyoyyiftckqvzvvo):
--   partner_organisations: owner postgres, relrowsecurity = true, relforcerowsecurity = false, 16 rows,
--   no dependent views, no database function mentions it.
--   Policies: exactly one, "Allow public read", PERMISSIVE, roles {public}, cmd SELECT, qual true.
--   Grants: anon, authenticated, postgres, service_role all hold full table privileges.
--   Columns include contact_person, contact_email, phone, email_from, email_reply_to, email_support.
--
-- If the pre-check shows a different policy set, stop and re-read before running part 2.
--
-- ORDER with the SEC-14 file (2026-11-07-sec14-service-role-policies.sql): independent; either may go
-- first. Suggested: SEC-14, then this file.


-- ── 1. PRE-CHECK (read-only) ────────────────────────────────────────────────────────────────────
-- Expect one row: "Allow public read" | PERMISSIVE | {public} | SELECT | true
SELECT policyname, permissive, roles, cmd, qual, with_check
  FROM pg_policies
 WHERE schemaname = 'public' AND tablename = 'partner_organisations';

-- Expect: postgres | true | false (owner, RLS on, not forced).
SELECT pg_get_userbyid(c.relowner) AS owner, c.relrowsecurity AS rls, c.relforcerowsecurity AS force_rls
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
 WHERE n.nspname = 'public' AND c.relname = 'partner_organisations';

-- Expect postgres | true (the app bypasses RLS).
SELECT rolname, rolbypassrls FROM pg_roles WHERE rolname IN ('postgres', 'service_role');


-- ── 2. THE CHANGE (one transaction) ─────────────────────────────────────────────────────────────
BEGIN;
SET LOCAL lock_timeout = '5s';

DROP POLICY "Allow public read" ON public.partner_organisations;
CREATE POLICY "service_role all" ON public.partner_organisations
  FOR ALL TO service_role USING (true) WITH CHECK (true);

COMMIT;
-- Any error above (a lock wait over 5 s, the policy already gone) aborts the whole transaction and
-- nothing changes; the COMMIT then reports ROLLBACK. Re-run the pre-check before trying again.


-- ── 3. READ-BACK ────────────────────────────────────────────────────────────────────────────────
-- Expect one row: "service_role all" | PERMISSIVE | {service_role} | ALL | true | true
SELECT policyname, permissive, roles, cmd, qual, with_check
  FROM pg_policies
 WHERE schemaname = 'public' AND tablename = 'partner_organisations';

-- Optional, from a machine with the anon key (expect [] , HTTP 200):
--   curl -s "https://pbrrlyoyyiftckqvzvvo.supabase.co/rest/v1/partner_organisations?select=code&limit=1" \
--     -H "apikey: <anon key>"
-- Then: Security Advisor no longer lists partner_organisations under 0012; the site's referral links
-- and an organisation's admin pages work as before (smoke test).


-- ── ROLLBACK (only if needed: puts the public read back exactly as it was) ──────────────────────
-- BEGIN;
-- SET LOCAL lock_timeout = '5s';
-- DROP POLICY IF EXISTS "service_role all" ON public.partner_organisations;
-- CREATE POLICY "Allow public read" ON public.partner_organisations
--   AS PERMISSIVE FOR SELECT TO public USING (true);
-- COMMIT;
