"""The public apply page's copy belongs to the GIFT, not the platform.

⚠ MIGRATE-FIRST. The deploy triggers do NOT run `migrate`, so this must be applied to production
via the Supabase MCP and its `django_migrations` row recorded BEFORE the push.

⚠ HAND-WRITTEN POSTGRES DDL — do NOT paste `sqlmigrate`, which renders for the LOCAL backend
(SQLite) and prints a whole table rebuild for what is one ALTER on Postgres (lessons.md,
2026-06-21):

    ALTER TABLE scholarship_programmes
        ADD COLUMN apply_copy jsonb NOT NULL DEFAULT '{}'::jsonb;

Additive, defaulted, no backfill: every existing gift reads `{}`, which MEANS "use the platform
default" — so BrightPath's apply page is byte-identical after this ships.

No new table ⇒ no RLS work and no Security Advisor step.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0153_programme_code_alias'),
    ]

    operations = [
        migrations.AddField(
            model_name='programme',
            name='apply_copy',
            field=models.JSONField(blank=True, default=dict, help_text='Public apply-page copy per language: {"en": {"title": …, "intro": …, "criteria": […]}, "ms": {…}, "ta": {…}}. Blank means the platform default. Validated by apply_copy.normalise.'),
        ),
    ]
