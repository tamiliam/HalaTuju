"""Third results route S2a (2026-10-25; TD-326, requests #37 #38 #43): a profile can hold
Matriculation / Asasi / Diploma results. Roadmap: docs/plans/2026-10-25-third-results-route-roadmap.md.

- `exam_type` / `results_exam_type` gain the choices `matric`, `asasi`, `diploma` (CHOICES ONLY:
  max_length 10 already fits, and the live table has no CHECK constraint - read 2026-10-25 - so
  these two AlterFields render as no-ops on Postgres);
- four ADDITIVE columns on `api_student_profiles`: `higher_cgpa` and `higher_koko` (double, NULL),
  `higher_institution_type` (varchar(10) NOT NULL, DEFAULT '' kept IN THE DATABASE) and
  `completed_qualifications` (jsonb NOT NULL, DEFAULT '[]' kept IN THE DATABASE). Postgres fills
  existing rows from the defaults without rewriting the table. NOTHING BACKFILLED: every existing
  profile reads [] / '' / NULL, which `exam_questions.results_held` answers exactly as before (D1).
  No index, no new table (so no RLS step).

MIGRATE-FIRST, BY HAND, before the push (courses ledger 0083 -> 0084). `sqlmigrate` renders for the
LOCAL backend (SQLite), so this is the Postgres DDL to run, verbatim - rendered offline with
Django's postgresql schema editor from this migration - with the ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "api_student_profiles" ADD COLUMN "completed_qualifications" jsonb DEFAULT '[]'::jsonb NOT NULL;
    ALTER TABLE "api_student_profiles" ADD COLUMN "higher_cgpa" double precision NULL;
    ALTER TABLE "api_student_profiles" ADD COLUMN "higher_institution_type" varchar(10) DEFAULT '' NOT NULL;
    ALTER TABLE "api_student_profiles" ADD COLUMN "higher_koko" double precision NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0084_third_results_route', now());
    COMMIT;

BETWEEN MIGRATE AND DEPLOY the image already serving never reads these columns, and its profile
inserts (which do not name them) still succeed because both NOT NULL defaults live in the database
(lessons 2026-10-19). Deploying BEFORE migrating is not safe: every profile read would 500 on the
missing columns.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0083_drop_retired_source_columns'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='completed_qualifications',
            field=models.JSONField(blank=True, db_default=models.Value([], output_field=models.JSONField()), default=list, help_text="Qualifications whose results form was COMPLETED, e.g. ['spm', 'matric']."),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='higher_cgpa',
            field=models.FloatField(blank=True, help_text='Matriculation / Asasi / Diploma CGPA (0-4) AS ENTERED. NULL = none.', null=True),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='higher_institution_type',
            field=models.CharField(blank=True, choices=[('public', 'Public institution'), ('private', 'Private college')], db_default='', default='', help_text="Diploma only: 'public' or 'private'. Only a PUBLIC diploma counts (D5).", max_length=10),
        ),
        migrations.AddField(
            model_name='studentprofile',
            name='higher_koko',
            field=models.FloatField(blank=True, help_text='Matriculation / Asasi co-curriculum score (0-10). NULL for Diploma.', null=True),
        ),
        migrations.AlterField(
            model_name='studentprofile',
            name='exam_type',
            field=models.CharField(choices=[('spm', 'SPM'), ('stpm', 'STPM'), ('matric', 'Matriculation'), ('asasi', 'Asasi (Foundation)'), ('diploma', 'Diploma')], default='spm', max_length=10),
        ),
        migrations.AlterField(
            model_name='studentprofile',
            name='results_exam_type',
            field=models.CharField(blank=True, choices=[('spm', 'SPM'), ('stpm', 'STPM'), ('matric', 'Matriculation'), ('asasi', 'Asasi (Foundation)'), ('diploma', 'Diploma')], default='', help_text="Which exam's results were last COMPLETED. Blank = never recorded.", max_length=10),
        ),
    ]
