# Post-award lifecycle S5 — maintenance sub-state (additive column).
# The stray `AlterField` on scholarshipcohort.name that makemigrations keeps
# re-proposing (a foreign help_text drift, not ours) is deliberately omitted.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0076_disbursement'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='maintenance_substate',
            field=models.CharField(
                blank=True, default='on_track', max_length=20,
                choices=[
                    ('on_track', 'On track'),
                    ('probation', 'Probation (at-risk)'),
                    ('on_hold', 'On hold (paused)'),
                    ('ready_to_close', 'Ready to close'),
                ],
                help_text="Operational sub-state within status='maintenance'; 'on_track' otherwise",
            ),
        ),
    ]
