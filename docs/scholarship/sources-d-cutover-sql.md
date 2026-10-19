# Retire the old shared fields and rows (sources and referral partners, Sprint D) — prod cutover SQL

**Migrations:** two, in OPPOSITE orders.
- `courses/0081_retire_old_source_rows` — **MIGRATE-FIRST** (before the push, ONE transaction, the
  lead applies it): a database default for `partner_organisations.show_in_apply`, the sources' old
  rows switched off (never deleted), a referral partner's students' chips aligned to its code (after
  a dated backup), one ledger row. Additive / data-update only.
- `courses/0082_drop_retired_source_columns` — **IMAGE-FIRST** (after the Sprint D revision serves,
  and no older revision carries traffic): drops `api_student_profiles.source_id` and
  `partner_organisations.show_in_apply`, after backing both up. **⚠ OWNER RUNS IT IN THE SUPABASE
  SQL EDITOR** (the lead's MCP tool is blocked from destructive SQL).

Ledger before: courses ends at `0080`, scholarship at `0174` (main `ad98107a`, Sprints A–C live). No
scholarship migration this sprint. If another session has taken courses 0081 on `main` by the time
this is applied, the sprint renumbers on rebase and this file's ledger rows change with it — never
apply a number that is not settled.

**Status:** written 2026-10-19 by the sprint; NOT applied. Re-run every pre-check against production
immediately before applying, write the answers into the cutover note, and tell the owner of any
count that differs from the expected one BEFORE applying (lessons.md 2026-10-09).

## What it does

1. **`show_in_apply` gets `DEFAULT false`.** The column is `NOT NULL` with NO database default (0065
   added it with a Python default only). The Sprint D image no longer has the field, so its inserts
   into `partner_organisations` (a new referral partner made by a partner invite; a new tenant made
   by the organisation form) do not name the column — without the default every such insert fails
   between the deploy and the drop. The old image names the column, so the default changes nothing
   for it.
2. **The sources' old rows are switched off — `is_active = false`, never deleted** (roadmap item 1;
   old intake snapshots name their codes). A source's old row is a `partner_organisations` row
   Sprint B copied into `referral_sources` KEEPING ITS ID, so it has a twin there with the same id
   AND the same code. Retired: such a row that is active, NOT a referral partner (CUMIG's row is the
   referral partner and stays live) and NOT a tenant. Since Sprint B nothing reads these rows for a
   source; the public branding endpoint already treats an inactive code as the platform's.
3. **(Review fix) a referral partner's students show that partner's code on the chip.** Before
   Sprint D the bursary submit wrote its answer onto the chip, so a student who came by CUMIG's link
   and later answered the bursary form can show that answer on CUMIG's Source column (lead's read:
   253 `cumig`, 1 `social`). The old values go to a dated backup table first, then the chip is set
   to the partner's code — for every referral partner, not only CUMIG. Only after this is the claim
   "a bursary answer no longer reaches a referral partner's logins" true for existing students.
4. **After the deploy, the drop** (owner): `api_student_profiles.source_id` (the profile's bursary
   source — written by nothing and read by nothing in the Sprint D image; the application carries
   its own since Sprint C) and `partner_organisations.show_in_apply`, each backed up first.

**Not dropped, on purpose:** `api_student_profiles.referral_source` (the chip) STAYS LIVE. The roadmap
said "retire the chip"; Sprint D re-scoped it instead (decisions.md 2026-10-19): it is the
course-selector partner dashboard's Source column / filter / CSV, and from this image on only the
`?ref=` sync writes it (first touch). The bursary no longer writes it, so a bursary answer can no
longer reach the referral partner's logins on that column.

The DDL was rendered OFFLINE from the migrations with Django's postgresql schema editor (no
connection; a dev box's `sqlmigrate` renders SQLite): 0081 →
`ALTER TABLE "partner_organisations" ALTER COLUMN "show_in_apply" SET DEFAULT false` (+ the
RunPython); 0082 → `ALTER TABLE "partner_organisations" DROP COLUMN "show_in_apply" CASCADE`, then
`SET CONSTRAINTS "<fk>" IMMEDIATE; ALTER TABLE "api_student_profiles" DROP CONSTRAINT "<fk>"` and
`ALTER TABLE "api_student_profiles" DROP COLUMN "source_id" CASCADE`. The hand-applied copies below
find the FK by `pg_constraint` lookup and drop WITHOUT `CASCADE` on purpose.

## Pre-checks (read-only — run first, write the answers into the cutover note)

