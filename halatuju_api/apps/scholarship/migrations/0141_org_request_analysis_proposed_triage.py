"""The engineer's PROPOSED triage — two columns on the analysis (2026-08-01).

MIGRATE-FIRST. Cloud Build never runs `migrate`, so this DDL is applied to production BY HAND
before the code that reads the columns is pushed. `sqlmigrate` here emits SQLite's table-rebuild
form, which is not what production runs — the Postgres statements below are the ones to use.

Additive and reversible: two nullable-in-spirit text columns with a '' default, no backfill, no
index. Existing rows read '' meaning "no opinion", which is deliberately NOT the same as agreeing
with the AI draft.

    -- 1. the columns
    ALTER TABLE org_request_analyses
      ADD COLUMN proposed_kind varchar(10) NOT NULL DEFAULT '',
      ADD COLUMN proposed_lane varchar(20) NOT NULL DEFAULT '';

    -- 2. the ledger row, so `migrate` never tries to add them again
    INSERT INTO django_migrations (app, name, applied)
    VALUES ('scholarship', '0141_org_request_analysis_proposed_triage', now());

    -- 3. post-checks
    SELECT column_name, data_type, character_maximum_length, column_default
    FROM information_schema.columns
    WHERE table_name = 'org_request_analyses' AND column_name LIKE 'proposed_%';

RLS is inherited from the table (deny-by-default, backend service role only, set in 0140) — a new
column on an existing table needs no policy of its own.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0140_org_request_analysis'),
    ]

    operations = [
        migrations.AddField(
            model_name='orgrequestanalysis',
            name='proposed_kind',
            field=models.CharField(blank=True, default='', max_length=10),
        ),
        migrations.AddField(
            model_name='orgrequestanalysis',
            name='proposed_lane',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
    ]
