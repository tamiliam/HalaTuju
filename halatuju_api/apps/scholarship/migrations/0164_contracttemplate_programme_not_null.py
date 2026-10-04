"""TD-327 (2026-10-04): ``contract_templates.programme_id`` becomes NOT NULL.

0163 (TD-229) added the column NULLABLE only so the migrate-first order could work (the image
before TD-229 inserted templates without it), back-filled every template of the flagship's
organisation onto ``brightpath-flagship``, and changed every write path to set it
(``contracts.create_template`` refuses ``programme_required`` without one). A template with NULL
here governs nobody, so the database now refuses one.

PRODUCTION — MIGRATE-FIRST, BY HAND, BEFORE THE PUSH (``sqlmigrate`` renders SQLite here, so the
Postgres below is hand-written).

1. The PRE-CHECK (read-only). It MUST read 0 — if it does not, STOP: a NULL template exists
   and the ALTER below would fail. Find out who wrote it before doing anything else::

       SELECT count(*) FROM contract_templates WHERE programme_id IS NULL;

2. Then, in ONE transaction::

       BEGIN;
       ALTER TABLE contract_templates ALTER COLUMN programme_id SET NOT NULL;
       INSERT INTO django_migrations (app, name, applied)
            VALUES ('scholarship', '0164_contracttemplate_programme_not_null', now());
       COMMIT;

   ``SET NOT NULL`` scans the table under an ACCESS EXCLUSIVE lock; the table holds a handful of
   rows, so the lock is momentary.

⚠ BETWEEN MIGRATE AND DEPLOY the image already serving (TD-229 onwards) runs against the new
schema, and that is safe: every path in it that creates a template sets ``programme``
(``contracts.create_template`` — the admin screen, ``seed_contract_template`` and
``bursary_e2e`` all go through it). Nothing in it writes NULL. The model change in this commit is
only Django catching up with the column.

Reverse (local only): drops the NOT NULL; nothing to undo in the data.

The RunPython step refuses a non-production database that still holds a NULL template (a bare
database 0163 could not back-fill), with the same pre-check, instead of failing inside the ALTER.
"""
from django.db import migrations, models
import django.db.models.deletion


def refuse_null_templates(apps, schema_editor):
    ContractTemplate = apps.get_model('scholarship', 'ContractTemplate')
    orphans = ContractTemplate.objects.filter(programme__isnull=True).count()
    if orphans:
        raise RuntimeError(
            f'TD-327: {orphans} contract template(s) have no gift (programme_id IS NULL). '
            'Assign each to its gift (or delete an unsigned draft) before 0164 makes the '
            'column NOT NULL.')


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0163_contracttemplate_programme'),
    ]

    operations = [
        migrations.RunPython(refuse_null_templates, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='contracttemplate',
            name='programme',
            field=models.ForeignKey(
                help_text='The gift this agreement is written for. One ACTIVE template per gift.',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='contract_templates', to='scholarship.programme'),
        ),
    ]
