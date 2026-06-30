# Generated for the post-award parent-PIN sprint (S3). Additive — apply migrate-first.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0083_award_comprehension_passed_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='guarantor_phone',
            field=models.CharField(blank=True, default='', max_length=32),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='guarantor_phone_verified_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
