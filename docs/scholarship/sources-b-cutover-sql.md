# Sources become their own table (sources and referral partners, Sprint B) — prod cutover SQL

**Migrations:**
- MIGRATE-FIRST (before the push, ONE transaction): `scholarship/0173_referral_sources` and
  `courses/0079_student_source_to_referral_sources` — two ledger rows.
- IMAGE-FIRST (only AFTER the new revision serves; its own transaction): `courses/0080_drop_partner_organisation_programme`
  (TD-379) — one ledger row. See **After the deploy — the TD-379 drop** at the end.

Ledgers before: courses ends at `0078`, scholarship at `0172` (lead, 2026-10-18). If another session
has taken 0173 / 0079 / 0080 on `main` by the time this is applied, the sprint renumbers on rebase and
this file's ledger rows change with it — never apply a number that is not settled.

**Status:** written 2026-10-18 by the sprint; NOT applied. The lead applies it to production
(Supabase `pbrrlyoyyiftckqvzvvo`) after re-running every pre-check and telling the owner of any
count that differs from the expected one BEFORE applying (lessons.md 2026-10-09).

## What it does (owner's model, settled 2026-10-09)

Organisations (tenants) > Sources (each owned by the organisation that added it) — and Referral
partners, a platform category owned by no organisation.

1. New table `referral_sources`, owned by an organisation (`organisation_id` → `partner_organisations`).
   RLS on + one `service_role` policy.
2. Every `partner_organisations` row that is a SOURCE — not a tenant, not carrying a fixed form code
   (`halatuju`, `social`, `other`) — is COPIED into it **keeping its id**, owned by THE tenant
   (production: `brightpath`, the only one). Nothing is deleted from `partner_organisations`.
3. Five foreign keys move from `partner_organisations` to `referral_sources` by a **constraint swap**
   (the column, its name and every value stay): `programme_referral_sources.source_id`,
   `api_student_profiles.source_id`, `scholarship_applications.witness_org_id`,
   `bursary_agreements.witness_org_id`, `partner_email_log.organisation_id`.
4. CUMIG is BOTH: its REFERRAL PARTNER row stays on `partner_organisations` — unowned, `is_referral_partner`,
   its two `partner` logins, its `?ref=cumig` link, the 254 students `referred_by_org` names — and its
   SOURCE row is the copy (same id, same code), owned by BrightPath. Nothing here touches
   `referred_by_org`, `is_referral_partner`, `partner_admins` or any chip.
5. The new id sequence starts past the highest id of EITHER table, so a source created after the
   cutover never takes an id that some `partner_organisations` row already has.

`invitations.organisation_id` does NOT move: it names the TENANT for every staff invitation, and no
code has ever written a `source_partner` invitation (pre-check 8 asserts there are none). The column
a source invitation will need is that feature's own decision.

The DDL was rendered OFFLINE from the migrations with Django's postgresql schema editor (no
connection; a dev box's `sqlmigrate` renders SQLite). Two departures, both deliberate:
- The old FK's NAME cannot be known offline, so each drop is a lookup in `pg_constraint` that
  asserts exactly ONE foreign key from that column to `partner_organisations` and drops it.
- Django emits the new table's own FK and index at the END; here they come straight after
  `CREATE TABLE` (the table is empty then), and `SET CONSTRAINTS ALL IMMEDIATE` follows the seed —
  otherwise the seed's pending deferred-FK events on `referral_sources` refuse every later
  `ADD CONSTRAINT … REFERENCES referral_sources` (the 0163 rule).

## Pre-checks (read-only — run first, write the answers into the cutover note)

