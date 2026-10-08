"""Request #31 (BrightPath, 2026-10-08): an intake year can accept only students BORN in chosen
states — `ScholarshipCohort.allowed_birth_states`, read against the place-of-birth code in the IC.

ADDITIVE: one JSON column. Every existing intake year gets an EMPTY list, and empty means the rule
is not applied (the value IS the switch — Sabah S2a, in list form), so nobody's eligibility changes
until an admin ticks a state. Nothing else is backfilled.

⚠ MIGRATE-FIRST via Supabase MCP before the push, then record the `django_migrations` row
(scholarship ledger 170 -> 171).

⚠ HAND-WRITTEN POSTGRES DDL — do NOT paste `sqlmigrate`, which renders for the LOCAL backend
(SQLite) and prints a whole table rebuild for what is one ALTER on Postgres (the 0154 convention):

    ALTER TABLE "scholarship_cohorts"
        ADD COLUMN "allowed_birth_states" jsonb NOT NULL DEFAULT '[]'::jsonb;
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0171_cohort_allowed_birth_states', now());

⚠ THE DATABASE DEFAULT IS KEPT ON PURPOSE (Django would drop it after filling the rows). Between
migrate and deploy the image already serving does not know this column, and its create-an-intake-
year INSERT names every column it knows — without a DB default that INSERT would break on NOT NULL.
With it, a year created in that window arrives empty, which is "not applied". Same shape as 0154.

No RLS step: a column on an existing table inherits that table's policies.

⚠ DEPLOYING BEFORE MIGRATING is not safe: the new image selects this column on every load of an
intake year (Django selects every field), so submissions, the apply page and the console would 500.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0170_application_final_reminder_close_days'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipcohort',
            name='allowed_birth_states',
            field=models.JSONField(blank=True, default=list, help_text="State keys (birth_state.STATE_KEYS) a student must have been BORN in, read from the IC's place-of-birth code. Empty list = not applied."),
        ),
    ]
