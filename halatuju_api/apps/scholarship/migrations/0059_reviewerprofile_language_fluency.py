from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0058_sponsorprofile_prompt_version'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewerprofile',
            name='english_fluency',
            field=models.CharField(blank=True, default='', max_length=20,
                                   choices=[('', 'None'), ('conversational', 'Conversational'), ('fluent', 'Fluent')]),
        ),
        migrations.AddField(
            model_name='reviewerprofile',
            name='bm_fluency',
            field=models.CharField(blank=True, default='', max_length=20,
                                   choices=[('', 'None'), ('conversational', 'Conversational'), ('fluent', 'Fluent')]),
        ),
        migrations.AddField(
            model_name='reviewerprofile',
            name='tamil_fluency',
            field=models.CharField(blank=True, default='', max_length=20,
                                   choices=[('', 'None'), ('conversational', 'Conversational'), ('fluent', 'Fluent')]),
        ),
    ]
