# A2.1 / TD-517: record-verdict queues the final profile instead of writing it inside the request;
# the `finalise-profiles` cron writes it. These five columns are the queue. Additive, old-image safe:
# `db_default` lets the still-serving old revision insert sponsor_profiles rows during the rollout.
# NUMBERING: 0209, after `0208_mentor_gifts`. Renumbered from 0205 at the G6 merge (2026-11-08).
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0208_mentor_gifts'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsorprofile',
            name='finalise_state',
            field=models.CharField(blank=True, db_default='', default='', max_length=10),
        ),
        migrations.AddField(
            model_name='sponsorprofile',
            name='finalise_language',
            field=models.CharField(blank=True, db_default='', default='', max_length=20),
        ),
        migrations.AddField(
            model_name='sponsorprofile',
            name='finalise_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sponsorprofile',
            name='finalise_claimed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='sponsorprofile',
            name='finalise_attempts',
            field=models.PositiveSmallIntegerField(db_default=0, default=0),
        ),
    ]
