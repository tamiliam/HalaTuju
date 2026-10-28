"""Bumi coverage Sprint B (owner ruling 2026-10-28): the student's own Bumiputera answer, for the
COURSE GUIDE ONLY — it unlocks Bumiputera-only courses (UiTM, MARA) for students who say yes. It
is never read by the scholarship app, sponsor views, reports or partner exports (s44(6) stance).
NULL = not answered, or not Malaysian. Every rule about it is in `apps/courses/bumiputera.py`.

One ADDITIVE, NULLABLE column on `api_student_profiles`. No default in the database, no index, no
new table (so no RLS step).

MIGRATE-FIRST, BY HAND, before the push (courses ledger 0086 -> 0087). The Postgres DDL, with the
ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "api_student_profiles" ADD COLUMN "bumiputera" boolean NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0087_studentprofile_bumiputera', now());
    COMMIT;

BETWEEN MIGRATE AND DEPLOY the image already serving never reads the column, and its inserts (which
do not name it) succeed because it is nullable. Deploying BEFORE migrating is not safe: every
profile read would 500 on the missing column.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0086_studentprofile_stpm_koko_unconfirmed'),
    ]

    operations = [
        migrations.AddField(
            model_name='studentprofile',
            name='bumiputera',
            field=models.BooleanField(blank=True, default=None, null=True),
        ),
    ]
