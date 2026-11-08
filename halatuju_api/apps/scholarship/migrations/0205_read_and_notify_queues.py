# A2.3 / TD-519: the upload's paid read and the assignment's two emails leave the request. These
# seven columns are the two queues (`upload_read.py`, `assign_notify.py`). Additive, old-image safe:
# `db_default` lets the still-serving old revision insert applicant_documents / assignment_events
# rows during the rollout, and its rows read '' (not queued), so nothing is read or sent twice.
# ⚠ Sibling branch a21 also adds a 0205 (sponsorprofile_finalise_queue). Whichever merges second
# renumbers its file to 0206 and depends on the other's 0205.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0204_decisionreopen_reopened_from'),
    ]

    operations = [
        migrations.AddField(
            model_name='applicantdocument',
            name='read_attempts',
            field=models.PositiveSmallIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name='applicantdocument',
            name='read_claimed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='applicantdocument',
            name='read_plan',
            field=models.JSONField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='applicantdocument',
            name='read_state',
            field=models.CharField(blank=True, db_default='', default='', max_length=10),
        ),
        migrations.AddField(
            model_name='assignmentevent',
            name='notify_attempts',
            field=models.PositiveSmallIntegerField(db_default=0, default=0),
        ),
        migrations.AddField(
            model_name='assignmentevent',
            name='notify_claimed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='assignmentevent',
            name='notify_state',
            field=models.CharField(blank=True, db_default='', default='', max_length=10),
        ),
    ]
