"""H3 (#597, owner 2026-11-15): an intake year can say which course-start YEARS it accepts —
`ScholarshipCohort.allowed_start_years`, read against the offer letter (`start_year.possible_start_years`).

ADDITIVE: one JSON column. Every existing intake year gets an EMPTY list, and empty means the rule
is not applied (the value IS the switch, the 0171 list form), so nobody's verdict changes until an
admin sets the years in the Gift editor's Rules tab. Nothing is backfilled: the Degree round's
2025 / 2026 is set there after release, like every other gift rule.

⚠ MIGRATE-FIRST via Supabase MCP before the push, then record the `django_migrations` row
(scholarship ledger 211 -> 212).

⚠ HAND-WRITTEN POSTGRES DDL — do NOT paste `sqlmigrate` (it renders for SQLite):

    ALTER TABLE "scholarship_cohorts"
        ADD COLUMN "allowed_start_years" jsonb NOT NULL DEFAULT '[]'::jsonb;
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0212_cohort_allowed_start_years', now());

⚠ THE DATABASE DEFAULT IS KEPT ON PURPOSE, as in 0171: the image still serving between migrate and
deploy does not know the column, and its create-an-intake-year INSERT would break on NOT NULL.

No RLS step: a column on an existing table inherits that table's policies.

⚠ DEPLOYING BEFORE MIGRATING is not safe: the new image selects this column on every load of an
intake year.

⚠ WHY THE DATABASE STEP IS HAND-WRITTEN SQL, NOT `AddField`. On SQLite (the test database) an
`AddField` with a default REBUILDS `scholarship_cohorts` from Django's state. 0211 took
`bucket_b_margin` out of the state but kept the column on purpose (expand-contract, step 1), so the
rebuild silently dropped it, and `test_a317_retired_columns` caught that. A plain `ADD COLUMN` never
rebuilds the table, on either database. The state still gets the `AddField`.
"""

from django.db import migrations, models

_ADD = {
    'postgresql': ('ALTER TABLE "scholarship_cohorts" ADD COLUMN IF NOT EXISTS "allowed_start_years" '
                   "jsonb NOT NULL DEFAULT '[]'::jsonb"),
    'sqlite': ('ALTER TABLE "scholarship_cohorts" ADD COLUMN "allowed_start_years" text NOT NULL '
               """DEFAULT '[]' CHECK ((JSON_VALID("allowed_start_years") OR "allowed_start_years" IS NULL))"""),
}


def _add_column(apps, schema_editor):
    schema_editor.execute(_ADD[schema_editor.connection.vendor])


def _drop_column(apps, schema_editor):
    schema_editor.execute('ALTER TABLE "scholarship_cohorts" DROP COLUMN "allowed_start_years"')


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0211_retire_orphaned_cohort_and_income_fields'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add_column, _drop_column)],
            state_operations=[
                migrations.AddField(
                    model_name='scholarshipcohort',
                    name='allowed_start_years',
                    field=models.JSONField(blank=True, default=list, help_text="Course-start years (e.g. [2025, 2026]) this intake accepts, read from the offer letter's intake year. Empty list = not applied."),
                ),
            ],
        ),
    ]
