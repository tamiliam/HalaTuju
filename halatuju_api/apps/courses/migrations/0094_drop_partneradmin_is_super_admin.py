"""TD-064 follow-up (2026-11-08): the `partner_admins.is_super_admin` column leaves a fresh database too.

0093 (STEP 1) took the field out of Django's state and kept the column; the owner dropped the column by
hand on production (STEP 2). This is the migration the 0093 docstring promised so a database built from
the migrations matches production:

- STATE: the field was already removed by 0093, so there is nothing to remove from state (a second
  RemoveField would fail). This migration therefore carries a database operation only, inside
  SeparateDatabaseAndState with empty state operations, to make the intent explicit.
- DATABASE: `DROP COLUMN IF EXISTS` on PostgreSQL (a column check first on SQLite, which has no IF EXISTS), so on production (column already dropped by hand) it is a no-op
  and the ledger row is all the owner records.

Production SQL (ledger only, the column is already gone):

    INSERT INTO django_migrations (app, name, applied)
    SELECT 'courses', '0094_drop_partneradmin_is_super_admin', now()
    WHERE NOT EXISTS (SELECT 1 FROM django_migrations
                      WHERE app = 'courses' AND name = '0094_drop_partneradmin_is_super_admin');

Reverse: a no-op (the column is not recreated; 0093's reverse is not reachable past STEP 2).
"""
from django.db import migrations


def drop_column_if_present(apps, schema_editor):
    """PostgreSQL: DROP COLUMN IF EXISTS. SQLite (tests) has no IF EXISTS there, so look first."""
    conn = schema_editor.connection
    if conn.vendor == 'postgresql':
        schema_editor.execute('ALTER TABLE partner_admins DROP COLUMN IF EXISTS is_super_admin')
        return
    with conn.cursor() as cur:
        cols = [c.name for c in conn.introspection.get_table_description(cur, 'partner_admins')]
    if 'is_super_admin' in cols:
        schema_editor.execute('ALTER TABLE partner_admins DROP COLUMN is_super_admin')


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0093_retire_partneradmin_is_super_admin'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(drop_column_if_present, migrations.RunPython.noop),
            ],
            state_operations=[],
        ),
    ]
