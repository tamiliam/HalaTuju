# Post-award lifecycle S6 — manual-close audit stamp (additive columns).
# The stray `AlterField` on scholarshipcohort.name that makemigrations keeps
# re-proposing (a foreign help_text drift, not ours) is deliberately omitted (TD-147).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0077_maintenance_substate'),
    ]

    operations = [
        migrations.AddField(
            model_name='scholarshipapplication',
            name='closed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='scholarshipapplication',
            name='closed_by',
            field=models.CharField(blank=True, default='', max_length=254),
        ),
    ]