```sql
BEGIN READ ONLY;

-- 1. Ledger: courses ends at 0080; 0081/0082 are not recorded.
SELECT app, name FROM django_migrations WHERE app = 'courses' ORDER BY name DESC LIMIT 3;
-- expect: 0080_drop_partner_organisation_programme first; no 0081_* / 0082_* row.

-- 2. show_in_apply has no database default yet; both columns still exist.
SELECT table_name, column_name, column_default, is_nullable FROM information_schema.columns
 WHERE (table_name = 'partner_organisations' AND column_name = 'show_in_apply')
    OR (table_name = 'api_student_profiles' AND column_name = 'source_id')
 ORDER BY table_name;
-- expect: 2 rows — api_student_profiles.source_id (NULL default, YES nullable);
--         partner_organisations.show_in_apply (NULL default, NO nullable).

-- 3. Every partner_organisations row, by category (the WHOLE table — it is small).
SELECT o.id, o.code, o.is_active, o.is_referral_partner,
       EXISTS (SELECT 1 FROM referral_sources s WHERE s.id = o.id AND s.code = o.code) AS has_twin,
       (EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
        OR EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                                                    AND a.role = 'org_admin' AND a.is_active)) AS is_tenant
  FROM partner_organisations o ORDER BY o.id;
-- expect: exactly ONE tenant (brightpath), never with has_twin; cumig is_referral_partner AND
-- has_twin AND active; every other has_twin row is a source's old row. Write the table down.

-- 4. THE ROWS THIS CUTOVER SWITCHES OFF (= courses 0081's `retire_old_source_rows`).
SELECT o.id, o.code, o.name FROM partner_organisations o
 WHERE o.is_active AND NOT o.is_referral_partner
   AND EXISTS (SELECT 1 FROM referral_sources s WHERE s.id = o.id AND s.code = o.code)
   AND NOT EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
   AND NOT EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                                                   AND a.role = 'org_admin' AND a.is_active)
 ORDER BY o.id;
-- expect: R rows (write the ids down — the rollback needs them). Sprint B copied 15 rows (CUMIG
-- among them) and nothing writes these rows since, so has_twin in check 3 should be 15 and
-- R = 14 minus those already switched off before Sprint B (check 3 shows which). ASK THE OWNER
-- if has_twin <> 15 before applying.

-- 5. Nothing still POINTS at a row being switched off in a way that would change behaviour.
WITH retire AS (
  SELECT o.id FROM partner_organisations o
   WHERE o.is_active AND NOT o.is_referral_partner
     AND EXISTS (SELECT 1 FROM referral_sources s WHERE s.id = o.id AND s.code = o.code)
     AND NOT EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
     AND NOT EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                                                     AND a.role = 'org_admin' AND a.is_active))
SELECT (SELECT count(*) FROM api_student_profiles WHERE referred_by_org_id IN (SELECT id FROM retire)) AS linked_students,
       (SELECT count(*) FROM partner_admins WHERE role = 'partner' AND is_active
                                              AND org_id IN (SELECT id FROM retire)) AS partner_logins,
       (SELECT count(*) FROM partner_admins WHERE is_active AND org_id IN (SELECT id FROM retire)) AS any_staff_referring_org;
-- expect: linked_students = 0 (Sprint A cleared every link to a non-partner row; `?ref=` links only
-- referral partners since); partner_logins = 0 (Sprint B refuses a partner login onto a non-partner
-- row); any_staff_referring_org = K, informational only — `PartnerAdmin.org` is attribution, never
-- access, and nothing reads the row's `is_active` for it.

-- 6. The referral partner's list today (must be the same after).
SELECT count(*) FROM api_student_profiles WHERE referred_by_org_id =
       (SELECT id FROM partner_organisations WHERE code = 'cumig');
-- expect: C (write it down; Sprint B read 254 — it may have GROWN since through `?ref=cumig`).

-- 6b. THE CHIP ON EACH REFERRAL PARTNER'S STUDENTS (review fix). One row per (partner, chip).
SELECT o.code AS partner, p.referral_source AS chip, count(*)
  FROM api_student_profiles p JOIN partner_organisations o ON o.id = p.referred_by_org_id
 WHERE o.is_referral_partner
 GROUP BY o.code, p.referral_source ORDER BY o.code, count(*) DESC;
-- expect: cumig / cumig 253, cumig / social 1 (lead's read 2026-10-19). The rows whose chip is not
-- the partner's code are A (expect 1) — ASK THE OWNER if A differs before applying.

-- 7. For the after-deploy drop: what the two columns hold now (both get a backup table).
SELECT count(*) FILTER (WHERE source_id IS NOT NULL) AS profiles_with_source FROM api_student_profiles;
SELECT count(*) FILTER (WHERE show_in_apply) AS rows_shown FROM partner_organisations;
-- expect: P and Q, informational (the backups must hold the same numbers).

ROLLBACK;
```

