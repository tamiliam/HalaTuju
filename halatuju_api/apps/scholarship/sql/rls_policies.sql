-- Row Level Security for B40 Assistance Programme tables (Sprint 1)
--
-- Apply this against Supabase AFTER `manage.py migrate` creates the tables and
-- BEFORE the first deploy. Then run the Supabase Security Advisor and confirm
-- 0 errors (see halatuju_api/CLAUDE.md pre-deploy checklist + docs/incident-001).
--
-- Access model: the Django API connects as the table-owner (service) role,
-- which BYPASSES RLS. The frontend never talks to these tables directly via
-- PostgREST. Enabling RLS with no permissive policy therefore denies all
-- direct anon/authenticated access (defense in depth) while the Django API
-- continues to work normally. Application rows hold sensitive financial/family
-- data, so deny-by-default is the correct posture.

ALTER TABLE scholarship_cohorts ENABLE ROW LEVEL SECURITY;
ALTER TABLE scholarship_applications ENABLE ROW LEVEL SECURITY;
ALTER TABLE funding_needs ENABLE ROW LEVEL SECURITY;
ALTER TABLE applicant_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE referees ENABLE ROW LEVEL SECURITY;
ALTER TABLE consents ENABLE ROW LEVEL SECURITY;

-- No GRANTs / policies for anon or authenticated roles: direct PostgREST access
-- is intentionally denied. If a future sprint needs direct client reads (e.g. a
-- public, non-sensitive cohort listing), add a narrowly-scoped SELECT policy
-- here for that table only.
