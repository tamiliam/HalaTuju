# Each application keeps its own "Who referred you?" (sources and referral partners, Sprint C) — prod cutover SQL

**Migration:** MIGRATE-FIRST (before the push, ONE transaction): `scholarship/0174_application_source`
— one ledger row. Nothing else. No courses migration this sprint.

Ledger before: scholarship ends at `0173`, courses at `0080` (main `d15c0f14`, Sprint B live
2026-10-19). If another session has taken 0174 on `main` by the time this is applied, the sprint
renumbers on rebase and this file's ledger row changes with it — never apply a number that is not
settled.

**Status:** written 2026-10-19 by the sprint; NOT applied. The lead applies it to production
(Supabase `pbrrlyoyyiftckqvzvvo`) after re-running every pre-check and telling the owner of any count
that differs from the expected one BEFORE applying (lessons.md 2026-10-09). **This cutover is
ADDITIVE ONLY** (two columns, three indexes, a backfill). The only destructive SQL is the ROLLBACK at
the end, which is marked for the owner to run in the SQL Editor.

## What it does (owner's rulings, 2026-10-09, accepted for Sprint C)

1. Two columns on `scholarship_applications`:
   - `referral_code varchar(50) NOT NULL DEFAULT ''` — the answer to "Who referred you?" ON THIS
     APPLICATION, as given at submit: a source's code or a fixed choice (`halatuju`, `social`,
     `other`), `''` for none. The DATABASE default is what lets the image still serving (which never
     names the column) keep inserting applications between this cutover and the deploy.
   - `source_id bigint NULL → referral_sources(id)` — that code's SOURCE, **resolved inside the
     application's own organisation** (`owning_organisation_id`); NULL for a fixed choice, a blank,
     or a code that organisation has no source for.
2. Backfill: both columns from the answer the application FROZE at submit,
   `intake_snapshot -> 'profile' ->> 'referral_source'` — never the profile's latest chip. The same
   rule as the new submit (`gift_sources.submitted_source`) and as the migration's RunPython.
3. After the deploy: partner emails (weekly digests, milestones), the Sources "Students" counts, the
   Applications Source filter / column / sort and the cockpit pill read these columns. The witness is
   the application's source (or the admin override) — never the referral partner, never another
   organisation's source. **Owner ruling 1 changes counts on purpose:** a student whose later
   application named a different source is no longer re-attributed; pre-check 6 lists every source's
   count before and after for the owner.

Nothing here touches `api_student_profiles` (its `referral_source` chip, `source_id` and
`referred_by_org_id` stay exactly as they are — the chip is retired in Sprint D), `partner_organisations`,
`referral_sources`, `partner_admins` or any witness column.

The DDL was rendered OFFLINE from the migration with Django's postgresql schema editor (no connection;
a dev box's `sqlmigrate` renders SQLite). One departure, deliberate: Django emits the column ADDs then
the indexes; here the backfill sits between them and `SET CONSTRAINTS ALL IMMEDIATE` follows it,
because the UPDATE of a `DEFERRABLE INITIALLY DEFERRED` foreign key queues trigger events that make
Postgres refuse a later `CREATE INDEX` in the same transaction (the 0163 rule, `halatuju_api/CLAUDE.md`).

## Pre-checks (read-only — run first, write the answers into the cutover note)

