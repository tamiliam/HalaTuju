"""Request #39, Sprint 1 (staff permissions, 2026-10-19): `PartnerAdmin.permissions`, a nullable list of
staff permission keys (`apps/courses/staff_permissions.py`).

ADDITIVE: one NULLABLE JSON column, NO default, NO backfill. NULL means "the preset of `role`", so every
existing staff member keeps exactly what they can do today without anyone writing a value, and every
future invitee gets their preset the same way. Nothing writes this column in Sprint 1 (the editor is
Sprint 4), and no gate reads it yet.

⚠ MIGRATE-FIRST, by hand, before the push, then record the `django_migrations` row (courses ledger
0080 -> 0081).

⚠ HAND-WRITTEN POSTGRES DDL — do NOT paste `sqlmigrate`, which renders for the LOCAL backend (SQLite)
and prints a whole table rebuild for what is one ALTER on Postgres (the scholarship 0154 / 0171
convention):

    ALTER TABLE "partner_admins" ADD COLUMN "permissions" jsonb NULL;
    INSERT INTO django_migrations (app, name, applied) VALUES ('courses', '0081_partneradmin_permissions', now());

Why migrate-first is safe in both directions: the image already serving does not know the column and
its INSERTs (invite, re-invite) never name it, so a staff row created in the window arrives NULL —
which is "the preset", exactly right. The NEW image selects the column on every staff read (Django
selects every field, and `get_admin` runs on every console request), so deploying BEFORE migrating
would 500 the whole console.

No RLS step: a column on an existing table inherits that table's policies. No index: the column is
read per row, never filtered on (`staff_permissions.holders` filters in Python, because JSONField
`__contains` is not supported on SQLite, which the tests run on).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0080_drop_partner_organisation_programme'),
    ]

    operations = [
        migrations.AddField(
            model_name='partneradmin',
            name='permissions',
            field=models.JSONField(blank=True, help_text='Staff permission keys (staff_permissions.CATALOGUE). NULL = the preset of role, which is the default. Read through has_perm, never directly.', null=True),
        ),
    ]
