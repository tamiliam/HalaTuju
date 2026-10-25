"""Request #44 (BrightPath, 2026-10-25): a gift may switch off two of the three fixed "Who referred
you?" choices — `scholarship_programmes.offers_halatuju` (Halatuju.xyz) and `offers_social`
(Facebook / WhatsApp). `other` has no column: it is on every form, always (decisions.md).

ADDITIVE: two plain ADD COLUMNs, boolean NOT NULL with DEFAULT true KEPT IN THE DATABASE
(`db_default`, so no `DROP DEFAULT` follows). Postgres fills existing rows from the default without
rewriting the table, so EVERY EXISTING GIFT READS ON — nothing changes on any form until an admin
switches one off. NOTHING BACKFILLED, no index, no new table (so no RLS step).

MIGRATE-FIRST, BY HAND, before the push (scholarship ledger 0176 -> 0177). `sqlmigrate` renders for
the LOCAL backend (SQLite), so this is the Postgres DDL to run, verbatim - rendered offline with
Django's postgresql schema editor from this migration - with the ledger row in the SAME transaction:

    BEGIN;
    ALTER TABLE "scholarship_programmes" ADD COLUMN "offers_halatuju" boolean DEFAULT true NOT NULL;
    ALTER TABLE "scholarship_programmes" ADD COLUMN "offers_social" boolean DEFAULT true NOT NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('scholarship', '0177_programme_fixed_source_switches', now());
    COMMIT;

BETWEEN MIGRATE AND DEPLOY the image already serving never reads these columns, and its gift create
(which does not name them) still inserts because the default lives in the database. Deploying BEFORE
migrating is not safe: every read of a gift would 500 on the missing columns.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0176_programme_overview_layouts'),
    ]

    operations = [
        migrations.AddField(
            model_name='programme',
            name='offers_halatuju',
            field=models.BooleanField(db_default=True, default=True, help_text="The apply form offers 'Halatuju.xyz' as who referred the student."),
        ),
        migrations.AddField(
            model_name='programme',
            name='offers_social',
            field=models.BooleanField(db_default=True, default=True, help_text="The apply form offers 'Facebook / WhatsApp' as who referred the student."),
        ),
    ]
