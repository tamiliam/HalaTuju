"""Request #75 (2026-11-16): reject before interview. ADDITIVE.

- `rejection_reason`: a new column, '' by default in the model AND in the database (`db_default`), so
  the old image, which inserts rows without it, keeps working between migrate and deploy.
- `rejection_category` / `pending_rejection_category` gain the choice 'pre_interview'. Choices live in
  Django's state only: no database change (13 characters, inside the existing 20).

Written as ONE plain `ADD COLUMN` (SeparateDatabaseAndState), not a bare AddField / AlterField: on
SQLite (the test database) both of those REBUILD the table from Django's state, and 0211 left three
retired columns in the database but not in the state, so a rebuild would drop them
(`test_a317_retired_columns`). On PostgreSQL the SQL is what AddField would have run. The production
DDL is exactly this statement.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0214_document_ocr_text'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE scholarship_applications ADD COLUMN rejection_reason varchar(40) DEFAULT '' NOT NULL;",
                    reverse_sql='ALTER TABLE scholarship_applications DROP COLUMN rejection_reason;',
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='scholarshipapplication',
                    name='rejection_reason',
                    field=models.CharField(blank=True, choices=[('not_b40', 'not_b40'), ('not_government_institution', 'not_government_institution'), ('results_too_low', 'results_too_low'), ('programme_requirements', 'programme_requirements'), ('not_responsive', 'not_responsive'), ('other', 'other')], db_default='', default='', help_text='#75 main reason (pre_interview only); internal', max_length=40),
                ),
                migrations.AlterField(
                    model_name='scholarshipapplication',
                    name='pending_rejection_category',
                    field=models.CharField(blank=True, choices=[('merit', 'Did not meet the academic/merit floor'), ('need', 'Did not meet the financial-need criteria'), ('ineligible', 'Out of scope / ineligible'), ('interview', 'Reviewed but not selected'), ('contractual', 'Failed post-award contractual steps'), ('incomplete', 'Did not complete the application'), ('pre_interview', 'Rejected before interview')], default='', help_text='A scheduled-but-unrevealed decline bucket (cool-off); blank = none pending', max_length=20),
                ),
                migrations.AlterField(
                    model_name='scholarshipapplication',
                    name='rejection_category',
                    field=models.CharField(blank=True, choices=[('merit', 'Did not meet the academic/merit floor'), ('need', 'Did not meet the financial-need criteria'), ('ineligible', 'Out of scope / ineligible'), ('interview', 'Reviewed but not selected'), ('contractual', 'Failed post-award contractual steps'), ('incomplete', 'Did not complete the application'), ('pre_interview', 'Rejected before interview')], default='', help_text="Why the application was rejected; blank unless status='rejected'", max_length=20),
                ),
            ],
        ),
    ]
