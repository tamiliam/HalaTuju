"""Owner ruling D16 (2026-10-27): whether a gift asks for STPM-level (higher) results is a PER-GIFT
setting — `scholarship_programmes.asks_higher_results`. BrightPath flagship (`brightpath-flagship`,
cohort b40-2026) is a POST-SPM programme and is switched OFF; BrightPath Sabah (`bpb-sabah-2026`)
and every other gift stay ON. The one reader is `results_route.gift_asks_higher`.

ADDITIVE: one plain ADD COLUMN, boolean NOT NULL with DEFAULT true KEPT IN THE DATABASE
(`db_default`, so no `DROP DEFAULT` follows). Postgres fills existing rows from the default without
rewriting the table, so EVERY EXISTING GIFT READS ON — exactly today's behaviour — until the data
step below switches the flagship off. No index, no new table (so no RLS step).

MIGRATE-FIRST, BY HAND, before the push (scholarship ledger 0178 -> 0179). `sqlmigrate` renders for
the LOCAL backend (SQLite), so this is the Postgres DDL to run, verbatim (the same shape as 0177's,
rendered by Django's postgresql schema editor), WITH THE DATA STEP AND the ledger row in the SAME
transaction:

    BEGIN;
    ALTER TABLE "scholarship_programmes" ADD COLUMN "asks_higher_results" boolean DEFAULT true NOT NULL;
    UPDATE "scholarship_programmes" SET "asks_higher_results" = false WHERE "code" = 'brightpath-flagship';
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0179_programme_asks_higher_results', now());
    COMMIT;

(The UPDATE must touch exactly 1 row; `RunPython` below does the same on any database migrated by
Django — a test database has no such gift, so it changes nothing there. Reverse: nothing to undo,
the column's removal takes the value with it.)

SUBMITTED APPLICATIONS ARE NOT REWRITTEN: their frozen `requirements_snapshot` stays exactly as it
was (D16). Only the LIVE requirement of unsubmitted flagship applications and the `higher_owed`
display / cap / ask of submitted ones read the new value.

BETWEEN MIGRATE AND DEPLOY the image already serving never reads this column, and its gift create
(which does not name it) still inserts because the default lives in the database. Deploying BEFORE
migrating is not safe: every read of a gift would 500 on the missing column.
"""
from django.db import migrations, models

FLAGSHIP = 'brightpath-flagship'


def flagship_is_post_spm(apps, schema_editor):
    Programme = apps.get_model('scholarship', 'Programme')
    Programme.objects.filter(code=FLAGSHIP).update(asks_higher_results=False)


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0178_higher_results'),
    ]

    operations = [
        migrations.AddField(
            model_name='programme',
            name='asks_higher_results',
            field=models.BooleanField(db_default=True, default=True, help_text='Students holding STPM, Matriculation, Asasi or Diploma results are asked to upload them (third results route). Off: this gift asks for the SPM slip only.', verbose_name='Ask for STPM-level results'),
        ),
        migrations.RunPython(flagship_is_post_spm, migrations.RunPython.noop),
    ]
