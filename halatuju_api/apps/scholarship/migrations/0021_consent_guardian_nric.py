# S19 — Minor consent flow hardening (round 2):
# - Consent.guardian_nric: NEW column (additive ADD COLUMN, NOT NULL DEFAULT '');
#   the guardian's own NRIC, validated against the parent_ic Vision OCR.
# - Consent.guardian_relationship: choices-only AlterField for the refined
#   GUARDIAN_RELATIONSHIPS list (older_sibling → brother + sister; other_relative
#   → relative). Column DDL unchanged; Django emits AlterField anyway.
#
# Applied migrate-first via Supabase MCP execute_sql per the TD-058 workaround.
# 0 existing consent rows on prod → both changes land cleanly with zero rewrites.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0020_minor_consent_flow'),
    ]

    operations = [
        migrations.AddField(
            model_name='consent',
            name='guardian_nric',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AlterField(
            model_name='consent',
            name='guardian_relationship',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
