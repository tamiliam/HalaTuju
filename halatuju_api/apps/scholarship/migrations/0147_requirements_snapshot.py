"""Layer 0 — freeze what the programme asked for at the Step-4 Submit (2026-08-30).

Additive, nullable. Applied MIGRATE-FIRST on production by hand (the deploy does not run
`migrate`; local is SQLite so `sqlmigrate` renders the wrong dialect). The Postgres DDL:

    ALTER TABLE scholarship_applications ADD COLUMN requirements_snapshot jsonb NULL;
    INSERT INTO django_migrations (app, name, applied)
    VALUES ('scholarship', '0147_requirements_snapshot', now());

Existing table, so no RLS work. Rows already submitted stay NULL here (they follow the live
configuration exactly as before) until `backfill_requirements_snapshots --apply` freezes
today's resolution for them — run it on the live service after the deploy.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0146_invitation_email_kinds_per_group'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='requirements_snapshot',
            field=models.JSONField(
                blank=True, null=True,
                help_text='What the programme asked for, frozen at the Step-4 Submit. NULL until then.',
            ),
        ),
    ]
