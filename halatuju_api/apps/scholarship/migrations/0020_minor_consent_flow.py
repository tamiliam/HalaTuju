# S17 — Minor consent flow. Choices-only migration (no DDL):
# - ApplicantDocument.DOC_TYPES gains parent_ic + guardianship_letter
# - Consent.guardian_relationship adopts a structured choices list (GUARDIAN_RELATIONSHIPS)
#
# Django records this as an AlterField on the column even though the underlying
# CharField storage shape is unchanged. Applied as a choices-only migration via
# Supabase MCP execute_sql — no DDL emitted; the django_migrations row is
# recorded directly to keep the recorded-migration log in sync with this file.
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0019_scholarshipapplication_siblings_studying_count'),
    ]

    operations = [
        migrations.AlterField(
            model_name='applicantdocument',
            name='doc_type',
            field=models.CharField(
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
                    ('parent_ic', 'Parent/Guardian IC'),
                    ('guardianship_letter', 'Guardianship Letter'),
                ],
                max_length=30,
            ),
        ),
        # Consent.guardian_relationship gains structured choices. Django emits
        # AlterField for any choices change, even when the column DDL is unchanged.
        # Pre-S17 free-text values stay readable; only writes through the serializer
        # are validated against the new list.
        migrations.AlterField(
            model_name='consent',
            name='guardian_relationship',
            field=models.CharField(blank=True, default='', max_length=100),
        ),
    ]
