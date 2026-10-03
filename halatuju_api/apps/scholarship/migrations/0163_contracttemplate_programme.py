"""TD-229 (2026-10-03): the bursary agreement template belongs to a GIFT, not to the organisation.

Owner ruling 2026-09-04 ("the template is PER GIFT"). Three steps, in this order:

  1. ``contract_templates.programme_id`` — a NULLABLE FK to ``scholarship_programmes`` (PROTECT).
  2. BACK-FILL, explicitly: every template of the organisation that runs the flagship gift
     (``code = 'brightpath-flagship'``) is set to that gift. A second gift starts with NONE, so
     nobody signs wording that was not written for them.
  3. A partial unique index: at most ONE ``status = 'active'`` template per programme.

⚠ THERE WAS NO ORGANISATION-LEVEL INDEX TO DROP. "Exactly one active per organisation" lived only
in ``contracts.deploy`` (it archived the previous active row); 0103 created no partial index. So
this ADDS the per-gift index; it swaps nothing. The org/version unique constraint stays — a
version label is still unique within the organisation, across its gifts.

⚠ NULLABLE DELIBERATELY, AND A TIGHTENING IS OWED (TD-327). The column must be nullable for the
migrate-first order below (the old image creates templates without it). After the back-fill no
row should be NULL and every write path in this change sets it; a template left NULL governs
nobody (``contract_scope.active_template_for`` cannot reach it, ``contracts.deploy`` refuses it).
Once production reads 0 NULL rows, TD-327 makes the column NOT NULL.

PRODUCTION — MIGRATE-FIRST, BY HAND, BEFORE THE PUSH (``sqlmigrate`` renders SQLite here, so the
Postgres below is hand-written). Run the read-only probe in ``halatuju_api/CLAUDE.md`` (Next
Sprint, NOW SPRINT 5 PART 1) first. Then, in ONE transaction::

    BEGIN;
    ALTER TABLE contract_templates
        ADD COLUMN programme_id bigint NULL
        REFERENCES scholarship_programmes (id) DEFERRABLE INITIALLY DEFERRED;
    CREATE INDEX contract_templates_programme_id_4ed8c6f0 ON contract_templates (programme_id);

    -- The back-fill. The gift by its CODE (with the alias table as a fallback, in case the
    -- flagship's code was ever renamed) and the templates by the gift's ORGANISATION — never
    -- by id literals, which differ between databases.
    UPDATE contract_templates AS t
       SET programme_id = p.id
      FROM scholarship_programmes AS p
     WHERE p.id = COALESCE(
               (SELECT id FROM scholarship_programmes WHERE code = 'brightpath-flagship'),
               (SELECT programme_id FROM scholarship_programme_code_aliases
                 WHERE code = 'brightpath-flagship'))
       AND t.organisation_id = p.organisation_id
       AND t.programme_id IS NULL;

    -- ⚠ The FK above is DEFERRABLE INITIALLY DEFERRED, so the UPDATE leaves PENDING TRIGGER
    -- EVENTS and Postgres refuses `CREATE INDEX ... because it has pending trigger events`. The
    -- first production run (2026-10-03) hit exactly this and rolled back cleanly. Settle them:
    SET CONSTRAINTS ALL IMMEDIATE;

    -- Must succeed: it fails (and the transaction rolls back) if the flagship ever had two
    -- ACTIVE templates, which `contracts.deploy` has never allowed. The probe counts them first.
    CREATE UNIQUE INDEX uniq_contract_template_active_per_programme
        ON contract_templates (programme_id) WHERE status = 'active';

    INSERT INTO django_migrations (app, name, applied)
         VALUES ('scholarship', '0163_contracttemplate_programme', now());
    COMMIT;

Then re-run the probe: every template of the flagship's organisation must now carry the
flagship's id, and ``programme_id IS NULL`` must count 0.

⚠ BETWEEN MIGRATE AND DEPLOY the OLD image runs against the new schema, and that is safe: it
never names ``programme_id`` (nullable, so its inserts succeed — a template it creates lands
NULL and would need the same UPDATE), and it still resolves the agreement by ORGANISATION, which
is what production did yesterday. ``BURSARY_AGREEMENT_ENABLED`` is OFF, so nothing signs. The
one thing the old image could do that the index refuses is deploy a second active template for
the flagship — which its own ``deploy`` prevents by archiving the previous one first.

⛔ SO: NO TEMPLATE AUTHORING OR DEPLOYING BETWEEN THE MIGRATION AND THE CODE DEPLOY. A template the
old image creates lands NULL, and the old ``deploy`` archives by ORGANISATION — deploying it would
archive the flagship's active template and activate one that governs nobody under the new code.
Re-run the NULL count after the deploy too.

Reverse (local only): drops the index and the column; the back-fill has nothing to undo.
"""
from django.db import migrations, models
import django.db.models.deletion

FLAGSHIP_CODE = 'brightpath-flagship'


def backfill_flagship_templates(apps, schema_editor):
    """The same back-fill as the hand-written UPDATE above, for every non-production database."""
    Programme = apps.get_model('scholarship', 'Programme')
    ProgrammeCodeAlias = apps.get_model('scholarship', 'ProgrammeCodeAlias')
    ContractTemplate = apps.get_model('scholarship', 'ContractTemplate')

    flagship = Programme.objects.filter(code=FLAGSHIP_CODE).first()
    if flagship is None:
        alias = ProgrammeCodeAlias.objects.filter(code=FLAGSHIP_CODE).first()
        flagship = alias.programme if alias is not None else None
    if flagship is None:
        # A bare database with no flagship: leave every template NULL rather than invent a gift.
        return
    ContractTemplate.objects.filter(
        organisation_id=flagship.organisation_id, programme__isnull=True,
    ).update(programme=flagship)


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0162_applicantdocument_order_tie_break_on_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='contracttemplate',
            name='programme',
            field=models.ForeignKey(
                blank=True, null=True,
                help_text='The gift this agreement is written for. One ACTIVE template per gift.',
                on_delete=django.db.models.deletion.PROTECT,
                related_name='contract_templates', to='scholarship.programme'),
        ),
        migrations.RunPython(backfill_flagship_templates, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name='contracttemplate',
            constraint=models.UniqueConstraint(
                condition=models.Q(('status', 'active')), fields=('programme',),
                name='uniq_contract_template_active_per_programme'),
        ),
    ]