## The cutover — ONE transaction (migrate-first, BEFORE the push; the lead applies it)

Replace `<<R>>` (check 4) and `<<A>>` (check 6b, expect 1) — each appears twice in the asserting
`DO` block.

```sql
BEGIN;

-- 1. DDL, rendered offline from courses 0081 (the AlterField adding `db_default=False`).
ALTER TABLE "partner_organisations" ALTER COLUMN "show_in_apply" SET DEFAULT false;

-- 2. The data step (= `retire_old_source_rows`). The SELECT prints the ids: copy them into the
--    cutover note (the rollback switches exactly those back on).
CREATE TEMP TABLE sources_d_retired ON COMMIT DROP AS
SELECT o.id, o.code FROM partner_organisations o
 WHERE o.is_active AND NOT o.is_referral_partner
   AND EXISTS (SELECT 1 FROM referral_sources s WHERE s.id = o.id AND s.code = o.code)
   AND NOT EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
   AND NOT EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                                                   AND a.role = 'org_admin' AND a.is_active);
SELECT id, code FROM sources_d_retired ORDER BY id;
UPDATE partner_organisations SET is_active = false WHERE id IN (SELECT id FROM sources_d_retired);

-- 2b. (= `align_partner_chips`) Back up, then align the chip of every referral partner's student.
CREATE TABLE public.referral_chip_backup_20261019 AS
SELECT p.supabase_user_id, p.referral_source AS old_chip, o.code AS new_chip, now() AS backed_up_at
  FROM api_student_profiles p JOIN partner_organisations o ON o.id = p.referred_by_org_id
 WHERE o.is_referral_partner AND p.referral_source IS DISTINCT FROM o.code;
ALTER TABLE public.referral_chip_backup_20261019 ENABLE ROW LEVEL SECURITY;
CREATE POLICY referral_chip_backup_20261019_service_role ON public.referral_chip_backup_20261019
  FOR ALL TO service_role USING (true) WITH CHECK (true);
UPDATE api_student_profiles p SET referral_source = o.code
  FROM partner_organisations o
 WHERE p.referred_by_org_id = o.id AND o.is_referral_partner
   AND p.referral_source IS DISTINCT FROM o.code;

-- 3. Assert before committing.
DO $$
DECLARE r int; still_on int; cumig_ok int; tenants_off int; dflt text; backed int; stale int;
BEGIN
  SELECT count(*) INTO r FROM sources_d_retired;
  SELECT count(*) INTO still_on FROM partner_organisations o
   WHERE o.is_active AND NOT o.is_referral_partner
     AND EXISTS (SELECT 1 FROM referral_sources s WHERE s.id = o.id AND s.code = o.code)
     AND NOT EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
     AND NOT EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                                                     AND a.role = 'org_admin' AND a.is_active);
  SELECT count(*) INTO cumig_ok FROM partner_organisations
   WHERE code = 'cumig' AND is_active AND is_referral_partner;
  -- Both halves of the tenant rule (review fix): an active programme OR an active org_admin.
  SELECT count(*) INTO tenants_off FROM sources_d_retired x
   WHERE EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = x.id AND p.is_active)
      OR EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = x.id
                                                  AND a.role = 'org_admin' AND a.is_active);
  SELECT count(*) INTO backed FROM public.referral_chip_backup_20261019;
  SELECT count(*) INTO stale FROM api_student_profiles p JOIN partner_organisations o
      ON o.id = p.referred_by_org_id
   WHERE o.is_referral_partner AND p.referral_source IS DISTINCT FROM o.code;
  SELECT column_default INTO dflt FROM information_schema.columns
   WHERE table_name = 'partner_organisations' AND column_name = 'show_in_apply';
  IF r <> <<R>> THEN RAISE EXCEPTION 'retired: % (expected <<R>>)', r; END IF;
  IF still_on <> 0 THEN RAISE EXCEPTION '% old source row(s) still on', still_on; END IF;
  IF cumig_ok <> 1 THEN RAISE EXCEPTION 'the referral partner cumig is not active and marked'; END IF;
  IF tenants_off <> 0 THEN RAISE EXCEPTION 'a tenant was switched off'; END IF;
  IF dflt IS DISTINCT FROM 'false' THEN RAISE EXCEPTION 'show_in_apply default is %', dflt; END IF;
  IF backed <> <<A>> THEN RAISE EXCEPTION 'chips backed up: % (expected <<A>>)', backed; END IF;
  IF stale <> 0 THEN RAISE EXCEPTION '% referral-partner student(s) still show another chip', stale; END IF;
END $$;

INSERT INTO django_migrations (app, name, applied)
VALUES ('courses', '0081_retire_old_source_rows', now());

COMMIT;
```

