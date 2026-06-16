from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0059_reviewerprofile_language_fluency'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewerprofile',
            name='share_phone_with_students',
            field=models.BooleanField(default=True),
        ),
    ]