```sql
BEGIN READ ONLY;

-- 1. Ledger: scholarship ends at 0173; 0174 is not recorded.
SELECT app, name FROM django_migrations
 WHERE app = 'scholarship' ORDER BY name DESC LIMIT 3;
-- expect: 0173_referral_sources first; no 0174_* row.

-- 2. The columns do not exist yet.
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'scholarship_applications' AND column_name IN ('referral_code', 'source_id');
-- expect: 0 rows.

-- 3. Applications, and those with no owning organisation (they can name no source).
SELECT count(*) AS applications,
       count(*) FILTER (WHERE owning_organisation_id IS NULL) AS no_owner
  FROM scholarship_applications;
-- expect: applications = N (write it down); no_owner = 0 (Sprint 2 backfill: production has none).

-- Checks 4 to 8 each start with the same CTE `answer`: the code each application FROZE at submit
-- (a non-string or missing value reads as '') — exactly what the cutover writes to referral_code.

-- 4. What referral_code will hold: one row per answer.
WITH answer AS (
  SELECT LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50) AS code
    FROM scholarship_applications a)
SELECT code, count(*) FROM answer GROUP BY code ORDER BY count(*) DESC, code;
-- expect: the rows sum to N. Write the list down (post-check B compares against it).

-- 5. How many get a source (S), and any answer naming a code that is a source ONLY in another
--    organisation (the TD-386 (a) case — it gets NO source, by rule).
WITH answer AS (
  SELECT a.id, a.owning_organisation_id,
         LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50) AS code
    FROM scholarship_applications a)
SELECT
  count(*) FILTER (WHERE EXISTS (SELECT 1 FROM referral_sources s
                                  WHERE s.organisation_id = x.owning_organisation_id
                                    AND s.code = x.code)
                     AND x.code NOT IN ('', 'halatuju', 'social', 'other')) AS gets_a_source,
  count(*) FILTER (WHERE x.code NOT IN ('', 'halatuju', 'social', 'other')
                     AND NOT EXISTS (SELECT 1 FROM referral_sources s
                                      WHERE s.organisation_id = x.owning_organisation_id
                                        AND s.code = x.code)) AS names_no_own_source
  FROM answer x;
-- expect: gets_a_source = S (write it down); names_no_own_source = R — every such row listed by
-- check 5b. With one tenant (BrightPath) R is the answers naming a code that was never a source
-- (e.g. a legacy code, or 'brightpath' itself); ASK THE OWNER if R > 0 before applying.

-- 5b. The R rows, by code.
WITH answer AS (
  SELECT a.owning_organisation_id,
         LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50) AS code
    FROM scholarship_applications a)
SELECT code, count(*) FROM answer x
 WHERE x.code NOT IN ('', 'halatuju', 'social', 'other')
   AND NOT EXISTS (SELECT 1 FROM referral_sources s
                    WHERE s.organisation_id = x.owning_organisation_id AND s.code = x.code)
 GROUP BY code ORDER BY code;

-- 6. PARTNER-EMAIL / SOURCES COUNTS, BEFORE vs AFTER, per source — FOR THE OWNER (ruling 1).
--    before = today's live rule (the PROFILE's chip = the code, within the source's organisation);
--    after  = the application's own answer (what this cutover writes).
WITH answer AS (
  SELECT a.id, a.owning_organisation_id,
         LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50) AS code
    FROM scholarship_applications a)
SELECT s.id, s.code, s.name, s.is_active, (s.contact_email <> '') AS has_email,
       (SELECT count(*) FROM scholarship_applications a
          LEFT JOIN api_student_profiles p ON p.supabase_user_id = a.profile_id
         WHERE p.referral_source = s.code AND a.owning_organisation_id = s.organisation_id) AS before,
       -- (a profile-deleted application has no chip: never in "before", but in "after" if it named s)
       (SELECT count(*) FROM answer x
         WHERE x.code = s.code AND x.owning_organisation_id = s.organisation_id) AS after
  FROM referral_sources s
 ORDER BY s.name;
-- expect: one row per source; give the whole table to the owner. A difference is a student whose
-- LATEST answer (chip) differs from what an application of hers answered. Check 7 counts them.

-- 7. Applications whose own answer differs from the student's current chip (the re-attributions
--    ruling 1 stops).
WITH answer AS (
  SELECT a.id, a.profile_id,
         LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50) AS code
    FROM scholarship_applications a)
SELECT count(*) AS differs
  FROM answer x LEFT JOIN api_student_profiles p ON p.supabase_user_id = x.profile_id
 WHERE COALESCE(p.referral_source, '') <> x.code;
-- expect: D (write it down). D = 0 means before = after on every row of check 6. LEFT JOIN on
-- purpose (review): an application whose profile was deleted has no chip, so it counts as
-- differing whenever it named something.

-- 8. WITNESS CHANGES (owner rulings 2 and 3) — applications that could be asked to witness
--    (awarded / active / maintenance) whose witness organisation changes:
--    old = override, else the profile's source, else the referral partner's source twin;
--    new = override, else this application's own source.
WITH answer AS (
  SELECT a.id, a.status, a.witness_org_id, a.owning_organisation_id, a.profile_id,
         LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50) AS code
    FROM scholarship_applications a
   WHERE a.status IN ('awarded', 'active', 'maintenance'))
SELECT x.id, x.status,
       COALESCE(x.witness_org_id, p.source_id, twin.id) AS old_witness,
       COALESCE(x.witness_org_id, own.id) AS new_witness
  FROM answer x
  LEFT JOIN api_student_profiles p ON p.supabase_user_id = x.profile_id
  LEFT JOIN partner_organisations po ON po.id = p.referred_by_org_id
  LEFT JOIN referral_sources twin ON twin.id = po.id AND twin.code = po.code
  LEFT JOIN referral_sources own
         ON own.organisation_id = x.owning_organisation_id AND own.code = x.code
        AND x.code NOT IN ('', 'halatuju', 'social', 'other')
 WHERE COALESCE(x.witness_org_id, p.source_id, twin.id) IS DISTINCT FROM COALESCE(x.witness_org_id, own.id)
 ORDER BY x.id;
-- expect: W rows (write them down and give them to the owner). Each is a student who came by a
-- referral partner's link without naming it as her source, or whose profile source moved since she
-- applied. `BURSARY_AGREEMENT_ENABLED` is off, so nothing is emailed by this change today.

-- 9. Recorded witness attestations stay as they are (this cutover writes no witness column).
SELECT count(*) FROM bursary_agreements WHERE witness_signed_at IS NOT NULL;
-- expect: the same number at post-check E.

-- 10. THE MILESTONE BACKLOG (review fix; owner 2026-07-26: partner milestone emails are "only
--     moving forward"). Applications in a milestone state, NOT stamped, whose own answer names a
--     source of their organisation, but which the old chip rule never reached (the chip differs,
--     or the profile is gone). Under the new rule each would become due at the next hourly run and
--     email a source about a months-old event. The cutover STAMPS them (below) so they never send.
WITH answer AS (
  SELECT a.id, a.status, a.owning_organisation_id, a.profile_id,
         a.partner_awaiting_notified_at, a.partner_awarded_notified_at,
         LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50) AS code
    FROM scholarship_applications a)
SELECT x.id, x.status, x.code, s.is_active, (s.contact_email <> '') AS has_email
  FROM answer x
  JOIN referral_sources s ON s.organisation_id = x.owning_organisation_id AND s.code = x.code
  LEFT JOIN api_student_profiles p ON p.supabase_user_id = x.profile_id
 WHERE x.code NOT IN ('', 'halatuju', 'social', 'other')
   AND ((x.status = 'profile_complete' AND x.partner_awaiting_notified_at IS NULL)
     OR (x.status IN ('awarded', 'active', 'maintenance') AND x.partner_awarded_notified_at IS NULL))
   AND (p.supabase_user_id IS NULL OR p.referral_source IS DISTINCT FROM x.code)
 ORDER BY x.id;
-- expect: 0 rows (lead's production read, 2026-10-19 — counted only rows naming an ACTIVE source
-- with an email; this check lists every one). ASK THE OWNER IF > 0 before applying: the cutover
-- stamps them as told (never emailed).

ROLLBACK;
```

