# Hand-written migration — choices-only change; no DDL on Postgres.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0013_fundingneed_s3_fields'),
    ]

    operations = [
        migrations.AlterField(
            model_name='applicantdocument',
            name='doc_type',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('ic', 'Identity Card'),
                    ('results_slip', 'Results Slip'),
                    ('photo', 'Photo'),
                    ('epf', 'EPF Statement'),
                    ('str', 'STR Document'),
                    ('statement_of_intent', 'Statement of Intent'),
                    ('reference_letter', 'Reference Letter'),
                    ('salary_slip', 'Salary Slip'),
                    ('water_bill', 'Water Bill'),
                    ('electricity_bill', 'Electricity Bill'),
                    ('offer_letter', 'Offer Letter'),
                ],
            ),
        ),
    ]