```sql
BEGIN READ ONLY;

-- 1. Ledgers: courses ends at 0078, scholarship at 0172; none of 0173 / 0079 / 0080 is recorded.
SELECT app, name FROM django_migrations
 WHERE app IN ('courses', 'scholarship') ORDER BY app, name DESC LIMIT 6;

-- 2. The new table does not exist yet.                                         expect: NULL
SELECT to_regclass('public.referral_sources');

-- 3. TENANTS (`PartnerOrganisation.objects.tenants()`: owns an ACTIVE programme, or has an ACTIVE
--    org_admin).                                                              expect: brightpath, alone
SELECT o.id, o.code FROM partner_organisations o
 WHERE EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
    OR EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                AND a.role = 'org_admin' AND a.is_active);

-- 4. The rows that will be COPIED (C = the row count).                 expect (2026-10-18 reading):
--    cumig, ewrf, hss, hyo, mhm, learnifi, muet, pacos, pptm, rckk, smc (+ switched-off sathya_sai,
--    tara) → C = 13. RE-READ: the list grows. cumig is the only one with is_referral_partner = t.
SELECT s.id, s.code, s.show_in_apply, s.is_active, s.is_referral_partner,
       (s.contact_email <> '') AS has_email
  FROM partner_organisations s
 WHERE s.code NOT IN ('halatuju', 'social', 'other')
   AND NOT EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = s.id AND p.is_active)
   AND NOT EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = s.id
                    AND a.role = 'org_admin' AND a.is_active)
 ORDER BY s.code;

-- 5. ⚠ ASSERTED — EVERY ROW MUST READ 0. A value in any of the five columns that names a row NOT
--    in the copy (a tenant such as brightpath, or a fixed-code row) would make the constraint swap
--    fail. If any is not 0: STOP and take the list to the owner — a witness on the house or a
--    tenant row is her question; nothing is cleared silently.
WITH copy AS (
  SELECT s.id FROM partner_organisations s
   WHERE s.code NOT IN ('halatuju', 'social', 'other')
     AND NOT EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = s.id AND p.is_active)
     AND NOT EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = s.id
                      AND a.role = 'org_admin' AND a.is_active))
SELECT 'programme_referral_sources.source_id' AS col, count(*) FROM programme_referral_sources
 WHERE source_id NOT IN (SELECT id FROM copy)
UNION ALL SELECT 'api_student_profiles.source_id', count(*) FROM api_student_profiles
 WHERE source_id IS NOT NULL AND source_id NOT IN (SELECT id FROM copy)
UNION ALL SELECT 'scholarship_applications.witness_org_id', count(*) FROM scholarship_applications
 WHERE witness_org_id IS NOT NULL AND witness_org_id NOT IN (SELECT id FROM copy)
UNION ALL SELECT 'bursary_agreements.witness_org_id', count(*) FROM bursary_agreements
 WHERE witness_org_id IS NOT NULL AND witness_org_id NOT IN (SELECT id FROM copy)
UNION ALL SELECT 'partner_email_log.organisation_id', count(*) FROM partner_email_log
 WHERE organisation_id NOT IN (SELECT id FROM copy);
-- expect: 0 on all five lines.

-- 6. The rows each column names today (the post-checks compare with these).
SELECT (SELECT count(*) FROM programme_referral_sources)                          AS links,        -- L
       (SELECT count(*) FROM api_student_profiles WHERE source_id IS NOT NULL)    AS sources_set,  -- 122
       (SELECT count(*) FROM scholarship_applications WHERE witness_org_id IS NOT NULL) AS app_witness,  -- W1
       (SELECT count(*) FROM bursary_agreements WHERE witness_org_id IS NOT NULL) AS agreement_witness, -- W2
       (SELECT count(*) FROM partner_email_log)                                   AS email_log;    -- E

-- 7. PARTNER EMAIL RECIPIENTS TODAY (`partner_comms.qualifying_partners`: active, an address, not
--    the house). Write the list down: post-check 4 must return the SAME (code, address) pairs.
SELECT o.code, lower(trim(o.contact_email)) AS recipient FROM partner_organisations o
 WHERE o.is_active AND o.code <> 'brightpath' AND o.contact_email <> '' ORDER BY o.name;
-- Every row here must also be in pre-check 4 (a source). A tenant here would be a recipient lost.

-- 8. Source invitations (nothing has ever written one).                        expect: 0
SELECT count(*) FROM invitations WHERE audience = 'source_partner';

-- 9. Applications the fenced partner emails / counts can see: every application must carry the
--    tenant as its owner, or it drops out of its source's figures.               expect: 0 and 0
SELECT count(*) FILTER (WHERE owning_organisation_id IS NULL) AS no_owner,
       count(*) FILTER (WHERE owning_organisation_id IS DISTINCT FROM
                        (SELECT id FROM partner_organisations WHERE code = 'brightpath')) AS other_owner
  FROM scholarship_applications;

-- 10. The referral partner, untouched by all of this.        expect: cumig | t | 2 logins | 254 students
SELECT o.code, o.is_referral_partner,
       (SELECT count(*) FROM partner_admins a WHERE a.org_id = o.id AND a.role = 'partner') AS logins,
       (SELECT count(*) FROM api_student_profiles p WHERE p.referred_by_org_id = o.id) AS students
  FROM partner_organisations o WHERE o.is_referral_partner;

-- 11. The ids the sequence must pass.
SELECT max(id) AS max_partner_org_id FROM partner_organisations;
COMMIT;
```