## The cutover (ONE transaction)

⚠ **Run it in a quiet hour** (late evening MYT): `ALTER TABLE … ADD COLUMN … REFERENCES` and the
indexes hold a lock on `scholarship_applications` for the whole transaction, so every application
read and write waits until the commit. **Write down the time you start it** (`SELECT now();`) — the
post-deploy sweep needs it as `<<CUTOVER_AT>>`.

Replace `<<N>>` (check 3) and `<<S>>` (check 5) — each appears in the asserting `DO` block.

```sql
BEGIN;

-- DDL, rendered offline from scholarship 0174 with Django's postgresql schema editor.
ALTER TABLE "scholarship_applications" ADD COLUMN "referral_code" varchar(50) DEFAULT '' NOT NULL;
ALTER TABLE "scholarship_applications" ADD COLUMN "source_id" bigint NULL CONSTRAINT "scholarship_applicat_source_id_6a6f120d_fk_referral_" REFERENCES "referral_sources"("id") DEFERRABLE INITIALLY DEFERRED;

-- Backfill (= `fill_from_snapshot`): the answer frozen at submit, then its source INSIDE the
-- application's own organisation. Fixed choices and blanks name no source.
UPDATE scholarship_applications a
   SET referral_code = LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                                 THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50);
UPDATE scholarship_applications a
   SET source_id = s.id
  FROM referral_sources s
 WHERE s.organisation_id = a.owning_organisation_id
   AND s.code = a.referral_code
   AND a.referral_code NOT IN ('', 'halatuju', 'social', 'other');

-- Stamp the milestone backlog (= scholarship 0174's `stamp_the_backlog`; pre-check 10). The SELECT
-- prints the ids — copy them into the cutover note. Expected: the rows pre-check 10 listed.
CREATE TEMP TABLE sources_c_backlog ON COMMIT DROP AS
SELECT a.id, a.status FROM scholarship_applications a
  LEFT JOIN api_student_profiles p ON p.supabase_user_id = a.profile_id
 WHERE a.source_id IS NOT NULL
   AND ((a.status = 'profile_complete' AND a.partner_awaiting_notified_at IS NULL)
     OR (a.status IN ('awarded', 'active', 'maintenance') AND a.partner_awarded_notified_at IS NULL))
   AND (p.supabase_user_id IS NULL OR p.referral_source IS DISTINCT FROM a.referral_code);
SELECT id, status FROM sources_c_backlog ORDER BY id;
UPDATE scholarship_applications SET partner_awaiting_notified_at = now()
 WHERE id IN (SELECT id FROM sources_c_backlog WHERE status = 'profile_complete');
UPDATE scholarship_applications SET partner_awarded_notified_at = now()
 WHERE id IN (SELECT id FROM sources_c_backlog WHERE status IN ('awarded', 'active', 'maintenance'));

-- The UPDATEs queued deferred-FK events; settle them before any CREATE INDEX (the 0163 rule).
SET CONSTRAINTS ALL IMMEDIATE;

CREATE INDEX "scholarship_applications_referral_code_0a2365a5" ON "scholarship_applications" ("referral_code");
CREATE INDEX "scholarship_applications_referral_code_0a2365a5_like" ON "scholarship_applications" ("referral_code" varchar_pattern_ops);
CREATE INDEX "scholarship_applications_source_id_6a6f120d" ON "scholarship_applications" ("source_id");

-- Assert before committing: every row equals its snapshot answer, the counts are the pre-checks',
-- and no application names another organisation's source.
DO $$
DECLARE n int; s int; mismatched int; cross_org int;
BEGIN
  SELECT count(*), count(source_id) INTO n, s FROM scholarship_applications;
  SELECT count(*) INTO mismatched FROM scholarship_applications a
   WHERE a.referral_code IS DISTINCT FROM
         LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                   THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50);
  SELECT count(*) INTO cross_org FROM scholarship_applications a
    JOIN referral_sources r ON r.id = a.source_id
   WHERE r.organisation_id IS DISTINCT FROM a.owning_organisation_id OR r.code <> a.referral_code;
  IF n <> <<N>> THEN RAISE EXCEPTION 'applications: % (expected <<N>>)', n; END IF;
  IF s <> <<S>> THEN RAISE EXCEPTION 'with a source: % (expected <<S>>)', s; END IF;
  IF mismatched <> 0 THEN RAISE EXCEPTION '% application(s) differ from their snapshot answer', mismatched; END IF;
  IF cross_org <> 0 THEN RAISE EXCEPTION '% application(s) name another organisation''s source', cross_org; END IF;
END $$;

INSERT INTO django_migrations (app, name, applied)
VALUES ('scholarship', '0174_application_source', now());

COMMIT;
```

