from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0057_alter_applicantdocument_doc_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='sponsorprofile',
            name='prompt_version',
            field=models.CharField(blank=True, default='', max_length=30),
        ),
    ]
