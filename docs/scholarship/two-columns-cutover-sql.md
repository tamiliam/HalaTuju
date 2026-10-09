# Two referral columns (sources and referral partners, Sprint A) — prod cutover SQL (migrate-first)

**Migration:** `courses/0078_two_referral_columns` (courses ledger 0077 → 0078; depends on
`scholarship/0172`, already applied). Schema + data, ONE ledger row.
**Status:** written 2026-10-09 by the sprint; NOT applied. The lead applies it to production
(Supabase `pbrrlyoyyiftckqvzvvo`) via the Supabase MCP BEFORE the push, per the migrate-first
convention (deploys never run `migrate`), after re-running the pre-checks and telling the owner of
any count that differs from the expected one BEFORE applying (lessons.md 2026-10-09).

What it does (owner's model and rulings, 2026-10-09; decisions.md "The student record has two
independent columns: source and referral partner"):
1. `partner_organisations.is_referral_partner` — `boolean DEFAULT false NOT NULL`. The DEFAULT is in
   the DATABASE (`db_default`), so the image still serving — whose Sources POST does not name the
   column — keeps inserting. Marked from the `partner`-role logins: `cumig` only.
2. `api_student_profiles.source_id` — nullable FK to `partner_organisations` (the SOURCE column).
3. SOURCE backfill: each profile's latest application (highest id) → the code in
   `intake_snapshot -> 'profile' ->> 'referral_source'`, when that code is a source row (not a tenant,
   not `halatuju` / `social` / `other`); otherwise left NULL.
4. REFERRAL PARTNER (`referred_by_org_id`): links to a referral partner are KEPT (incl. the 13 CUMIG
   pickers — owner: "Filled", both columns CUMIG); links to any other row are COPIED to a dated
   backup table and then CLEARED.

The DDL below was rendered OFFLINE from the migration with Django's postgresql schema editor (no
connection; `sqlmigrate` renders SQLite on a dev box), so names are exactly Django's. Django emits the
`CREATE INDEX` at the END (after the Python steps); here it is moved up, BEFORE any `UPDATE`, so the
0163 rule (a deferred FK's pending trigger events block a later `CREATE INDEX`) cannot bite. The new
backup table follows the house RLS convention: ENABLE + one `service_role` policy (the
`rls_auto_enable` trigger switches RLS on but adds no policy).

## Pre-checks (read-only — run first, write the answers into the cutover note)

```sql
BEGIN READ ONLY;

-- 1. Ledgers: courses ends at 0077, scholarship at 0172, no gap.
SELECT app, name FROM django_migrations WHERE app IN ('courses', 'scholarship')
 ORDER BY app, name DESC;

-- 2. Neither new column exists yet.                                  expect: 0 rows
SELECT table_name, column_name FROM information_schema.columns
 WHERE (table_name, column_name) IN (('partner_organisations', 'is_referral_partner'),
                                    ('api_student_profiles', 'source_id'));
SELECT to_regclass('public.referral_link_backup_20261009');          -- expect NULL

-- 3. Who will be marked a referral partner.                          expect: cumig | 2
SELECT o.code, count(*) AS partner_logins,
       EXISTS (SELECT 1 FROM scholarship_programmes tp WHERE tp.organisation_id = o.id AND tp.is_active)
    OR EXISTS (SELECT 1 FROM partner_admins t WHERE t.owning_organisation_id = o.id
                AND t.role = 'org_admin' AND t.is_active) AS is_tenant         -- expect false
  FROM partner_admins a JOIN partner_organisations o ON o.id = a.org_id
 WHERE a.role = 'partner'
 GROUP BY o.id, o.code ORDER BY o.code;

-- 4. referred_by_org today, by row.        expect: cumig 254 (241 + 13); every other row = N, cleared
SELECT o.code, count(*) AS linked,
       count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM scholarship_applications a
                                           WHERE a.profile_id = p.supabase_user_id)) AS no_application
  FROM api_student_profiles p JOIN partner_organisations o ON o.id = p.referred_by_org_id
 GROUP BY o.code ORDER BY o.code;
-- expect cumig: linked 254, no_application 241.

-- 5. The SOURCE each profile will get (latest application's answer, source rows only).
WITH latest AS (
  SELECT DISTINCT ON (a.profile_id) a.profile_id,
         a.intake_snapshot -> 'profile' ->> 'referral_source' AS code
    FROM scholarship_applications a
   WHERE a.profile_id IS NOT NULL
   ORDER BY a.profile_id, a.id DESC
), src AS (
  SELECT s.id, s.code FROM partner_organisations s
   WHERE s.code NOT IN ('halatuju', 'social', 'other')
     AND NOT EXISTS (SELECT 1 FROM scholarship_programmes tp
                      WHERE tp.organisation_id = s.id AND tp.is_active)
     AND NOT EXISTS (SELECT 1 FROM partner_admins t
                      WHERE t.owning_organisation_id = s.id AND t.role = 'org_admin' AND t.is_active)
)
SELECT coalesce(src.code, '(none: ' || coalesce(l.code, 'null') || ')') AS source, count(*)
  FROM latest l LEFT JOIN src ON src.code = l.code
 GROUP BY 1 ORDER BY 1;
-- expect: cumig >= 13 (the 13 pickers); every named source row; the "(none: …)" lines stay NULL.
-- S = the sum of the rows that name a source (no "(none" prefix) — the UPDATE count in the cutover.

-- 6. The 13 "Filled" profiles: linked to cumig AND latest answer cumig.          expect: 13
WITH latest AS (
  SELECT DISTINCT ON (a.profile_id) a.profile_id,
         a.intake_snapshot -> 'profile' ->> 'referral_source' AS code
    FROM scholarship_applications a WHERE a.profile_id IS NOT NULL
   ORDER BY a.profile_id, a.id DESC)
SELECT count(*) FROM latest l
  JOIN api_student_profiles p ON p.supabase_user_id = l.profile_id
  JOIN partner_organisations o ON o.id = p.referred_by_org_id AND o.code = 'cumig'
 WHERE l.code = 'cumig';

-- 7. N = links that will be cleared (and backed up): not to a partner-login row.
SELECT count(*) FROM api_student_profiles p
 WHERE p.referred_by_org_id IS NOT NULL
   AND p.referred_by_org_id NOT IN (SELECT org_id FROM partner_admins
                                     WHERE role = 'partner' AND org_id IS NOT NULL);

-- 8. Witness/cockpit impact (informational): profiles whose "referring organisation" changes —
--    before = referred_by_org; after = the new source, else the kept partner link.
WITH latest AS (
  SELECT DISTINCT ON (a.profile_id) a.profile_id,
         a.intake_snapshot -> 'profile' ->> 'referral_source' AS code
    FROM scholarship_applications a WHERE a.profile_id IS NOT NULL
   ORDER BY a.profile_id, a.id DESC
), src AS (
  SELECT s.id, s.code FROM partner_organisations s
   WHERE s.code NOT IN ('halatuju', 'social', 'other')
     AND NOT EXISTS (SELECT 1 FROM scholarship_programmes tp WHERE tp.organisation_id = s.id AND tp.is_active)
     AND NOT EXISTS (SELECT 1 FROM partner_admins t WHERE t.owning_organisation_id = s.id
                      AND t.role = 'org_admin' AND t.is_active)
), partners AS (SELECT DISTINCT org_id AS id FROM partner_admins WHERE role = 'partner' AND org_id IS NOT NULL)
SELECT count(*) AS changes,
       count(*) FILTER (WHERE EXISTS (SELECT 1 FROM scholarship_applications a
                                       WHERE a.profile_id = p.supabase_user_id
                                         AND a.status IN ('recommended', 'awarded', 'active', 'maintenance')))
         AS in_funded_or_pool
  FROM api_student_profiles p
  LEFT JOIN latest l ON l.profile_id = p.supabase_user_id
  LEFT JOIN src ON src.code = l.code
 WHERE p.referred_by_org_id IS DISTINCT FROM
       coalesce(src.id, CASE WHEN p.referred_by_org_id IN (SELECT id FROM partners)
                             THEN p.referred_by_org_id END);
-- These are the stale links (an earlier answer, a later fixed choice — TD-380) and old course-selector
-- links to a source or a tenant. Signing is OFF (BURSARY_AGREEMENT_ENABLED), so no witness email moves
-- today; the cockpit's "sourceless" witness dropdown appears for them. Report the figure to the owner.

-- 9. ⚠ ASSERTED — MUST RETURN 0. No OPEN gift's apply form offers `cumig` at the cutover. "Open" and
--    "offers" are the intake's own definitions (`views.py` `_open_round_choices`: an intake round
--    `is_active AND is_open` under an `is_active` programme; `gift_sources.offered_sources`: a link
--    whose source is `show_in_apply AND is_active` and not a tenant). If this is not 0, a CUMIG pick
--    submitted on the OLD image between the cutover and the deploy would be linked to CUMIG and stay
--    on CUMIG's list (see "Deploy window") — STOP and ask the owner before applying.
SELECT count(*) AS open_gifts_offering_cumig
  FROM programme_referral_sources l
  JOIN partner_organisations s ON s.id = l.source_id AND s.code = 'cumig'
                              AND s.show_in_apply AND s.is_active
  JOIN scholarship_programmes p ON p.id = l.programme_id AND p.is_active
 WHERE EXISTS (SELECT 1 FROM scholarship_cohorts c
                WHERE c.programme_id = p.id AND c.is_active AND c.is_open);
-- expect 0 (2026-10-09: Sabah is open and offers ewrf, pptm, smc; the flagship offers all seven
-- incl. cumig but is closed).

-- 10. Chip drift: applicants whose chip differs from their latest application's answer.   expect: 1
WITH latest AS (
  SELECT DISTINCT ON (a.profile_id) a.profile_id,
         a.intake_snapshot -> 'profile' ->> 'referral_source' AS code
    FROM scholarship_applications a WHERE a.profile_id IS NOT NULL
   ORDER BY a.profile_id, a.id DESC)
SELECT count(*) FROM latest l JOIN api_student_profiles p ON p.supabase_user_id = l.profile_id
 WHERE coalesce(p.referral_source, '') IS DISTINCT FROM coalesce(l.code, '');
-- The 1 row is `pushparani` → `other`, the deliberate courses 0077 move (2026-10-09). NO chip repair
-- is needed: the bursary readers of the chip agree with the per-application answers.

COMMIT;
```

**Lead's production reading, 2026-10-09 (read-only, before applying):** pre-checks 1–8 matched —
partner logins only on `cumig` (2); `referred_by_org`: cumig 254 (241 with no application), smc 62,
pptm 16, ewrf 9, mhm 6, hyo 1, hss 1 → **N = 95** to clear, all applicants; latest-answer sources
cumig 13, smc 62, pptm 16, ewrf 9, mhm 6, hyo 1, hss 1 → **S = 108**; filled 13; witness/cockpit
changes 0. Chip drift 1 (the 0077 move, above). Pre-check 9 must still read 0 at the cutover.

⚠ The backfill takes a SOURCE from any non-tenant, non-fixed row, switched off or not, while the live
writer (`profile_sync`) only ever names `gift_sources.active_sources()` — the same result today,
because every latest answer names a source that was offered when it was given.

## The cutover — ONE transaction

```sql
BEGIN;

-- Schema (rendered offline; the index moved up, before any UPDATE).
ALTER TABLE "partner_organisations" ADD COLUMN "is_referral_partner" boolean DEFAULT false NOT NULL;
ALTER TABLE "api_student_profiles" ADD COLUMN "source_id" bigint NULL CONSTRAINT "api_student_profiles_source_id_015accbd_fk_partner_o" REFERENCES "partner_organisations"("id") DEFERRABLE INITIALLY DEFERRED; SET CONSTRAINTS "api_student_profiles_source_id_015accbd_fk_partner_o" IMMEDIATE;
CREATE INDEX "api_student_profiles_source_id_015accbd" ON "api_student_profiles" ("source_id");

-- 1. Mark the referral partners: every row carrying a partner-role login.   expect: UPDATE 1
UPDATE partner_organisations SET is_referral_partner = true
 WHERE id IN (SELECT org_id FROM partner_admins WHERE role = 'partner' AND org_id IS NOT NULL);

-- Refuse to go on unless exactly `cumig` is marked and it is not a tenant, and (pre-check 9) no
-- OPEN gift offers `cumig`.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM programme_referral_sources l
               JOIN partner_organisations s ON s.id = l.source_id AND s.code = 'cumig'
                                           AND s.show_in_apply AND s.is_active
               JOIN scholarship_programmes p ON p.id = l.programme_id AND p.is_active
              WHERE EXISTS (SELECT 1 FROM scholarship_cohorts c
                             WHERE c.programme_id = p.id AND c.is_active AND c.is_open)) THEN
    RAISE EXCEPTION 'an open gift offers cumig: stop and ask the owner (deploy window)';
  END IF;
  IF (SELECT string_agg(code, ',' ORDER BY code) FROM partner_organisations
       WHERE is_referral_partner) IS DISTINCT FROM 'cumig' THEN
    RAISE EXCEPTION 'expected exactly cumig to be marked a referral partner';
  END IF;
  IF EXISTS (SELECT 1 FROM partner_organisations o WHERE o.is_referral_partner AND (
       EXISTS (SELECT 1 FROM scholarship_programmes tp WHERE tp.organisation_id = o.id AND tp.is_active)
    OR EXISTS (SELECT 1 FROM partner_admins t WHERE t.owning_organisation_id = o.id
                AND t.role = 'org_admin' AND t.is_active))) THEN
    RAISE EXCEPTION 'a tenant would be marked a referral partner';
  END IF;
END $$;

-- 2. BACKUP every link about to be cleared (restorable), BEFORE clearing.  expect: SELECT N
CREATE TABLE public.referral_link_backup_20261009 AS
SELECT p.supabase_user_id, p.referred_by_org_id, now() AS backed_up_at
  FROM api_student_profiles p
 WHERE p.referred_by_org_id IS NOT NULL
   AND p.referred_by_org_id NOT IN (SELECT id FROM partner_organisations WHERE is_referral_partner);
ALTER TABLE public.referral_link_backup_20261009 ADD PRIMARY KEY (supabase_user_id);
ALTER TABLE public.referral_link_backup_20261009 ENABLE ROW LEVEL SECURITY;
CREATE POLICY referral_link_backup_20261009_service_role ON public.referral_link_backup_20261009
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- 3. The SOURCE column from each profile's latest application.               expect: UPDATE S
WITH latest AS (
  SELECT DISTINCT ON (a.profile_id) a.profile_id,
         a.intake_snapshot -> 'profile' ->> 'referral_source' AS code
    FROM scholarship_applications a
   WHERE a.profile_id IS NOT NULL
   ORDER BY a.profile_id, a.id DESC
), src AS (
  SELECT s.id, s.code FROM partner_organisations s
   WHERE s.code NOT IN ('halatuju', 'social', 'other')
     AND NOT EXISTS (SELECT 1 FROM scholarship_programmes tp
                      WHERE tp.organisation_id = s.id AND tp.is_active)
     AND NOT EXISTS (SELECT 1 FROM partner_admins t
                      WHERE t.owning_organisation_id = s.id AND t.role = 'org_admin' AND t.is_active)
)
UPDATE api_student_profiles p SET source_id = src.id
  FROM latest l JOIN src ON src.code = l.code
 WHERE p.supabase_user_id = l.profile_id;

-- 4. CLEAR every link to a row that is not a referral partner.               expect: UPDATE N
UPDATE api_student_profiles SET referred_by_org_id = NULL
 WHERE referred_by_org_id IS NOT NULL
   AND referred_by_org_id NOT IN (SELECT id FROM partner_organisations WHERE is_referral_partner);

-- Any count different from the pre-check: ROLLBACK and look before going on.
SET CONSTRAINTS ALL IMMEDIATE;

INSERT INTO django_migrations (app, name, applied)
  VALUES ('courses', '0078_two_referral_columns', now());

COMMIT;
```

`updated_at` is deliberately left alone (the Django migration's queryset `update()` does not touch it
either).

## Post-checks (read-only)

```sql
BEGIN READ ONLY;
SELECT code FROM partner_organisations WHERE is_referral_partner;                     -- cumig
SELECT column_default, is_nullable FROM information_schema.columns
 WHERE table_name = 'partner_organisations' AND column_name = 'is_referral_partner';   -- false | NO
SELECT o.code, count(*) FROM api_student_profiles p
  JOIN partner_organisations o ON o.id = p.referred_by_org_id GROUP BY o.code;        -- cumig 254 only
-- ⚠ Read straight after COMMIT. AFTER the deploy CUMIG's figure may GROW and that is not a failure:
-- a cleared applicant whose browser still holds `?ref=cumig` is linked on her next sign-in (a `?ref`
-- now applies first touch to an empty column), exactly as the new rule says.
SELECT count(*) FROM public.referral_link_backup_20261009;                            -- N
SELECT o.code, count(*) FROM api_student_profiles p
  JOIN partner_organisations o ON o.id = p.source_id GROUP BY o.code ORDER BY o.code; -- sums to S
SELECT count(*) FROM api_student_profiles p JOIN partner_organisations o ON o.code = 'cumig'
 WHERE p.source_id = o.id AND p.referred_by_org_id = o.id;                            -- 13 ("Filled")
SELECT relrowsecurity FROM pg_class WHERE relname = 'referral_link_backup_20261009';  -- t
SELECT policyname FROM pg_policies WHERE tablename = 'referral_link_backup_20261009'; -- one service_role
SELECT name FROM django_migrations WHERE app = 'courses' ORDER BY name DESC LIMIT 1;   -- 0078_…
COMMIT;
```

Then run the Supabase Security Advisor (0 errors before deploy), and diff the ledger against the
migration files (no gap).

## After the deploy — sweep the window (idempotent)

Between this cutover and the new image going live, the OLD image still runs: its bursary submit links
`referred_by_org` to the chosen source and leaves `source_id` empty, and its sign-in sync re-links any
active row. Once `status.latestReadyRevisionName` is the new revision, re-run steps 2–4 with the
backup step as an INSERT (the first value is kept):

```sql
BEGIN;
INSERT INTO public.referral_link_backup_20261009 (supabase_user_id, referred_by_org_id, backed_up_at)
SELECT p.supabase_user_id, p.referred_by_org_id, now() FROM api_student_profiles p
 WHERE p.referred_by_org_id IS NOT NULL
   AND p.referred_by_org_id NOT IN (SELECT id FROM partner_organisations WHERE is_referral_partner)
ON CONFLICT (supabase_user_id) DO NOTHING;
-- then step 3 and step 4 exactly as above (expect small numbers, usually 0)
COMMIT;
```

Then two read-only checks of the window:

```sql
BEGIN READ ONLY;
-- A. Profiles linked to CUMIG whose application submitted SINCE THE CUTOVER recorded `cumig`.
--    expect: 0 (pre-check 9 held: no open gift offered cumig). Any row may be an OLD-image CUMIG pick
--    that the sweep KEEPS (it is a partner link) — or a genuine `?ref=cumig` student who then picked
--    CUMIG on the new image. Compare `submitted_at` with the deploy time and take the list to the
--    owner; never clear one without her ruling.
SELECT p.supabase_user_id, a.id AS application_id, a.submitted_at
  FROM api_student_profiles p
  JOIN partner_organisations o ON o.id = p.referred_by_org_id AND o.code = 'cumig'
  JOIN scholarship_applications a ON a.profile_id = p.supabase_user_id
 WHERE a.intake_snapshot -> 'profile' ->> 'referral_source' = 'cumig'
   AND a.submitted_at >= (SELECT applied FROM django_migrations
                           WHERE app = 'courses' AND name = '0078_two_referral_columns')
 ORDER BY a.submitted_at;
-- B. Chip drift again (pre-check 10). expect: 1 (the 0077 move). More = an OLD-image sign-in sync
--    rewrote an applicant's chip in the window; list them for the owner before repairing anything.
COMMIT;
```

## Rollback

**Before the deploy** (the old image reads neither column):

```sql
BEGIN;
UPDATE api_student_profiles p SET referred_by_org_id = b.referred_by_org_id
  FROM public.referral_link_backup_20261009 b
 WHERE p.supabase_user_id = b.supabase_user_id;
ALTER TABLE api_student_profiles DROP COLUMN source_id;
ALTER TABLE partner_organisations DROP COLUMN is_referral_partner;
DELETE FROM django_migrations WHERE app = 'courses' AND name = '0078_two_referral_columns';
COMMIT;
-- Keep the backup table until the owner says the cutover is settled; then DROP it.
```

**After the deploy** the new image selects both columns on every profile and organisation read:
dropping either 500s the site. Roll the service back to the previous revision FIRST, then run the
rollback above. Restoring only the links (the first `UPDATE` alone) is safe with the new image live —
it puts the source-only students back on `referred_by_org`, which no partner login reads (only `cumig`
has logins) but the witness fallback does. ⚠ After the deploy that restore OVERWRITES any `?ref=cumig`
link made since the cutover for the same profiles (a cleared applicant who signed in again holding the
CUMIG link) — add `AND p.referred_by_org_id IS NULL` to its `WHERE` to keep those.

## Order — migrate FIRST, then deploy

Deploying before this is applied 500s every `StudentProfile` and `PartnerOrganisation` read (Django
selects every model field). Applying it first is safe for the image already serving: it never names
`source_id`, and `is_referral_partner` has a database default.

## Deploy window (accepted, with one guard)

For the minutes between the cutover and the new revision the OLD image keeps its old writers:
- **Its bursary submit links `referred_by_org` to the picked source and leaves `source_id` empty.**
  For a source that is not a referral partner (smc, pptm, …) the post-deploy sweep backs the link up,
  clears it and fills `source_id` from the snapshot — fully repaired. **For a CUMIG pick it is NOT
  repaired:** the sweep keeps every link to a referral partner, so that student would stay on CUMIG's
  course-selector list (and gain `source = cumig`, the "Filled" state). That can only happen if an
  OPEN gift offers `cumig`; pre-check 9 asserts none does, the cutover refuses to run if one does, and
  post-deploy check A lists any such profile for the owner.
- **Its sign-in sync rewrites the chip and links ANY active row** from the browser's saved code. A
  non-partner link is cleared by the sweep; a `cumig` link from a saved `?ref=cumig` is a genuine
  referral-partner link and is kept (as the new rule would have made it); an applicant's chip rewritten
  in the window shows in post-deploy check B.