⚠ Applications are still arriving: if check 3's N moved between the pre-check and the apply, the
`DO` block refuses and nothing is written — re-run checks 3 and 5 and apply again. That is the point.

## Post-checks (read-only, straight after the commit)

```sql
BEGIN READ ONLY;

-- A. Ledger row, and the three indexes.
SELECT app, name FROM django_migrations WHERE app = 'scholarship' ORDER BY name DESC LIMIT 2;
SELECT indexname FROM pg_indexes WHERE tablename = 'scholarship_applications'
   AND indexname IN ('scholarship_applications_referral_code_0a2365a5',
                     'scholarship_applications_referral_code_0a2365a5_like',
                     'scholarship_applications_source_id_6a6f120d');
-- expect: 0174_application_source on top; 3 index rows.

-- B. EACH APPLICATION'S NEW SOURCE EQUALS ITS SUBMIT-TIME ANSWER.
SELECT count(*) AS code_mismatch FROM scholarship_applications a
 WHERE a.referral_code IS DISTINCT FROM
       LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                 THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50);
SELECT count(*) AS source_mismatch FROM scholarship_applications a
  LEFT JOIN referral_sources s
         ON s.organisation_id = a.owning_organisation_id AND s.code = a.referral_code
        AND a.referral_code NOT IN ('', 'halatuju', 'social', 'other')
 WHERE a.source_id IS DISTINCT FROM s.id;
SELECT referral_code, count(*) FROM scholarship_applications GROUP BY referral_code ORDER BY 2 DESC, 1;
-- expect: 0, 0, and the list equals pre-check 4's.

-- C. Never another organisation's source.
SELECT count(*) FROM scholarship_applications a JOIN referral_sources r ON r.id = a.source_id
 WHERE r.organisation_id IS DISTINCT FROM a.owning_organisation_id;
-- expect: 0.

-- D. Partner-email / Sources counts now (= pre-check 6's "after" column, row for row).
SELECT s.code, s.name, count(a.id) AS students
  FROM referral_sources s
  LEFT JOIN scholarship_applications a
         ON a.source_id = s.id AND a.owning_organisation_id = s.organisation_id
 GROUP BY s.id, s.code, s.name ORDER BY s.name;

-- E. Nothing else moved.
SELECT count(*) FROM bursary_agreements WHERE witness_signed_at IS NOT NULL;   -- = pre-check 9
SELECT count(*) FROM api_student_profiles WHERE referred_by_org_id IS NOT NULL; -- = before (CUMIG list)

ROLLBACK;
```

