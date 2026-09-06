"""Org Config Sprint A — a home for the values an organisation tunes.

ADDITIVE: one new table, no change to any existing one. Every read falls back to the platform
default when no row (or no key) exists, so applying this changes nothing by itself.

⚠ MIGRATE-FIRST via Supabase MCP before the push, then record the `django_migrations` row
(courses ledger 73 → 74). `sqlmigrate` renders SQLite on a dev box, so this is the Postgres DDL
to run, verbatim:

    CREATE TABLE public.organisation_configurations (
        id               bigserial    PRIMARY KEY,
        "values"         jsonb        NOT NULL,
        updated_by_email varchar(254) NOT NULL,
        created_at       timestamptz  NOT NULL,
        updated_at       timestamptz  NOT NULL,
        organisation_id  bigint       NOT NULL UNIQUE
                         REFERENCES public.partner_organisations(id) DEFERRABLE INITIALLY DEFERRED
    );
    ALTER TABLE public.organisation_configurations ENABLE ROW LEVEL SECURITY;
    CREATE POLICY organisation_configurations_service_role ON public.organisation_configurations
        FOR ALL TO service_role USING (true) WITH CHECK (true);

`values` is quoted — it is a reserved-looking word. No separate index on `organisation_id`
(`UNIQUE` already builds one). RLS in the SAME step as the CREATE — the house convention for
every new table (deny by default, one service_role policy); re-run the Security Advisor after.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0073_s_assign_programme_scope'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganisationConfiguration',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('values', models.JSONField(default=dict)),
                ('updated_by_email', models.CharField(blank=True, default='', max_length=254)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organisation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='configuration', to='courses.partnerorganisation')),
            ],
            options={
                'db_table': 'organisation_configurations',
            },
        ),
    ]
