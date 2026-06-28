# Reviewer-query S3 — normalised (sortable) offer reporting date (additive column).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0079_alter_scholarshipcohort_name'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='reporting_date',
            field=models.DateField(blank=True, null=True),
        ),
    ]
