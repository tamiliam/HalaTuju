"""STPM CGPA sprint C2 (owner ruling 2026-10-28: CGPA and merit are different): the STPM
co-curriculum score, stored for the MERIT only — `stpm_pngk.stpm_merit_overall` =
`exam_questions.overall_from(PNGK, stpm_koko)`. The onboarding step already asked for it; the server
never kept it. Roadmap: docs/plans/2026-10-28-stpm-cgpa-from-grades-roadmap.md.

One ADDITIVE, NULLABLE column on `api_student_profiles`. No default, no index, no new table (so no
RLS step). Existing rows read NULL until `backfill_stpm_cgpa --apply` derives each STPM student's
score from the stored figure (the backfill's docstring has the rule).

MIGRATE-FIRST, BY HAND, before the push (courses ledger 0084 -> 0085). The Postgres DDL, with the
ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "api_student_profiles" ADD COLUMN "stpm_koko" double precision NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0085_studentprofile_stpm_koko', now());
    COMMIT;

BETWEEN MIGRATE AND DEPLOY the image already serving never reads the column, and its inserts (which
do not name it) succeed because it is nullable. Deploying BEFORE migrating is not safe: every
profile read would 500 on the missing column.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0084_third_results_route'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='stpm_koko',
            field=models.FloatField(
                blank=True,
                help_text='STPM co-curriculum score (0-10): merit only, never the CGPA (stpm_pngk.stpm_merit_overall).',
                null=True,
            ),
        ),
    ]
