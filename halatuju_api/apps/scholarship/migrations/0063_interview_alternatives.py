from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0062_decisionreopen_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='interview_alternatives_requested_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='interview_alternatives_note',
            field=models.TextField(blank=True, default=''),
        ),
    ]