## The cutover — ONE transaction (migrate-first, BEFORE the push)

Edit the ONE literal marked `<<C>>` to the row count of pre-check 4 before running.

```sql
BEGIN;

-- A. The table, its owner FK and index (rendered offline; FK + index moved up — the table is empty).
CREATE TABLE "referral_sources" ("id" bigint NOT NULL PRIMARY KEY GENERATED BY DEFAULT AS IDENTITY, "code" varchar(50) NOT NULL, "name" varchar(200) NOT NULL, "contact_person" varchar(200) NOT NULL, "contact_email" varchar(254) NOT NULL, "phone" varchar(30) NOT NULL, "show_in_apply" boolean NOT NULL, "is_active" boolean NOT NULL, "created_at" timestamp with time zone NOT NULL, "organisation_id" bigint NOT NULL, CONSTRAINT "uniq_referral_source_org_code" UNIQUE ("organisation_id", "code"));
ALTER TABLE "referral_sources" ADD CONSTRAINT "referral_sources_organisation_id_17ea5748_fk_partner_o" FOREIGN KEY ("organisation_id") REFERENCES "partner_organisations" ("id") DEFERRABLE INITIALLY DEFERRED;
CREATE INDEX "referral_sources_organisation_id_17ea5748" ON "referral_sources" ("organisation_id");
-- RLS: the event trigger switches it on but adds no policy; scholarship tables are deny-all to the
-- public key and every read and write goes through Django (service_role).
ALTER TABLE public.referral_sources ENABLE ROW LEVEL SECURITY;
CREATE POLICY referral_sources_service_role ON public.referral_sources
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- B. Exactly one tenant, or nothing is copied (the migration refuses the same way).
DO $$
BEGIN
  IF (SELECT count(*) FROM partner_organisations o
       WHERE EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
          OR EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                      AND a.role = 'org_admin' AND a.is_active)) <> 1 THEN
    RAISE EXCEPTION 'not exactly one tenant: whose is each source? stop and ask the owner';
  END IF;
END $$;

-- C. The copy, KEEPING EVERY ID, owned by the tenant.                         expect: INSERT 0 C
INSERT INTO referral_sources (id, organisation_id, code, name, contact_person, contact_email, phone,
                              show_in_apply, is_active, created_at)
SELECT s.id, t.id, s.code, s.name, s.contact_person, s.contact_email, s.phone,
       s.show_in_apply, s.is_active, s.created_at
  FROM partner_organisations s
 CROSS JOIN (SELECT o.id FROM partner_organisations o
              WHERE EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = o.id AND p.is_active)
                 OR EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = o.id
                             AND a.role = 'org_admin' AND a.is_active)) t
 WHERE s.code NOT IN ('halatuju', 'social', 'other')
   AND NOT EXISTS (SELECT 1 FROM scholarship_programmes p WHERE p.organisation_id = s.id AND p.is_active)
   AND NOT EXISTS (SELECT 1 FROM partner_admins a WHERE a.owning_organisation_id = s.id
                    AND a.role = 'org_admin' AND a.is_active);

-- Settle the seed's deferred FK checks NOW: the constraint swaps below add triggers on this table.
SET CONSTRAINTS ALL IMMEDIATE;

-- The sequence: past the highest id of EITHER table.
SELECT setval(pg_get_serial_sequence('referral_sources', 'id'),
              GREATEST((SELECT max(id) FROM referral_sources), (SELECT max(id) FROM partner_organisations)));

-- D. Assert the copy and that nothing dangles (pre-check 5 again, inside the transaction).
DO $$
DECLARE bad bigint;
BEGIN
  IF (SELECT count(*) FROM referral_sources) <> <<C>> THEN
    RAISE EXCEPTION 'copied % rows, expected <<C>>', (SELECT count(*) FROM referral_sources);
  END IF;
  IF EXISTS (SELECT 1 FROM referral_sources r JOIN partner_organisations o ON o.id = r.id
              WHERE o.code <> r.code) THEN
    RAISE EXCEPTION 'an id was not kept with its code';
  END IF;
  SELECT (SELECT count(*) FROM programme_referral_sources WHERE source_id NOT IN (SELECT id FROM referral_sources))
       + (SELECT count(*) FROM api_student_profiles WHERE source_id IS NOT NULL
                                                     AND source_id NOT IN (SELECT id FROM referral_sources))
       + (SELECT count(*) FROM scholarship_applications WHERE witness_org_id IS NOT NULL
                                                         AND witness_org_id NOT IN (SELECT id FROM referral_sources))
       + (SELECT count(*) FROM bursary_agreements WHERE witness_org_id IS NOT NULL
                                                   AND witness_org_id NOT IN (SELECT id FROM referral_sources))
       + (SELECT count(*) FROM partner_email_log WHERE organisation_id NOT IN (SELECT id FROM referral_sources))
    INTO bad;
  IF bad <> 0 THEN
    RAISE EXCEPTION '% reference(s) name a row that is not a source: stop and ask the owner', bad;
  END IF;
END $$;

-- E. The constraint swaps. Each old FK is found by lookup (its name is not knowable offline) and
--    there must be EXACTLY ONE per column, pointing at partner_organisations.
DO $$
DECLARE
  t text; c text; names text[];
BEGIN
  FOR t, c IN VALUES ('programme_referral_sources', 'source_id'),
                     ('api_student_profiles', 'source_id'),
                     ('scholarship_applications', 'witness_org_id'),
                     ('bursary_agreements', 'witness_org_id'),
                     ('partner_email_log', 'organisation_id')
  LOOP
    SELECT array_agg(con.conname) INTO names
      FROM pg_constraint con
      JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
     WHERE con.contype = 'f' AND con.conrelid = ('public.' || t)::regclass
       AND con.confrelid = 'public.partner_organisations'::regclass
       AND att.attname = c AND array_length(con.conkey, 1) = 1;
    IF coalesce(array_length(names, 1), 0) <> 1 THEN
      RAISE EXCEPTION '%.%: expected exactly one FK to partner_organisations, found %', t, c, names;
    END IF;
    EXECUTE format('ALTER TABLE public.%I DROP CONSTRAINT %I', t, names[1]);
  END LOOP;
END $$;
-- (rendered offline, verbatim)
ALTER TABLE "programme_referral_sources" ADD CONSTRAINT "programme_referral_s_source_id_9ef1bb6b_fk_referral_" FOREIGN KEY ("source_id") REFERENCES "referral_sources" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "scholarship_applications" ADD CONSTRAINT "scholarship_applicat_witness_org_id_8e19d72b_fk_referral_" FOREIGN KEY ("witness_org_id") REFERENCES "referral_sources" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "bursary_agreements" ADD CONSTRAINT "bursary_agreements_witness_org_id_bd4d6192_fk_referral_" FOREIGN KEY ("witness_org_id") REFERENCES "referral_sources" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "partner_email_log" ADD CONSTRAINT "partner_email_log_organisation_id_d5194faa_fk_referral_" FOREIGN KEY ("organisation_id") REFERENCES "referral_sources" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "api_student_profiles" ADD CONSTRAINT "api_student_profiles_source_id_015accbd_fk_referral_sources_id" FOREIGN KEY ("source_id") REFERENCES "referral_sources" ("id") DEFERRABLE INITIALLY DEFERRED;

-- F. The ledger: TWO rows (0080 is NOT recorded here — it is applied after the deploy).
INSERT INTO django_migrations (app, name, applied) VALUES
  ('scholarship', '0173_referral_sources', now()),
  ('courses', '0079_student_source_to_referral_sources', now());

-- Any count different from the pre-checks: ROLLBACK and look before going on.
COMMIT;
```