## Between the cutover and the deploy

The image still serving does not know the columns: an application submitted in this window is
inserted with `referral_code = ''` and `source_id = NULL` (the database default), and its partner
emails still read the profile chip until the deploy. Nothing breaks; the window's rows are filled by
the sweep below. No freeze is needed (Sources and gift Configuration are untouched by this sprint).

## After the deploy (once `status.latestReadyRevisionName` is the new revision)

Re-run the backfill for the applications submitted in the window — ONLY those submitted at or after
the cutover's start (`<<CUTOVER_AT>>`, the time you wrote down). **Run it twice, a few minutes
apart**: a submit still in flight on an old-image instance at the first run lands after it. It is
idempotent; the new image writes both columns itself, so its rows are never touched.

```sql
BEGIN;
UPDATE scholarship_applications a
   SET referral_code = LEFT(CASE WHEN jsonb_typeof(a.intake_snapshot -> 'profile' -> 'referral_source') = 'string'
                                 THEN a.intake_snapshot -> 'profile' ->> 'referral_source' ELSE '' END, 50)
 WHERE a.submitted_at >= '<<CUTOVER_AT>>'
   AND a.referral_code = '' AND a.source_id IS NULL;
UPDATE scholarship_applications a
   SET source_id = s.id
  FROM referral_sources s
 WHERE a.submitted_at >= '<<CUTOVER_AT>>'
   AND a.source_id IS NULL
   AND s.organisation_id = a.owning_organisation_id
   AND s.code = a.referral_code
   AND a.referral_code NOT IN ('', 'halatuju', 'social', 'other');
COMMIT;
```

Then re-run post-check B (expect 0, 0) and tell the owner how many rows each sweep filled. (A window
row cannot be a milestone backlog: it was submitted after the cutover, so any milestone it reaches
happens later and is told normally.)

## Rollback

**Before the deploy** (the serving image never reads the columns): ⚠ **OWNER RUNS IN SQL EDITOR** —
it drops columns, which the lead's MCP tool is blocked from doing.

```sql
-- OWNER RUNS IN SQL EDITOR (destructive). Only while the PREVIOUS image is the one serving.
BEGIN;
DROP INDEX IF EXISTS "scholarship_applications_referral_code_0a2365a5";
DROP INDEX IF EXISTS "scholarship_applications_referral_code_0a2365a5_like";
DROP INDEX IF EXISTS "scholarship_applications_source_id_6a6f120d";
ALTER TABLE "scholarship_applications" DROP COLUMN "source_id";
ALTER TABLE "scholarship_applications" DROP COLUMN "referral_code";
DELETE FROM django_migrations WHERE app = 'scholarship' AND name = '0174_application_source';
COMMIT;
```

**After the deploy:** first shift Cloud Run traffic back to the previous revision (no build) — the new
image SELECTs both columns on every application read and would 500 without them. Only then, if the
columns must go, the owner runs the block above. Leaving them in place under the old image is
harmless (it never reads them, and the database default covers its inserts), so the usual rollback is
the traffic shift alone. Nothing is lost either way: every value is derived from `intake_snapshot`,
which this cutover never writes.
