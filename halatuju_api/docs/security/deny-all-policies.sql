-- Explicit backend-only RLS policies for the "deny-all" tables  (security hardening item E)
-- ============================================================================================
-- These tables already have RLS ENABLED with NO policy — which is the *safe* deny-all state
-- (anon/authenticated get nothing; the app reaches them only via Django on the privileged
-- service/postgres connection, which bypasses RLS). This script makes that intent EXPLICIT by
-- adding a service_role policy, so:
--   (a) it matches the project standard ("RLS enabled + policies", per incident-001), and
--   (b) Supabase's `rls_enabled_no_policy` advisor INFO clears.
--
-- BEHAVIOUR-NEUTRAL: service_role already bypasses RLS, so this changes nothing for the
-- backend; anon/authenticated remain denied (still no policy applies to them).
--
-- HOW TO APPLY: run via the Supabase MCP against PROD (apply_migration / execute_sql) —
-- this project manages RLS by hand via MCP, NOT via Django migrations (tests run on SQLite,
-- which has no RLS, so a RunSQL migration would break the suite). Idempotent / re-runnable.
--
-- AFTER APPLYING: re-run get_advisors(type="security") — the rls_enabled_no_policy INFOs for
-- these tables should be gone. (Verification query at the bottom.)

DO $$
DECLARE
  t text;
  tables text[] := ARRAY[
    'applicant_documents', 'assignment_events', 'consents', 'django_migrations',
    'funding_needs', 'graduation_messages', 'interview_sessions', 'onboarding_responses',
    'referees', 'resolution_items', 'reviewer_profiles', 'scholarship_applications',
    'scholarship_cohorts', 'semester_results', 'sponsor_donations', 'sponsor_profiles',
    'sponsor_referrals', 'sponsors', 'sponsorships'
    -- (django_migrations is Django-internal; the policy is harmless and only clears the advisor.)
  ];
BEGIN
  FOREACH t IN ARRAY tables LOOP
    EXECUTE format('DROP POLICY IF EXISTS %I ON public.%I', 'Backend service role only', t);
    EXECUTE format(
      'CREATE POLICY %I ON public.%I AS PERMISSIVE FOR ALL TO service_role '
      'USING (true) WITH CHECK (true)',
      'Backend service role only', t
    );
  END LOOP;
END $$;

-- Verification — every listed table should now report policies = 1 (or more):
-- SELECT c.relname, (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid) AS policies
-- FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
-- WHERE n.nspname = 'public'
--   AND c.relname = ANY(ARRAY[
--     'applicant_documents','assignment_events','consents','django_migrations','funding_needs',
--     'graduation_messages','interview_sessions','onboarding_responses','referees',
--     'resolution_items','reviewer_profiles','scholarship_applications','scholarship_cohorts',
--     'semester_results','sponsor_donations','sponsor_profiles','sponsor_referrals','sponsors',
--     'sponsorships'])
-- ORDER BY c.relname;
