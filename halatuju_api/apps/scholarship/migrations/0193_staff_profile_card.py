"""Common profile S2 (2026-10-31): every staff member's own card — job title, About, photo, "show my
phone to my team" — and ONE optional fourth language (name + fluency; owner, same day) on the existing
personal-profile row (`reviewer_profiles`; the model is `ReviewerProfile`, aliased `StaffProfile`, NOT
renamed, so no `RenameModel` and no content-type rewrite).

ADDITIVE: six plain ADD COLUMNs, each NOT NULL with its DEFAULT KEPT IN THE DATABASE (`db_default`, so no
`DROP DEFAULT` follows). Postgres fills existing rows from the default without rewriting the table.
NOTHING BACKFILLED, no index, no new table (so no RLS step — the table has had RLS on since F6).

MIGRATE-FIRST, BY HAND, before the push (scholarship ledger 0192 -> 0193). `sqlmigrate` renders for the
LOCAL backend (SQLite), so this is the Postgres DDL to run, verbatim — rendered offline with Django's
postgresql schema editor from this migration — with the ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "reviewer_profiles" ADD COLUMN "about" text DEFAULT '' NOT NULL;
    ALTER TABLE "reviewer_profiles" ADD COLUMN "job_title" varchar(120) DEFAULT '' NOT NULL;
    ALTER TABLE "reviewer_profiles" ADD COLUMN "other_language" varchar(60) DEFAULT '' NOT NULL;
    ALTER TABLE "reviewer_profiles" ADD COLUMN "other_language_fluency" varchar(20) DEFAULT '' NOT NULL;
    ALTER TABLE "reviewer_profiles" ADD COLUMN "photo_path" varchar(255) DEFAULT '' NOT NULL;
    ALTER TABLE "reviewer_profiles" ADD COLUMN "share_phone_with_team" boolean DEFAULT false NOT NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0193_staff_profile_card', now());
    COMMIT;

BETWEEN MIGRATE AND DEPLOY the image already serving never reads these columns, and its
`get_or_create` (which does not name them) still inserts because each default lives in the database
(lessons.md 2026-10-19). Deploying BEFORE migrating is not safe: every read of a profile would 500.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0192_letters'),
    ]

    operations = [
        migrations.AddField(
            model_name='reviewerprofile',
            name='about',
            field=models.TextField(blank=True, db_default='', default='', help_text='Capped at 600 characters by the admin/me/ PATCH.'),
        ),
        migrations.AddField(
            model_name='reviewerprofile',
            name='job_title',
            field=models.CharField(blank=True, db_default='', default='', max_length=120),
        ),
        migrations.AddField(
            model_name='reviewerprofile',
            name='other_language',
            field=models.CharField(blank=True, db_default='', default='', max_length=60),
        ),
        migrations.AddField(
            model_name='reviewerprofile',
            name='other_language_fluency',
            field=models.CharField(blank=True, choices=[('', 'None'), ('conversational', 'Conversational'), ('fluent', 'Fluent')], db_default='', default='', max_length=20),
        ),
        migrations.AddField(
            model_name='reviewerprofile',
            name='photo_path',
            field=models.CharField(blank=True, db_default='', default='', help_text='Key in the private b40-documents bucket; blank = no photo.', max_length=255),
        ),
        migrations.AddField(
            model_name='reviewerprofile',
            name='share_phone_with_team',
            field=models.BooleanField(db_default=False, default=False, help_text='Show this phone on the Team (People) page. Off by default.'),
        ),
    ]
