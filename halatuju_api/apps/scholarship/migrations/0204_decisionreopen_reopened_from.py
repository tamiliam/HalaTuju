# A1.11a / TD-486: record the status a decision was reopened from, so Cancel reopen restores
# from the record instead of inferring it from the current status. Additive, nullable-safe:
# `db_default=''` lets the still-serving old revision insert rows during the rollout.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0203_applicantdocument_one_live_per_slot'),
    ]

    operations = [
        migrations.AddField(
            model_name='decisionreopen',
            name='reopened_from',
            field=models.CharField(blank=True, db_default='', default='', max_length=20),
        ),
    ]
