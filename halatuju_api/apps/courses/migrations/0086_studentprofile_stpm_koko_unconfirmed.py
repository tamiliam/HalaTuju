"""STPM CGPA sprint C4 (owner ruling 2026-10-28): a marker for an STPM co-curriculum score the C2
backfill could NOT work back cleanly from the old stored figure. TRUE raises the Check-2 ask
`stpm_koko_confirm` (`apps/scholarship/stpm_asks.py`); it is set by the one-off command
`flag_stpm_koko_unconfirmed` for the application ids the lead passes, and CLEARED (FALSE) when the
student saves a co-curriculum score through the onboarding STPM step (the profile writer). NULL =
never flagged. Roadmap: docs/plans/2026-10-28-stpm-cgpa-from-grades-roadmap.md.

One ADDITIVE, NULLABLE column on `api_student_profiles`. No default, no index, no new table (so no
RLS step).

MIGRATE-FIRST, BY HAND, before the push (courses ledger 0085 -> 0086). The Postgres DDL, with the
ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "api_student_profiles" ADD COLUMN "stpm_koko_unconfirmed" boolean NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0086_studentprofile_stpm_koko_unconfirmed', now());
    COMMIT;

BETWEEN MIGRATE AND DEPLOY the image already serving never reads the column, and its inserts (which
do not name it) succeed because it is nullable. Deploying BEFORE migrating is not safe: every
profile read would 500 on the missing column.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0085_studentprofile_stpm_koko'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='stpm_koko_unconfirmed',
            field=models.BooleanField(
                blank=True,
                help_text='TRUE: the stored STPM co-curriculum score was derived, not cleanly; the student is asked to confirm it. Cleared when they save one through onboarding.',
                null=True,
            ),
        ),
    ]
