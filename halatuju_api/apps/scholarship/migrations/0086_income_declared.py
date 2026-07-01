# Generated for Phase 2A — declared informal income (income model).

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0085_bursary_reminder_stamps'),
    ]

    operations = [
        # The only DDL for prod (migrate-first): additive, 0-row-safe.
        migrations.AddField(
            model_name='scholarshipapplication',
            name='income_declared',
            field=models.JSONField(blank=True, default=dict, help_text='Salary route: {member: declared avg monthly income (RM, int)} for a working member with no payslip/EPF. Accepted if a valid STR is on file, else needs an income_support_doc. Feeds earner_monthly_income → per-capita.'),
        ),
        # State-only: adds the 'income_support_doc' choice to ApplicantDocument.doc_type.
        # Django tracks `choices` in migration state but they are not a DB constraint, so this
        # emits NO SQL — nothing to apply on prod beyond the AddField above.
        migrations.AlterField(
            model_name='applicantdocument',
            name='doc_type',
            field=models.CharField(choices=[('ic', 'Identity Card'), ('results_slip', 'Results Slip'), ('photo', 'Photo'), ('epf', 'EPF Statement'), ('str', 'STR Document'), ('statement_of_intent', 'Statement of Intent'), ('reference_letter', 'Reference Letter'), ('salary_slip', 'Salary Slip'), ('income_support_doc', 'Income Support Document'), ('water_bill', 'Water Bill'), ('electricity_bill', 'Electricity Bill'), ('offer_letter', 'Offer Letter'), ('parent_ic', 'Parent/Guardian IC'), ('guardianship_letter', 'Guardianship Letter'), ('birth_certificate', 'Birth Certificate'), ('bank_statement', 'Bank Statement'), ('other', 'Other Document')], max_length=30),
        ),
    ]
