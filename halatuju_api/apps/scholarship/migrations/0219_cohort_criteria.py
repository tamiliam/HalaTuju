"""Criteria editor Sprint 2 (2026-11-26): `ScholarshipCohort.criteria`, the intake's rules as one
AND/OR tree (`apps.scholarship.criteria`), and the fill from today's columns.

ADDITIVE: one NULLABLE JSON column, then a data step that stores `criteria.from_legacy(cohort)`
(`criteria.build_trees`) on every intake whose `criteria` is NULL (on the `migrate` path, i.e. dev
and test; production uses the hand SQL below and `build_criteria_trees`). NULL KEEPS TODAY'S MEANING:
the gate reads it through `criteria.tree_of`, which builds today's gate from the columns at read time
(`from_legacy(cohort, keep_empty_spm=True)` = `shortlisting.evaluate_columns` exactly), so an intake
the fill has not reached (or one the old image creates between migrate and deploy) decides exactly as
before. It is NOT the tree the fill stores: on the CGPA-trap shape (intake 5: a PNGK floor and no SPM
bar) the stored tree switches the SPM group off (owner ruling 2026-11-25), so intake 5 changes at the
fill, never at the deploy. The requirement columns stay; nothing is dropped.

The fill refuses WHOLE (ValueError naming intake ids and codes, nothing written) if any intake's tree
fails `criteria.validate_tree` (a wrong-case birth state, a start-year list of junk only). Run
`python manage.py replay_criteria` first: it lists such intakes as TREE REFUSED.

⚠ MIGRATE-FIRST, BY HAND, and ONLY WITH THE OWNER'S YES, before the publish (scholarship ledger
0218 -> 0219; 0218 must be applied first). NOBODY RUNS `migrate` AGAINST PRODUCTION.

Pre-check (read-only; expect 1, then 0, then no row):

    SELECT count(*) FROM django_migrations WHERE app = 'scholarship' AND name = '0218_application_verdict_context';
    SELECT count(*) FROM django_migrations WHERE app = 'scholarship' AND name = '0219_cohort_criteria';
    SELECT column_name FROM information_schema.columns
     WHERE table_name = 'scholarship_cohorts' AND column_name = 'criteria';

⚠ HAND-WRITTEN POSTGRES DDL - do NOT paste `sqlmigrate`. A nullable column with no default: no table
rewrite, no db_default needed (the old image never names the column, and NULL is a valid value):

    BEGIN;
    SET LOCAL lock_timeout = '5s';
    ALTER TABLE "scholarship_cohorts" ADD COLUMN "criteria" jsonb NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0219_cohort_criteria', now());
    COMMIT;

The hand SQL leaves every row NULL (= today's columns, read live; no decision moves). The fill is a
SEPARATE, later step with its own yes: `python manage.py build_criteria_trees` (dry run, lists what it
would store) then `--apply` (one transaction). It makes the tree the stored source of truth, and it
is THE step that switches intake 5's CGPA trap off (class b in `replay_criteria`: an SPM-only student
there moves from pass to refused); every other live intake keeps its outcomes.

Post-check: `SELECT count(*) FROM scholarship_cohorts WHERE criteria IS NOT NULL` is 0 after the SQL,
and the number of intakes after the fill.

No RLS step: a column on an existing table inherits that table's policies.

DEPLOYING BEFORE MIGRATING is NOT safe: the new image selects this column on every intake load.

⚠ WHY THE DATABASE STEP IS HAND-WRITTEN SQL, NOT `AddField` (the 0212 / 0218 reason): on SQLite (the
test database) some `AddField`s REBUILD the table from Django's state, and `scholarship_cohorts` keeps
a column the state no longer names (`bucket_b_margin`, TD-226). A plain ADD COLUMN never rebuilds.

ROLLBACK / REVERSIBLE: the data step's reverse is a no-op (the column goes with the schema step). Roll
the IMAGE back FIRST (it reads the column), then:

    BEGIN;
    SET LOCAL lock_timeout = '5s';
    ALTER TABLE "scholarship_cohorts" DROP COLUMN "criteria";
    DELETE FROM django_migrations WHERE app = 'scholarship' AND name = '0219_cohort_criteria';
    COMMIT;

The old image reads only the columns, which this migration never touches, so after a rollback every
intake means exactly what it meant before.
"""

from django.db import migrations, models

_ADD = {
    'postgresql': 'ALTER TABLE "scholarship_cohorts" ADD COLUMN IF NOT EXISTS "criteria" jsonb NULL',
    'sqlite': ('ALTER TABLE "scholarship_cohorts" ADD COLUMN "criteria" text NULL '
               'CHECK ((JSON_VALID("criteria") OR "criteria" IS NULL))'),
}


def _give_up_rather_than_queue(schema_editor):
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("SET LOCAL lock_timeout = '5s'")


def _add_column(apps, schema_editor):
    _give_up_rather_than_queue(schema_editor)
    schema_editor.execute(_ADD[schema_editor.connection.vendor])


def _drop_column(apps, schema_editor):
    _give_up_rather_than_queue(schema_editor)
    schema_editor.execute('ALTER TABLE "scholarship_cohorts" DROP COLUMN "criteria"')


def _fill(apps, schema_editor):
    from apps.scholarship import criteria
    Cohort = apps.get_model('scholarship', 'ScholarshipCohort')

    def save(c, tree):
        Cohort.objects.filter(pk=c.pk, criteria__isnull=True).update(criteria=tree)

    criteria.build_trees(list(Cohort.objects.order_by('id')), save)


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0218_application_verdict_context'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add_column, _drop_column)],
            state_operations=[
                migrations.AddField(
                    model_name='scholarshipcohort',
                    name='criteria',
                    field=models.JSONField(blank=True, default=None, help_text="The intake's criteria tree (results, merit, income, born-in sections; course-start flag). NULL keeps today's meaning: read live from the requirement columns.", null=True),
                ),
            ],
        ),
        migrations.RunPython(_fill, migrations.RunPython.noop),
    ]
