"""Bumi coverage Sprint D1 (owner rulings 2026-10-28/29): `CourseRequirement.req_bumiputera`, the SPM
catalogue's own Bumiputera-only flag (the STPM side has had `StpmRequirement.req_bumiputera` since
launch). True on the UiTM rows Sprint D1 adds; the engine shows such a course only to a Malaysian
who said yes (`apps/courses/bumiputera.py`, `engine.check_eligibility`).

One ADDITIVE column on `course_requirements`, NOT NULL with a DATABASE default of false
(`db_default`), so every existing row reads false and the image still serving — whose inserts do
not name the column — keeps working. No index, no new table (so no RLS step).

MIGRATE-FIRST, BY HAND, before the push (courses ledger 0087 -> 0088). The Postgres DDL, with the
ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "course_requirements" ADD COLUMN "req_bumiputera" boolean DEFAULT false NOT NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0088_courserequirement_req_bumiputera', now());
    COMMIT;

BETWEEN MIGRATE AND DEPLOY the image already serving never reads the column (its `.values()` frame
load just carries one more key, which the old engine ignores), and its inserts succeed because of
the database default. Deploying BEFORE migrating is not safe: every course-requirement read would
500 on the missing column. The UiTM rows themselves are loaded AFTER the deploy, by
`ingest_spm_courses --apply` — never before, or the old image (which has no gate) would show them
to every student.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0087_studentprofile_bumiputera'),
    ]

    operations = [
        migrations.AddField(
            model_name='courserequirement',
            name='req_bumiputera',
            field=models.BooleanField(db_default=False, default=False),
        ),
    ]
