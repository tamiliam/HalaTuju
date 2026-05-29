# S15 — capture *how many* siblings are studying (not just whether any are).
# Additive (ADD COLUMN, 0 risk). Applied migrate-first via Supabase MCP
# execute_sql per the TD-058 workaround (sidesteps the post_migrate
# contenttypes/auth non-zero exit on this DB).
#
# The legacy `siblings_studying` boolean stays this sprint for back-compat;
# the drop joins the TD-061 contract batch alongside family_income/siblings/phone.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0018_applicantdocument_vision_address'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='siblings_studying_count',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