## Post-checks (read-only, straight after the commit)

```sql
BEGIN READ ONLY;
SELECT name FROM django_migrations WHERE app = 'courses' ORDER BY name DESC LIMIT 1;  -- 0081_…
SELECT column_default FROM information_schema.columns
 WHERE table_name = 'partner_organisations' AND column_name = 'show_in_apply';     -- 'false'
SELECT count(*) FROM partner_organisations o WHERE NOT o.is_active
   AND EXISTS (SELECT 1 FROM referral_sources s WHERE s.id = o.id AND s.code = o.code);
-- expect: R + the rows check 3 showed already off.
SELECT count(*) FROM partner_organisations;                                       -- unchanged (nothing deleted)
SELECT count(*) FROM api_student_profiles WHERE referred_by_org_id =
       (SELECT id FROM partner_organisations WHERE code = 'cumig');                -- = check 6's C
SELECT code FROM partner_organisations WHERE is_referral_partner AND is_active;    -- cumig
SELECT o.code, p.referral_source, count(*) FROM api_student_profiles p
  JOIN partner_organisations o ON o.id = p.referred_by_org_id WHERE o.is_referral_partner
 GROUP BY 1, 2;                                                                    -- cumig / cumig 254
SELECT old_chip, new_chip, count(*) FROM public.referral_chip_backup_20261019 GROUP BY 1, 2;  -- social → cumig 1
ROLLBACK;
```

## Between the cutover and the deploy

The image still serving reads `is_active` only for tenants, referral partners and the public branding
lookup; none of them is one of the retired rows, so nothing changes for a visitor. It still writes the
profile's `source_id` and chip on a bursary submit (both columns exist); that is the last such write —
and it can re-stale the chip of a referral partner's student who applies in the window. So, once the
new revision serves, the lead re-runs the alignment (idempotent; expect 0 or a handful):

```sql
BEGIN;
INSERT INTO public.referral_chip_backup_20261019 (supabase_user_id, old_chip, new_chip, backed_up_at)
SELECT p.supabase_user_id, p.referral_source, o.code, now()
  FROM api_student_profiles p JOIN partner_organisations o ON o.id = p.referred_by_org_id
 WHERE o.is_referral_partner AND p.referral_source IS DISTINCT FROM o.code;
UPDATE api_student_profiles p SET referral_source = o.code
  FROM partner_organisations o
 WHERE p.referred_by_org_id = o.id AND o.is_referral_partner
   AND p.referral_source IS DISTINCT FROM o.code;
COMMIT;
```
No freeze needed.

## The deploy — web and api in either order

The cockpit's old `referred_by_org` key leaves the api; the web stops reading it. Both orders are safe:
- **api first** (old web): the old web reads `source ?? referred_by_org` — `source` is served, so the
  pill, the witness card and the witness button behave exactly as before.
- **web first** (old api): the Sprint C api serves BOTH keys, and the new web reads `source`.

Confirm `status.latestReadyRevisionName` is the new api revision **and that no older revision carries
any traffic** (this service carries a tagged revision at index zero — read every `status.traffic[]`
entry) before the drop below.

## After the deploy — the drop (`courses/0082`, IMAGE-FIRST)

**⚠ OWNER RUNS IN SUPABASE SQL EDITOR — after the deploy.** Only when the Sprint D revision serves
100% of traffic: every older image SELECTs both columns on every profile / organisation read, and a
drop under one 500s the site. Its own transaction, its own ledger row.