`ADD CONSTRAINT … FOREIGN KEY` checks every existing row when it is added (a DEFERRABLE constraint
defers only later writes), so a dangling value refuses the transaction even if step D were skipped.

## Post-checks (read-only)

```sql
BEGIN READ ONLY;
-- 1. The copy: C rows, every one owned by the tenant, every id kept with its code.   expect: C | 1 | 0
SELECT count(*) AS copied, count(DISTINCT organisation_id) AS owners,
       count(*) FILTER (WHERE NOT EXISTS (SELECT 1 FROM partner_organisations o
                                          WHERE o.id = r.id AND o.code = r.code)) AS id_mismatches
  FROM referral_sources r;
-- 2. Every swapped FK now names referral_sources, and none still names partner_organisations.
SELECT conrelid::regclass AS tbl, conname, confrelid::regclass AS target FROM pg_constraint
 WHERE contype = 'f' AND conrelid::regclass::text IN ('programme_referral_sources',
       'api_student_profiles', 'scholarship_applications', 'bursary_agreements', 'partner_email_log')
   AND confrelid::regclass::text IN ('partner_organisations', 'referral_sources')
 ORDER BY 1;
-- expect: the five new `…_fk_referral_…` constraints → referral_sources, plus
--         api_student_profiles' referred_by_org FK → partner_organisations (UNCHANGED — the referral
--         partner's column). Nothing else to partner_organisations from these five columns.
-- 3. Pre-check 6 again: L | 122 | W1 | W2 | E — identical (a swap rewrites no value).
-- 4. PARTNER EMAIL RECIPIENTS AFTER — the SAME (code, address) pairs as pre-check 7:
SELECT r.code, lower(trim(r.contact_email)) AS recipient FROM referral_sources r
 WHERE r.is_active AND r.code <> 'brightpath' AND r.contact_email <> '' ORDER BY r.name;
-- 5. The referral partner untouched (pre-check 10): cumig | t | 2 | 254.
-- 6. The sequence is past both tables.                    expect: last_value >= max_partner_org_id
SELECT last_value FROM pg_sequences WHERE schemaname = 'public'
   AND sequencename = split_part(pg_get_serial_sequence('referral_sources', 'id'), '.', 2);
-- 7. RLS on and one service_role policy.                                  expect: t | referral_sources_service_role
SELECT relrowsecurity FROM pg_class WHERE relname = 'referral_sources';
SELECT policyname, roles FROM pg_policies WHERE tablename = 'referral_sources';
-- 8. Ledger: scholarship …0173_referral_sources, courses …0079_student_source_to_referral_sources.
SELECT app, name FROM django_migrations WHERE app IN ('courses', 'scholarship')
 ORDER BY applied DESC LIMIT 3;
COMMIT;
```

