"""Admin System health light (2026-10-28): `system_health_status`, the small store the email and cron
recorders write (`apps/scholarship/system_health_store.py`) and the super-admin light reads.

ADDITIVE: one new table, no change to any existing column, nothing backfilled.

⚠ MIGRATE-FIRST, BY HAND, before the push (scholarship ledger 0179 -> 0180). `sqlmigrate` renders for
the LOCAL backend (SQLite), so this is the Postgres DDL to run, verbatim — rendered offline with
Django's postgresql schema editor from this migration — with RLS in the SAME step and the ledger row:

    BEGIN;
    CREATE TABLE "system_health_status" ("key" varchar(80) NOT NULL PRIMARY KEY, "data" jsonb NOT NULL, "updated_at" timestamp with time zone NOT NULL);
    CREATE INDEX "system_health_status_key_6543d33d_like" ON "system_health_status" ("key" varchar_pattern_ops);
    ALTER TABLE public.system_health_status ENABLE ROW LEVEL SECURITY;
    CREATE POLICY system_health_status_service_role ON public.system_health_status FOR ALL TO service_role USING (true) WITH CHECK (true);
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0180_system_health_status', now());
    COMMIT;

⚠ DEPLOYING BEFORE MIGRATING IS SURVIVABLE, unlike most new tables: every write is best-effort and
runs after the caller's own transaction (`transaction.on_commit`), so a missing table costs a log
line, never an email or a cron run; the light then reads "nothing recorded yet". Migrate first anyway.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0179_programme_asks_higher_results'),
    ]

    operations = [
        migrations.CreateModel(
            name='SystemHealthStatus',
            fields=[
                ('key', models.CharField(help_text="'email', 'cron:<job>' or 'cron:_since'", max_length=80, primary_key=True, serialize=False)),
                ('data', models.JSONField(blank=True, default=dict, help_text='Timestamps (ISO), counts and an error class name. No PII.')),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name_plural': 'System health statuses',
                'db_table': 'system_health_status',
            },
        ),
    ]