```sql
-- OWNER RUNS IN SUPABASE SQL EDITOR — after the deploy (destructive).
BEGIN;

-- Keep what the two columns said, restorable, before they go (RLS on + service_role policy).
CREATE TABLE public.student_profile_source_backup_sources_d AS
SELECT supabase_user_id, source_id, now() AS backed_up_at
  FROM api_student_profiles WHERE source_id IS NOT NULL;
ALTER TABLE public.student_profile_source_backup_sources_d ENABLE ROW LEVEL SECURITY;
CREATE POLICY student_profile_source_backup_sources_d_service_role
  ON public.student_profile_source_backup_sources_d
  FOR ALL TO service_role USING (true) WITH CHECK (true);

CREATE TABLE public.partner_org_show_in_apply_backup_sources_d AS
SELECT id AS partner_organisation_id, show_in_apply, now() AS backed_up_at
  FROM partner_organisations;
ALTER TABLE public.partner_org_show_in_apply_backup_sources_d ENABLE ROW LEVEL SECURITY;
CREATE POLICY partner_org_show_in_apply_backup_sources_d_service_role
  ON public.partner_org_show_in_apply_backup_sources_d
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- The profile's source FK, found by lookup (its name was generated when 0079 swapped it). Django's
-- render settles the constraint first (`SET CONSTRAINTS … IMMEDIATE`) and then drops it; the same.
SET CONSTRAINTS ALL IMMEDIATE;
DO $$
DECLARE names text[];
BEGIN
  SELECT array_agg(con.conname) INTO names FROM pg_constraint con
    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
   WHERE con.contype = 'f' AND con.conrelid = 'public.api_student_profiles'::regclass
     AND att.attname = 'source_id';
  IF coalesce(array_length(names, 1), 0) <> 1 THEN
    RAISE EXCEPTION 'api_student_profiles.source_id: expected exactly one FK, found %', names;
  END IF;
  EXECUTE format('ALTER TABLE public.api_student_profiles DROP CONSTRAINT %I', names[1]);
END $$;

-- Plain DROP COLUMN, deliberately not Django's rendered `CASCADE`: if anything else depends on a
-- column (a view, a policy), the drop must REFUSE and be looked at. Its index goes with it.
ALTER TABLE "api_student_profiles" DROP COLUMN "source_id";
ALTER TABLE "partner_organisations" DROP COLUMN "show_in_apply";

INSERT INTO django_migrations (app, name, applied)
  VALUES ('courses', '0082_drop_retired_source_columns', now());
COMMIT;

-- Post-checks (read-only).
BEGIN READ ONLY;
SELECT table_name, column_name FROM information_schema.columns
 WHERE (table_name = 'api_student_profiles' AND column_name = 'source_id')
    OR (table_name = 'partner_organisations' AND column_name = 'show_in_apply');   -- expect: 0 rows
SELECT count(*) FROM public.student_profile_source_backup_sources_d;              -- = check 7's P
SELECT count(*) FILTER (WHERE show_in_apply) FROM public.partner_org_show_in_apply_backup_sources_d; -- = Q
SELECT name FROM django_migrations WHERE app = 'courses' ORDER BY name DESC LIMIT 1;  -- 0082_…
COMMIT;
```

Then run the Supabase Security Advisor (two new tables: 0 errors expected — RLS is on and each has
its policy) and watch for 5xx for an hour.

## Rollback

**Before the deploy** (only 0081 applied; the old image serving). The UPDATE is a data restore; the
ledger row is a DELETE, so the block is the owner's:

```sql
-- OWNER RUNS IN SUPABASE SQL EDITOR (it deletes a ledger row).
BEGIN;
UPDATE partner_organisations SET is_active = true WHERE id IN (<<the ids printed by the cutover>>);
UPDATE api_student_profiles p SET referral_source = b.old_chip
  FROM public.referral_chip_backup_20261019 b WHERE b.supabase_user_id = p.supabase_user_id;
ALTER TABLE "partner_organisations" ALTER COLUMN "show_in_apply" DROP DEFAULT;
DELETE FROM django_migrations WHERE app = 'courses' AND name = '0081_retire_old_source_rows';
COMMIT;
```
(Leaving 0081 in place under the old image is harmless — it never reads the retired rows, and the
default changes nothing for it — so usually no rollback is needed at all.)

**After the deploy, before the drop:** shift Cloud Run traffic back to the previous revision (no
build). Both columns still exist, so the old image works.

**After the drop:** a pre-Sprint-D image cannot serve until the columns are back:
```sql
-- OWNER RUNS IN SUPABASE SQL EDITOR.
BEGIN;
ALTER TABLE api_student_profiles ADD COLUMN source_id bigint NULL
  REFERENCES referral_sources(id) DEFERRABLE INITIALLY DEFERRED;
UPDATE api_student_profiles p SET source_id = b.source_id
  FROM public.student_profile_source_backup_sources_d b WHERE b.supabase_user_id = p.supabase_user_id;
ALTER TABLE partner_organisations ADD COLUMN show_in_apply boolean NOT NULL DEFAULT false;
UPDATE partner_organisations o SET show_in_apply = b.show_in_apply
  FROM public.partner_org_show_in_apply_backup_sources_d b WHERE b.partner_organisation_id = o.id;
DELETE FROM django_migrations WHERE app = 'courses' AND name = '0082_drop_retired_source_columns';
COMMIT;
```
then shift traffic. (Profiles that submitted a bursary application between the deploy and the drop
have no `source_id` in the backup — nothing reads it, so nothing is lost.)