Then run the Supabase Security Advisor (0 errors before the push), and diff the ledger against the
migration files: the ONE expected gap is `courses/0080`, applied after the deploy (below).

## Order — migrate FIRST, then deploy, then the drop

- **Deploying before this is applied 500s** every source surface (the new image selects
  `referral_sources`, which would not exist).
- **Applying it first is safe for the image already serving.** The old image reads sources from
  `partner_organisations`; every row it reads is still there with the same id, and every value in
  the five swapped columns names a row that exists in BOTH tables.

## Deploy window (accepted — with a freeze)

Between COMMIT and the new revision serving, the OLD image keeps writing to `partner_organisations`:
- **Sources POST** would create a source the new table never hears of; a **Sources PATCH** would edit
  a row the new image no longer reads. **Freeze both** (and gift Configuration's source switches,
  which would fail for a row created in the window) until `status.latestReadyRevisionName` is the
  new revision. Tell the owner and the BrightPath admins before the cutover.
- **Witness assignment** on the old image to a tenant (the house row is in the old Sources list) now
  fails the new FK and answers 500 — refused, as the new image refuses it with a 400. Nothing written.
- **The bursary submit** writes `source_id` = an offered source's id: every offered source is copied,
  so it keeps working. **Partner emails** log against copied ids: they keep working.

