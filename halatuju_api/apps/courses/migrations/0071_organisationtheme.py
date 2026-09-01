"""Layer 1 A1 — a tenant's colours get a home.

ADDITIVE: one new table, no change to any existing one. Nothing reads it until a row exists, and
BrightPath deliberately gets no row, so applying this changes nothing a visitor sees.

⚠ MIGRATE-FIRST. Apply on production BEFORE the push, then record the `django_migrations` row.
`sqlmigrate` renders SQLite on a dev box, so the Postgres DDL is hand-written here:

    CREATE TABLE organisation_themes (
        id                bigserial    PRIMARY KEY,
        source_colour     varchar(20)  NOT NULL DEFAULT '',
        tokens            jsonb        NOT NULL,
        created_at        timestamptz  NOT NULL,
        updated_at        timestamptz  NOT NULL,
        organisation_id   bigint       NOT NULL UNIQUE
                          REFERENCES partner_organisations(id) DEFERRABLE INITIALLY DEFERRED
    );
    CREATE INDEX organisation_themes_organisation_id_key
        ON organisation_themes (organisation_id);
    ALTER TABLE organisation_themes ENABLE ROW LEVEL SECURITY;
    CREATE POLICY organisation_themes_service_role ON organisation_themes
        FOR ALL TO service_role USING (true) WITH CHECK (true);

RLS in the SAME step as the CREATE — the house convention for every new table (deny by default,
one service_role policy). Confirm the Supabase Security Advisor is clean afterwards.
"""
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0070_results_exam_type'),
    ]

    operations = [
        migrations.CreateModel(
            name='OrganisationTheme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('source_colour', models.CharField(blank=True, default='', help_text="The hex these tokens were derived from, e.g. '#a21caf'; '' = set by hand", max_length=20)),
                ('tokens', models.JSONField(default=dict)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('organisation', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='theme', to='courses.partnerorganisation')),
            ],
            options={
                'db_table': 'organisation_themes',
            },
        ),
    ]
