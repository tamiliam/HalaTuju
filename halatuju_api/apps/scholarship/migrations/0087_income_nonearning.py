# Generated for Phase 2B — unemployment detail (income model).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0086_income_declared'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='income_nonearning',
            field=models.JSONField(blank=True, default=dict, help_text="{member: {reason, since:'YYYY-MM'}} for an 'unemployed' roster member — why and since when. Reviewer texture; EPF (all-zeros employer) corroborates. Never a gate."),
        ),
    ]
