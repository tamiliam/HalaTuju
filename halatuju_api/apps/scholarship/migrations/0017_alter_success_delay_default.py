# Shift the shortlist invitation default from 2h to 48h (per user direction
# 2026-05-28 — preparing for an inflow of applicants and wanting a longer
# considered window before the invitation email goes out).
#
# Applied migrate-first via Supabase MCP:
#   - ALTER TABLE scholarship_cohorts ALTER COLUMN success_delay_hours SET DEFAULT 48
#   - UPDATE scholarship_cohorts SET success_delay_hours = 48 WHERE id = 1  (b40-2026)
#   - INSERT INTO django_migrations (...)
# (AlterField default-change does NOT rewrite existing rows — per the lesson —
# so the UPDATE is required to flip the live cohort. Existing 3 apps keep
# their original decision_due_at; this only affects future submissions.)
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0016_applicantdocument_vision_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scholarshipcohort',
            name='success_delay_hours',
            field=models.IntegerField(
                default=48,
                help_text='Hours after submit before the shortlist (invitation) email + follow-up unlock (S8 delayed reveal)',
            ),
        ),
    ]
