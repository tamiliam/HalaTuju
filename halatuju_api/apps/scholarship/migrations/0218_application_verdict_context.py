"""LL4 (learning loop, 2026-11-19): record what fed each decision —
`ScholarshipApplication.ai_verdict_context`, written by `AdminRecordVerdictView` in the same save as
`ai_verdict_snapshot` (`verdict_context.verdict_context_or_empty`).

ADDITIVE: one JSON column. Every existing row gets an EMPTY object, which reads "decided before LL4,
evidence state unknown". Nothing is backfilled: the evidence of an old decision cannot be recovered.

⚠ MIGRATE-FIRST, BY HAND, and ONLY WITH THE OWNER'S YES, before the publish (scholarship ledger
0217 -> 0218; 0217 must be applied first). Then record the `django_migrations` row.
⚠ THE OWNER RUNS THE SQL BELOW BY HAND: NOBODY RUNS `migrate` AGAINST PRODUCTION (the code path
carries the same 5s lock_timeout only as a backstop).

Pre-check (read-only; expect 1, then 0, then no row):

    SELECT count(*) FROM django_migrations WHERE app = 'scholarship' AND name = '0217_reviewerprofile_highest_position';
    SELECT count(*) FROM django_migrations WHERE app = 'scholarship' AND name = '0218_application_verdict_context';
    SELECT column_name FROM information_schema.columns
     WHERE table_name = 'scholarship_applications' AND column_name = 'ai_verdict_context';

⚠ HAND-WRITTEN POSTGRES DDL — do NOT paste `sqlmigrate` (it renders for SQLite). The busy table takes a
brief lock; `lock_timeout` makes the step give up rather than queue behind it (if it times out, nothing
changed: run it again at a quiet time):

    BEGIN;
    SET LOCAL lock_timeout = '5s';
    ALTER TABLE "scholarship_applications"
        ADD COLUMN "ai_verdict_context" jsonb NOT NULL DEFAULT '{}'::jsonb;
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0218_application_verdict_context', now());
    COMMIT;

Post-check: `SELECT count(*) FROM scholarship_applications WHERE ai_verdict_context <> '{}'::jsonb` is 0.

⚠ THE DATABASE DEFAULT IS KEPT ON PURPOSE, as in 0171 and 0212: the image still serving between migrate
and deploy does not know the column, and its create-an-application INSERT would break on NOT NULL.

No RLS step: a column on an existing table inherits that table's policies.

⚠ DEPLOYING BEFORE MIGRATING is NOT safe, and the failure is wide: the new image selects this column on
EVERY load of an application (every list, detail and cockpit read), not only on the verdict write.

⚠ WHY THE DATABASE STEP IS HAND-WRITTEN SQL, NOT `AddField` (the 0212 reason). On SQLite (the test
database) an `AddField` with a default REBUILDS `scholarship_applications` from Django's state. 0211 took
fields out of the state but kept their columns on purpose (expand-contract, step 1), so a rebuild would
silently drop them. A plain `ADD COLUMN` never rebuilds the table, on either database. The state still
gets the `AddField`.

ROLLBACK (roll the IMAGE back FIRST — the new image reads the column on every application load — then):

    BEGIN;
    SET LOCAL lock_timeout = '5s';
    ALTER TABLE "scholarship_applications" DROP COLUMN "ai_verdict_context";
    DELETE FROM django_migrations WHERE app = 'scholarship' AND name = '0218_application_verdict_context';
    COMMIT;
"""

from django.db import migrations, models

_ADD = {
    'postgresql': ('ALTER TABLE "scholarship_applications" ADD COLUMN IF NOT EXISTS "ai_verdict_context" '
                   "jsonb NOT NULL DEFAULT '{}'::jsonb"),
    'sqlite': ('ALTER TABLE "scholarship_applications" ADD COLUMN "ai_verdict_context" text NOT NULL '
               """DEFAULT '{}' CHECK ((JSON_VALID("ai_verdict_context") OR "ai_verdict_context" IS NULL))"""),
}


def _give_up_rather_than_queue(schema_editor):
    """The same guard as the hand-run SQL above, should `migrate` ever run against Postgres: the
    migration runs in one transaction there (atomic), so `SET LOCAL` holds for the ALTER and ends
    with it. It changes no result, only how long the ALTER may wait for the table lock."""
    if schema_editor.connection.vendor == 'postgresql':
        schema_editor.execute("SET LOCAL lock_timeout = '5s'")


def _add_column(apps, schema_editor):
    _give_up_rather_than_queue(schema_editor)
    schema_editor.execute(_ADD[schema_editor.connection.vendor])


def _drop_column(apps, schema_editor):
    _give_up_rather_than_queue(schema_editor)
    schema_editor.execute('ALTER TABLE "scholarship_applications" DROP COLUMN "ai_verdict_context"')


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0217_reviewerprofile_highest_position'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[migrations.RunPython(_add_column, _drop_column)],
            state_operations=[
                migrations.AddField(
                    model_name='scholarshipapplication',
                    name='ai_verdict_context',
                    field=models.JSONField(blank=True, default=dict, help_text='LL4: the PII-free record of what fed ai_verdict_snapshot {schema, documents, models, fingerprint, key_check}, or {schema, error} when it could not be built. Empty = decided before LL4 (evidence state unknown).'),
                ),
            ],
        ),
    ]
