"""A3.17 / TD-084 / TD-226 (2026-11-11): retire three orphaned columns, expand-contract, in two steps.

`ScholarshipApplication.earner_work_status` (NOT NULL), `ScholarshipApplication.household_other_earners`
(nullable) and `ScholarshipCohort.bucket_b_margin` (NOT NULL) are read by nothing. A plain RemoveField
breaks the deploy in either order: the old image still SELECTs the columns while the new one builds,
and the new image's INSERTs omit them, so the two NOT NULL columns would refuse every new row.

- this migration (STEP 1, by hand, BEFORE the push): the two NOT NULL columns get a DATABASE default
  (earner_work_status '' and bucket_b_margin 1), so the new code's INSERTs pass; the three fields leave
  Django's STATE only. No column is dropped, so the old image keeps working and stays a rollback target.
- DROP COLUMN (STEP 2, a later sprint, 0212, AFTER the new image serves all traffic): `DROP COLUMN IF
  EXISTS`, no CASCADE, state_operations empty. Not written yet.

`funding_envelope` is NOT touched: KEPT by owner ruling on 2026-11-11 for the planned Programme budget.

NOTE for 0212: test_a317_retired_columns.py asserts the three columns still EXIST in the database;
0212 must delete or rewrite those column-exists asserts when it drops them.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0210_read_and_notify_queues'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.AlterField(
                    model_name='scholarshipapplication',
                    name='earner_work_status',
                    field=models.CharField(
                        blank=True, default='', db_default='', max_length=12,
                        choices=[('', 'Not chosen'), ('payslip', 'Working — has payslip'),
                                 ('informal', 'Working — no payslip'), ('not_working', 'Not working')]),
                ),
                migrations.AlterField(
                    model_name='scholarshipcohort',
                    name='bucket_b_margin',
                    field=models.IntegerField(default=1, db_default=1),
                ),
            ],
            state_operations=[
                migrations.RemoveField(
                    model_name='scholarshipapplication',
                    name='earner_work_status',
                ),
                migrations.RemoveField(
                    model_name='scholarshipapplication',
                    name='household_other_earners',
                ),
                migrations.RemoveField(
                    model_name='scholarshipcohort',
                    name='bucket_b_margin',
                ),
            ],
        ),
    ]
