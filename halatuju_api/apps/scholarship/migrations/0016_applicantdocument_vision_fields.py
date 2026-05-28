# S13 — Vision OCR soft-signal fields on ApplicantDocument.
# Additive (ADD COLUMN x4 with defaults), 0 risk to existing rows. Applied
# migrate-first via Supabase MCP execute_sql per the TD-058 workaround.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0015_drop_funding_amount_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicantdocument',
            name='vision_nric',
            field=models.CharField(blank=True, default='', max_length=20),
        ),
        migrations.AddField(
            model_name='applicantdocument',
            name='vision_name',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
        migrations.AddField(
            model_name='applicantdocument',
            name='vision_run_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='applicantdocument',
            name='vision_error',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