After the deploy, two read-only checks of the window:

```sql
BEGIN READ ONLY;
-- A. Rows created in partner_organisations since the cutover that are not tenants or referral
--    partners: a Sources POST from the old image.                                  expect: 0 rows
SELECT o.id, o.code, o.created_at FROM partner_organisations o
 WHERE o.created_at >= (SELECT applied FROM django_migrations
                         WHERE app = 'scholarship' AND name = '0173_referral_sources')
   AND NOT o.is_referral_partner
   AND o.id NOT IN (SELECT id FROM referral_sources);
-- B. A copied source edited on the old image since the cutover: its two rows now differ.  expect: 0
SELECT o.code FROM referral_sources r JOIN partner_organisations o ON o.id = r.id
 WHERE (o.name, o.contact_person, o.contact_email, o.phone, o.show_in_apply, o.is_active)
       IS DISTINCT FROM (r.name, r.contact_person, r.contact_email, r.phone, r.show_in_apply, r.is_active);
COMMIT;
```

Any row in A or B goes to the owner: copying it into `referral_sources` (A) or carrying the edit
across (B) is a reviewed `INSERT`/`UPDATE`, never automatic. ⚠ Read B soon after the deploy: from
then on a `cumig` difference is EXPECTED and correct — its two `partner` logins edit their own
contact person and phone (`/admin/profile/`) on the referral-partner row, while the partner emails
read the source row. The two CUMIGs' contact details are separate from this sprint on (roadmap
Sprint C item 5).

## Rollback

**Before the deploy** (the old image reads only `partner_organisations`):

```sql
BEGIN;
ALTER TABLE "programme_referral_sources" DROP CONSTRAINT "programme_referral_s_source_id_9ef1bb6b_fk_referral_";
ALTER TABLE "scholarship_applications" DROP CONSTRAINT "scholarship_applicat_witness_org_id_8e19d72b_fk_referral_";
ALTER TABLE "bursary_agreements" DROP CONSTRAINT "bursary_agreements_witness_org_id_bd4d6192_fk_referral_";
ALTER TABLE "partner_email_log" DROP CONSTRAINT "partner_email_log_organisation_id_d5194faa_fk_referral_";
ALTER TABLE "api_student_profiles" DROP CONSTRAINT "api_student_profiles_source_id_015accbd_fk_referral_sources_id";
ALTER TABLE "programme_referral_sources" ADD CONSTRAINT "programme_referral_sources_source_id_fk_partner_o_rb" FOREIGN KEY ("source_id") REFERENCES "partner_organisations" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "scholarship_applications" ADD CONSTRAINT "scholarship_applications_witness_org_id_fk_partner_o_rb" FOREIGN KEY ("witness_org_id") REFERENCES "partner_organisations" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "bursary_agreements" ADD CONSTRAINT "bursary_agreements_witness_org_id_fk_partner_o_rb" FOREIGN KEY ("witness_org_id") REFERENCES "partner_organisations" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "partner_email_log" ADD CONSTRAINT "partner_email_log_organisation_id_fk_partner_o_rb" FOREIGN KEY ("organisation_id") REFERENCES "partner_organisations" ("id") DEFERRABLE INITIALLY DEFERRED;
ALTER TABLE "api_student_profiles" ADD CONSTRAINT "api_student_profiles_source_id_fk_partner_o_rb" FOREIGN KEY ("source_id") REFERENCES "partner_organisations" ("id") DEFERRABLE INITIALLY DEFERRED;
DROP TABLE public.referral_sources;
DELETE FROM django_migrations
 WHERE (app, name) IN (('scholarship', '0173_referral_sources'),
                       ('courses', '0079_student_source_to_referral_sources'));
COMMIT;
```

