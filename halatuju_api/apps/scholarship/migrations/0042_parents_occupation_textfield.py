# Widen parents_occupation varchar(255) -> text. Students write a sentence or
# two here ("My mother is a Grab driver and sole breadwinner…"); the 255 cap
# silently rolled back the entire Story save. Anti-spam length now lives at the
# serializer/UI (STORY_TEXT_MAX), not the column. Backward-compatible widening.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0041_application_reminders'),
    ]

    operations = [
        migrations.AlterField(
            model_name='scholarshipapplication',
            name='parents_occupation',
            field=models.TextField(
                blank=True, default='',
                help_text='What do your parents or guardians do for a living?',
            ),
        ),
    ]
