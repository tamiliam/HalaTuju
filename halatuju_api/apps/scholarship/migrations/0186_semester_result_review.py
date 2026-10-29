"""Student maintenance Sprint 4a (2026-10-29): a funded student's semester result is REVIEWED.

ADDITIVE, five columns on `semester_results`, nothing backfilled (production held no result on
2026-10-29): `review_status` (pending / accepted / queried, DEFAULT 'pending' KEPT IN THE DATABASE —
the old image inserts results without it between the migrate and the deploy), `reviewed_by`,
`reviewed_at`, `review_note` (DEFAULT '' kept for the same reason) and `term_index` (nullable; S4b's
results expectations key on it). No new table, so no RLS step.

MIGRATE-FIRST, BY HAND, before the push (scholarship ledger 0185 -> 0186). `sqlmigrate` renders for
the LOCAL backend (SQLite), so this is the Postgres DDL to run, verbatim — rendered offline with
Django's postgresql schema editor from this migration — with the ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "semester_results" ADD COLUMN "review_note" varchar(500) DEFAULT '' NOT NULL;
    ALTER TABLE "semester_results" ADD COLUMN "review_status" varchar(10) DEFAULT 'pending' NOT NULL;
    ALTER TABLE "semester_results" ADD COLUMN "reviewed_at" timestamp with time zone NULL;
    ALTER TABLE "semester_results" ADD COLUMN "reviewed_by" varchar(254) DEFAULT '' NOT NULL;
    ALTER TABLE "semester_results" ADD COLUMN "term_index" smallint NULL CHECK ("term_index" >= 0);
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0186_semester_result_review', now());
    COMMIT;

⚠ DEPLOYING BEFORE MIGRATING IS NOT SURVIVABLE: the student's results list, every sponsor reader
(they filter `review_status`) and the officer's file read these columns. Migrate first.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0185_receipt_emailed'),
    ]

    operations = [
        migrations.AddField(
            model_name='semesterresult',
            name='review_note',
            field=models.CharField(blank=True, db_default='', default='', max_length=500),
        ),
        migrations.AddField(
            model_name='semesterresult',
            name='review_status',
            field=models.CharField(choices=[('pending', 'Awaiting review'), ('accepted', 'Accepted'), ('queried', 'Queried')], db_default='pending', default='pending', max_length=10),
        ),
        migrations.AddField(
            model_name='semesterresult',
            name='reviewed_at',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='semesterresult',
            name='reviewed_by',
            field=models.CharField(blank=True, db_default='', default='', max_length=254),
        ),
        migrations.AddField(
            model_name='semesterresult',
            name='term_index',
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
    ]
