from django.db import migrations, models


class Migration(migrations.Migration):
    """Additive: a ≤20-word card-strict blurb for the sponsor-pool browse card."""

    dependencies = [
        ('scholarship', '0070_interview_cancel_reason'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsorprofile',
            name='anon_blurb',
            field=models.CharField(blank=True, default='', max_length=200),
        ),
    ]
