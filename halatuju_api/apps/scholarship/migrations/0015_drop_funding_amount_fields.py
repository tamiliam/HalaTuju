# TD-059 cleanup — drop the dead FundingNeed amount columns left behind by the
# S3 funding reframe (v2.4.2). 0 prod rows in funding_needs at the time of cleanup
# (verified before push); destructive but safe. Deployed under the expand-contract
# pattern: code that no longer reads these columns ships first, THEN the DROP
# COLUMN runs on prod (via Supabase MCP execute_sql + a django_migrations row,
# per the TD-058 workaround — manage.py migrate exits non-zero on this prod DB).
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0014_more_doc_types'),
    ]

    operations = [
        migrations.RemoveField(model_name='fundingneed', name='tuition_gap'),
        migrations.RemoveField(model_name='fundingneed', name='laptop'),
        migrations.RemoveField(model_name='fundingneed', name='hostel'),
        migrations.RemoveField(model_name='fundingneed', name='transport'),
        migrations.RemoveField(model_name='fundingneed', name='books'),
        migrations.RemoveField(model_name='fundingneed', name='monthly_allowance'),
        migrations.RemoveField(model_name='fundingneed', name='allowance_months'),
        migrations.RemoveField(model_name='fundingneed', name='other'),
        migrations.RemoveField(model_name='fundingneed', name='other_desc'),
    ]
