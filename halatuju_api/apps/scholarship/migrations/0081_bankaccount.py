# Bank details capture — the student's payout account (post-award, Action Centre).
# CreateModel BankAccount (RLS applied separately, migrate-first via Supabase MCP) +
# the additive 'bank_statement' doc_type choice (choices-only, no DDL).
# The stray AlterField on scholarshipcohort.name that makemigrations keeps re-proposing
# (a foreign help_text drift, not ours) is deliberately omitted — see 0076/0079.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0080_reporting_date'),
    ]

    operations = [
        migrations.AlterField(
            model_name='applicantdocument',
            name='doc_type',
            field=models.CharField(
                max_length=30,
                choices=[
                    ('ic', 'Identity Card'), ('results_slip', 'Results Slip'),
                    ('photo', 'Photo'), ('epf', 'EPF Statement'), ('str', 'STR Document'),
                    ('statement_of_intent', 'Statement of Intent'),
                    ('reference_letter', 'Reference Letter'), ('salary_slip', 'Salary Slip'),
                    ('water_bill', 'Water Bill'), ('electricity_bill', 'Electricity Bill'),
                    ('offer_letter', 'Offer Letter'), ('parent_ic', 'Parent/Guardian IC'),
                    ('guardianship_letter', 'Guardianship Letter'),
                    ('birth_certificate', 'Birth Certificate'),
                    ('bank_statement', 'Bank Statement'), ('other', 'Other Document'),
                ],
            ),
        ),
        migrations.CreateModel(
            name='BankAccount',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bank_name', models.CharField(max_length=120)),
                ('account_number', models.CharField(max_length=40)),
                ('account_holder', models.CharField(max_length=200)),
                ('holder_verdict', models.CharField(choices=[('ok', 'Holder matches the student')], default='ok', max_length=20)),
                ('confirmed_at', models.DateTimeField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('application', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='bank_account', to='scholarship.scholarshipapplication')),
                ('source_doc', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='bank_accounts', to='scholarship.applicantdocument')),
            ],
            options={
                'db_table': 'bank_accounts',
            },
        ),
    ]
