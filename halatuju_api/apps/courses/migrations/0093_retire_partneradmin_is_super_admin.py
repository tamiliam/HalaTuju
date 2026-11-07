"""A1.10b / TD-064 (2026-11-07): retire `PartnerAdmin.is_super_admin`. `role` is the only super marker.

Expand-contract, contract half, in TWO steps so that no moment of the deploy breaks:

- this migration (STEP 1, migrate-first, before the push):
  - the two CHECKs that named the flag are re-made WITHOUT it, names kept:
    `partner_admin_source_iff_source_partner` and `partner_admin_mentor_iff_mentor`. Both are pure
    RELAXATIONS: the flag term was already implied by the role term (a `source_partner` row, or a
    row in `MENTOR_LINK_ROLES`, is never role `super`), so every row the old checks accepted, the
    new ones accept — the image still serving keeps writing rows that pass;
  - the column gets a DATABASE default `false` (prod already has it: checked 2026-11-07, so this is
    a no-op there; a fresh database built from the migrations needs it). The new code no longer
    names the column in an INSERT, so without the default its NOT NULL would refuse every new
    staff row while the column still exists;
  - the field leaves Django's STATE only (SeparateDatabaseAndState): the column stays in the
    database, because the OLD image (still serving while the new one builds, and the rollback
    target) selects it on every PartnerAdmin read.
- DROP COLUMN (STEP 2, by hand, AFTER the new image is live and serving 100% of traffic, and only
  once nobody would roll back to an image older than this one) — below. No migration file carries it.

Pre-check (read-only). Expect 0, 0: no row holds the flag without the role or the role without the
flag (2026-11-07: 1 super, flag true; 46 others, flag false), so reading the role alone changes
nobody's access:

    SELECT count(*) FROM partner_admins WHERE is_super_admin AND role <> 'super';
    SELECT count(*) FROM partner_admins WHERE NOT is_super_admin AND role = 'super';

No RLS policy, function, view, trigger or edge function reads the column (checked 2026-11-07); its
only dependants are the two CHECKs and its default.

STEP 1 — before the push (courses ledger 0092 -> 0093):

Rendered offline with Django's postgresql schema editor from this migration, verbatim:

    BEGIN;
    ALTER TABLE "partner_admins" DROP CONSTRAINT "partner_admin_source_iff_source_partner";
    ALTER TABLE "partner_admins" DROP CONSTRAINT "partner_admin_mentor_iff_mentor";
    ALTER TABLE "partner_admins" ADD CONSTRAINT "partner_admin_source_iff_source_partner" CHECK ((("role" = 'source_partner' AND "source_id" IS NOT NULL) OR (NOT ("role" = 'source_partner') AND "source_id" IS NULL)));
    ALTER TABLE "partner_admins" ADD CONSTRAINT "partner_admin_mentor_iff_mentor" CHECK (((NOT ("role" = 'mentor') AND "mentor_id" IS NULL) OR ("mentor_id" IS NOT NULL AND "role" IN ('mentor', 'org_admin', 'admin', 'reviewer', 'qc', 'finance'))));
    ALTER TABLE "partner_admins" ALTER COLUMN "is_super_admin" SET DEFAULT false;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0093_retire_partneradmin_is_super_admin', now());
    COMMIT;

BETWEEN STEP 1 AND STEP 2 both images work: the old one writes the flag in lockstep with the role and
reads it; the new one leaves it to the default (false) and reads the role. ⚠ In that window a row the
NEW image demotes from `super` keeps flag true, and the OLD image would still read it as a super — so
do not demote a super until STEP 2 is done (there is one super, the owner).

STEP 2 — after the new image is live (check `SELECT count(*) FROM pg_constraint WHERE conrelid =
'partner_admins'::regclass AND pg_get_constraintdef(oid) ILIKE '%is_super_admin%'` is 0 first; DROP
COLUMN would otherwise silently drop a CHECK that still names it):

    ALTER TABLE "partner_admins" DROP COLUMN "is_super_admin";

ROLLBACK of STEP 1 (only before STEP 2; the old checks accept every row the new ones do while every
super still carries the flag):

    BEGIN;
    ALTER TABLE "partner_admins" DROP CONSTRAINT "partner_admin_source_iff_source_partner";
    ALTER TABLE "partner_admins" DROP CONSTRAINT "partner_admin_mentor_iff_mentor";
    ALTER TABLE "partner_admins" ADD CONSTRAINT "partner_admin_source_iff_source_partner" CHECK (((NOT "is_super_admin" AND "role" = 'source_partner' AND "source_id" IS NOT NULL) OR (NOT ("role" = 'source_partner') AND "source_id" IS NULL)));
    ALTER TABLE "partner_admins" ADD CONSTRAINT "partner_admin_mentor_iff_mentor" CHECK (((NOT ("role" = 'mentor') AND "mentor_id" IS NULL) OR (NOT "is_super_admin" AND "mentor_id" IS NOT NULL AND "role" IN ('mentor', 'org_admin', 'admin', 'reviewer', 'qc', 'finance'))));
    DELETE FROM django_migrations WHERE app = 'courses' AND name = '0093_retire_partneradmin_is_super_admin';
    COMMIT;

(The default `false` may stay: the old image always writes the value itself.)
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0092_reviewergift'),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name='partneradmin',
            name='partner_admin_source_iff_source_partner',
        ),
        migrations.RemoveConstraint(
            model_name='partneradmin',
            name='partner_admin_mentor_iff_mentor',
        ),
        migrations.AddConstraint(
            model_name='partneradmin',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(('role', 'source_partner'), ('source__isnull', False)), models.Q(models.Q(('role', 'source_partner'), _negated=True), ('source__isnull', True)), _connector='OR'), name='partner_admin_source_iff_source_partner'),
        ),
        migrations.AddConstraint(
            model_name='partneradmin',
            constraint=models.CheckConstraint(condition=models.Q(models.Q(models.Q(('role', 'mentor'), _negated=True), ('mentor__isnull', True)), models.Q(('mentor__isnull', False), ('role__in', ('mentor', 'org_admin', 'admin', 'reviewer', 'qc', 'finance'))), _connector='OR'), name='partner_admin_mentor_iff_mentor'),
        ),
        # STEP 1's column half: a DB default so the new code's INSERTs (which no longer name the column)
        # pass its NOT NULL, then the field leaves the STATE only. The DROP COLUMN is STEP 2, by hand.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name='partneradmin',
                    name='is_super_admin',
                    field=models.BooleanField(default=False, db_default=False),
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='partneradmin',
                    name='is_super_admin',
                ),
            ],
        ),
    ]
