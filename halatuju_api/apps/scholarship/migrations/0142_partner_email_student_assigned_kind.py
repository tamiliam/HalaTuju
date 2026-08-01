"""Add the `student_assigned` partner-email kind (request #3, 2026-08-01).

⚠ THIS MIGRATION EMITS NO DDL. Django `choices` are validated in Python, never in Postgres — both
operations alter only the field's declared choices, and `sqlmigrate` prints nothing but the BEGIN /
COMMIT. So there is nothing to apply by hand on production under the migrate-first rule; the ONLY
production step is recording the ledger row, back-stamped to the commit that shipped it, so the
sequence reads in order and the next `migrate` does not try to re-run it.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0141_org_request_analysis_proposed_triage'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partneremaillog',
            name='kind',
            field=models.CharField(choices=[('weekly_summary', 'Weekly summary'), ('shortlisted_followup', 'Chase list'), ('awaiting_review', 'Awaiting review'), ('awarded', 'Awarded'), ('assigned', 'A student joins their list'), ('student_assigned', 'The student is told')], max_length=32),
        ),
        migrations.AlterField(
            model_name='partneremailtemplate',
            name='kind',
            field=models.CharField(choices=[('weekly_summary', 'Weekly summary'), ('shortlisted_followup', 'Chase list'), ('awaiting_review', 'Awaiting review'), ('awarded', 'Awarded'), ('assigned', 'A student joins their list'), ('student_assigned', 'The student is told')], max_length=32, unique=True),
        ),
    ]
