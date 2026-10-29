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
500 on the missing column.

RUNBOOK (review round 1, M3/L1):
  1. Apply the SQL above (migrate-first).
  2. Push: the api AND the web build.
  3. CONFIRM BOTH the new api revision AND the new web revision serve 100% of traffic. Only then
     run `ingest_spm_courses --file data/spm/spm_new_courses_D1.json --institution-id UNIV-012`
     (dry run), then the same with `--apply`. An old web bundle sends the student's own Bumiputera
     answer to the scholarship picker's SPM check, which is harmless only while no SPM row is
     Bumi-flagged; an old api image has no gate at all and would show the rows to everyone.
  4. The eligibility frame loads at start-up: the rows show from the NEXT revision (redeploy).
ROLLBACK: delete the D1 rows FIRST, then roll back to a pre-0088 image (an old image would show
them to everyone). In one transaction:

    BEGIN;
    DELETE FROM course_requirements WHERE course_id IN (D1);
    DELETE FROM course_institutions WHERE course_id IN (D1);
    DELETE FROM courses WHERE course_id IN (D1);
    COMMIT;

where (D1) is the 84 ids of data/spm/spm_new_courses_D1.json:
    'UE0222001', 'UE0380001', 'UE0380002', 'UE4343004', 'UE4213001', 'UE4224001',
    'UE4727001', 'UE4726002', 'UE4213004', 'UE4322003', 'UE4723001', 'UE4526003',
    'UE4523001', 'UE4522002', 'UE4524001', 'UE4521001', 'UE4422001', 'UE4621001',
    'UE4321001', 'UE4421001', 'UE4343005', 'UE4724001', 'UE4726001', 'UE4143001',
    'UE4146001', 'UE4343003', 'UE4343002', 'UE4340001', 'UE4340002', 'UE4813001',
    'UE4725002', 'UE4346001', 'UE4221001', 'UE4581002', 'UE4811002', 'UE4620002',
    'UE4322001', 'UE4812001', 'UE4212003', 'UE4813002', 'UE4345001', 'UE4345002',
    'UE4222001', 'UE4344001', 'UE4581003', 'UE4212005', 'UE4214003', 'UE4545004',
    'UE4462002', 'UE4581004', 'UE4481001', 'UE4461001', 'UE4211002', 'UE4811003',
    'UE4215002', 'UE4215001', 'UE4212001', 'UE4811001', 'UE4213005', 'UE4581001',
    'UE4343001', 'UE4462001', 'UE4212004', 'UE4212002', 'UE4620001', 'UE4582001',
    'UE4213002', 'UE4581005', 'UE4545001', 'UE4543001', 'UE4524002', 'UE4213003',
    'UE4541001', 'UE4725001', 'UE4620003', 'UE4213006', 'UE4545003', 'UE4214001',
    'UE4214002', 'UE4214004', 'UE4542001', 'UE4526002', 'UE4526001', 'UE6581001'
The column itself may stay (the old image ignores it, and its inserts take the default).
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
