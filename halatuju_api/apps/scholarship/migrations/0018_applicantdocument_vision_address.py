# Post-S14 — add MyKad address (from Vision OCR) to ApplicantDocument.
# Additive (ADD COLUMN, 0 risk). Applied migrate-first via Supabase MCP
# execute_sql per the TD-058 workaround (sidesteps the post_migrate
# contenttypes/auth non-zero exit on this DB).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0017_alter_success_delay_default'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicantdocument',
            name='vision_address',
            field=models.CharField(blank=True, default='', max_length=500),
        ),
    ]
