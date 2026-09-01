"""Layer 1 A3 — a colour gets a lifecycle: draft, live, and what it used to be.

ADDITIVE except for one deliberate DROP: the `UNIQUE (organisation_id)` that A1's `OneToOne` put
there. A1 said A3 would relax it and this is that. In its place go TWO PARTIAL uniques — one draft
and one active per organisation — because an organisation must be able to hold many `archived`
rows, and that history IS the undo.

⚠ THE DATA STEP MATTERS EVEN THOUGH PRODUCTION IS EMPTY. A row that existed before A3 WAS the live
theme: `status` defaults to `draft`, so without the promotion below an existing tenant would be
silently un-published by a migration that reads as purely additive. Production has 0 rows today
(checked, not assumed), so this is a no-op there — but a dev or restored database is not production,
and a migration should express intent rather than rely on being lucky.

⚠ MIGRATE-FIRST. Apply on production BEFORE the push, then record the `django_migrations` row.
`sqlmigrate` renders SQLite on a dev box, so the Postgres DDL is hand-written here — the existing
unique's real name was read off production, not guessed:

    ALTER TABLE organisation_themes
        ADD COLUMN archived_at        timestamptz NULL,
        ADD COLUMN published_at       timestamptz NULL,
        ADD COLUMN published_by_email varchar(254) NOT NULL DEFAULT '',
        ADD COLUMN status             varchar(20)  NOT NULL DEFAULT 'draft';

    -- a pre-A3 row was the LIVE theme
    UPDATE organisation_themes SET status = 'active', published_at = created_at;

    ALTER TABLE organisation_themes DROP CONSTRAINT organisation_themes_organisation_id_key;
    CREATE INDEX organisation_themes_organisation_id
        ON organisation_themes (organisation_id);

    CREATE UNIQUE INDEX one_draft_theme_per_organisation
        ON organisation_themes (organisation_id) WHERE status = 'draft';
    CREATE UNIQUE INDEX one_active_theme_per_organisation
        ON organisation_themes (organisation_id) WHERE status = 'active';

RLS is already on the table from `0071` with its one `service_role` policy — this migration adds no
table, so there is nothing new to secure. Confirm the Security Advisor is still clean afterwards.
"""
import django.db.models.deletion
from django.db import migrations, models


def promote_existing_to_active(apps, schema_editor):
    """A theme that existed before A3 was what visitors saw. Say so, rather than leaving it a
    draft — a migration that silently un-publishes a tenant is the worst kind, because it reads as
    additive and produces no error."""
    OrganisationTheme = apps.get_model('courses', 'OrganisationTheme')
    for row in OrganisationTheme.objects.all():
        row.status = 'active'
        row.published_at = row.created_at
        row.save(update_fields=['status', 'published_at'])


def demote_all_to_draft(apps, schema_editor):
    """The reverse. Not lossy in itself — but note that going back also means going back to ONE row
    per organisation, so a reversal after A3 has archived versions needs a human, not this."""
    OrganisationTheme = apps.get_model('courses', 'OrganisationTheme')
    OrganisationTheme.objects.update(status='draft')


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0071_organisationtheme'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='organisationtheme',
            options={'ordering': ['-created_at']},
        ),
        migrations.AddField(
            model_name='organisationtheme',
            name='archived_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='organisationtheme',
            name='published_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='organisationtheme',
            name='published_by_email',
            field=models.CharField(blank=True, default='', max_length=254),
        ),
        migrations.AddField(
            model_name='organisationtheme',
            name='status',
            field=models.CharField(choices=[('draft', 'Draft'), ('active', 'Active'), ('archived', 'Archived')], default='draft', max_length=20),
        ),
        # Between the column and the constraints: existing rows were live, so they become active
        # while there is still at most one per organisation.
        migrations.RunPython(promote_existing_to_active, demote_all_to_draft),
        migrations.AlterField(
            model_name='organisationtheme',
            name='organisation',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='themes', to='courses.partnerorganisation'),
        ),
        migrations.AddConstraint(
            model_name='organisationtheme',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'draft')), fields=('organisation',), name='one_draft_theme_per_organisation'),
        ),
        migrations.AddConstraint(
            model_name='organisationtheme',
            constraint=models.UniqueConstraint(condition=models.Q(('status', 'active')), fields=('organisation',), name='one_active_theme_per_organisation'),
        ),
    ]
