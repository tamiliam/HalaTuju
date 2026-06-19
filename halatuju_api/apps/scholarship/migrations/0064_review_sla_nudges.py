from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0063_interview_alternatives'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='review_nudged_soon_at',
            field=models.DateTimeField(blank=True, null=True,
                                       help_text="When the 'verdict due soon' reviewer nudge was sent"),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='review_nudged_overdue_at',
            field=models.DateTimeField(blank=True, null=True,
                                       help_text="When the 'verdict overdue' reviewer nudge was sent"),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='review_escalated_at',
            field=models.DateTimeField(blank=True, null=True,
                                       help_text="When the overdue verdict was escalated to super-admins"),
        ),
    ]