**After the deploy** the new image reads `referral_sources` on every source surface: roll the
service back to the previous revision FIRST. ⚠ A source created by the new image exists only in
`referral_sources`, with an id above every `partner_organisations` id, and the re-added FKs would
refuse any link, profile, witness or log row naming it. List them first —
`SELECT id, code FROM referral_sources WHERE id NOT IN (SELECT id FROM partner_organisations);` —
and copy each into `partner_organisations` with the same id (a reviewed `INSERT`, then
`setval` that table's sequence past it) before the rollback above. Once courses 0080 has run, a
pre-Sprint-B image cannot serve at all (it selects `programme_id`): there is no rollback past it.

## After the deploy — the TD-379 drop (`courses/0080`, IMAGE-FIRST)

Run ONLY when `status.latestReadyRevisionName` is the Sprint B revision and no older revision
carries traffic (a pre-Sprint-B image selects `programme_id` on every organisation read; dropping it
under one 500s the site). Its own transaction, its own ledger row.

```sql
BEGIN READ ONLY;
-- Pre-check: nothing to lose that was not already carried into the per-gift links (0172 seeded
-- programme_referral_sources from this column on 2026-10-09).                   informational
SELECT o.code, o.programme_id FROM partner_organisations o WHERE o.programme_id IS NOT NULL;
COMMIT;

BEGIN;
-- Keep what the column said, restorable, before it goes.
CREATE TABLE public.partner_org_programme_backup_td379 AS
SELECT id AS partner_organisation_id, programme_id, now() AS backed_up_at
  FROM partner_organisations WHERE programme_id IS NOT NULL;
ALTER TABLE public.partner_org_programme_backup_td379 ENABLE ROW LEVEL SECURITY;
CREATE POLICY partner_org_programme_backup_td379_service_role ON public.partner_org_programme_backup_td379
  FOR ALL TO service_role USING (true) WITH CHECK (true);

-- The drop (rendered offline: Django drops the FK by name, then the column; the column drop takes
-- its FK and index with it, so the FK step is the same lookup as above).
DO $$
DECLARE names text[];
BEGIN
  SELECT array_agg(con.conname) INTO names FROM pg_constraint con
    JOIN pg_attribute att ON att.attrelid = con.conrelid AND att.attnum = ANY (con.conkey)
   WHERE con.contype = 'f' AND con.conrelid = 'public.partner_organisations'::regclass
     AND att.attname = 'programme_id';
  IF coalesce(array_length(names, 1), 0) <> 1 THEN
    RAISE EXCEPTION 'partner_organisations.programme_id: expected exactly one FK, found %', names;
  END IF;
  EXECUTE format('ALTER TABLE public.partner_organisations DROP CONSTRAINT %I', names[1]);
END $$;
ALTER TABLE "partner_organisations" DROP COLUMN "programme_id" CASCADE;

INSERT INTO django_migrations (app, name, applied)
  VALUES ('courses', '0080_drop_partner_organisation_programme', now());
COMMIT;

BEGIN READ ONLY;
SELECT column_name FROM information_schema.columns
 WHERE table_name = 'partner_organisations' AND column_name = 'programme_id';     -- expect: 0 rows
SELECT name FROM django_migrations WHERE app = 'courses' ORDER BY name DESC LIMIT 1;  -- 0080_…
COMMIT;
```

Rollback of the drop (only with the Sprint B image serving — it never names the column):
`ALTER TABLE partner_organisations ADD COLUMN programme_id bigint NULL REFERENCES scholarship_programmes(id) DEFERRABLE INITIALLY DEFERRED;`
then restore from `partner_org_programme_backup_td379` and delete the 0080 ledger row. Close TD-379
in the register (with this evidence) once the drop has run.
