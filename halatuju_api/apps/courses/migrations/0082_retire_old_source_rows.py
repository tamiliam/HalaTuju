"""Sources-and-referrals Sprint D (2026-10-19), the EXPAND half — MIGRATE-FIRST.

1. `partner_organisations.show_in_apply` gets a DATABASE default (false). The Sprint D image no
   longer has the field in its model, so it inserts a `partner_organisations` row (a referral
   partner made by an invite, a tenant made by the organisation form) WITHOUT naming the column;
   the column is NOT NULL with no default today (0065 added it with a Python default only), so
   without this every such insert would fail between the deploy and courses 0083's drop. The old
   image names the column on every insert, so the default changes nothing for it.
2. The SOURCES' OLD ROWS are switched off, never deleted (roadmap item 1; old snapshots name their
   codes). A source's old row is one Sprint B copied into `referral_sources` KEEPING ITS ID, so it
   has a twin with the same id AND the same code there. Retired: such a row that is NOT a referral
   partner (CUMIG's row is the referral partner and stays live) and NOT a tenant. Nothing reads
   these rows since Sprint B; switching them off makes the category plain (`is_active` false) and
   keeps them out of anything that ever lists active rows.
3. (Review fix.) A student linked to a REFERRAL PARTNER gets that partner's code on the chip
   (`align_partner_chips`): the bursary used to write its answer there, and the chip is the
   partner dashboard's Source column — so no bursary answer stays visible to the partner's logins.

SQL (rendered offline; the hand-applied copy with its asserting DO block and ledger row is in
`docs/scholarship/sources-d-cutover-sql.md`):
    ALTER TABLE "partner_organisations" ALTER COLUMN "show_in_apply" SET DEFAULT false;
    UPDATE partner_organisations o SET is_active = false
     WHERE o.is_active AND NOT o.is_referral_partner
       AND EXISTS (SELECT 1 FROM referral_sources s WHERE s.id = o.id AND s.code = o.code)
       AND NOT <tenant>;
    -- 3. (review fix) a referral partner's students show that partner's code on the chip:
    UPDATE api_student_profiles p SET referral_source = o.code FROM partner_organisations o
     WHERE p.referred_by_org_id = o.id AND o.is_referral_partner
       AND p.referral_source IS DISTINCT FROM o.code;      -- after a dated backup table
    INSERT INTO django_migrations (app, name, applied)
      VALUES ('courses', '0082_retire_old_source_rows', now());

Reverse: the default is dropped by Django's reverse of the AlterField; the retirement and the chip
alignment are NOT undone automatically (no-ops) — the cutover note records the retired ids and backs
the old chips up (`referral_chip_backup_20261019`), and the rollback there restores exactly those.
"""
from django.db import migrations, models


def retire_old_source_rows(apps, schema_editor):
    """Switch off every source's old `partner_organisations` row (same id AND code in
    `referral_sources`) that is neither a referral partner nor a tenant. Idempotent. Returns the
    retired ids (for the test)."""
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    PartnerAdmin = apps.get_model('courses', 'PartnerAdmin')
    ReferralSource = apps.get_model('scholarship', 'ReferralSource')
    Programme = apps.get_model('scholarship', 'Programme')
    tenant_ids = set(Programme.objects.filter(is_active=True).values_list('organisation_id', flat=True))
    tenant_ids |= set(PartnerAdmin.objects.filter(role='org_admin', is_active=True)
                      .values_list('owning_organisation_id', flat=True))
    twins = set(ReferralSource.objects.values_list('id', 'code'))
    retire = [o.pk for o in PartnerOrganisation.objects.filter(is_active=True, is_referral_partner=False)
              .only('id', 'code')
              if (o.pk, o.code) in twins and o.pk not in tenant_ids]
    PartnerOrganisation.objects.filter(pk__in=retire).update(is_active=False)
    return retire


def align_partner_chips(apps, schema_editor):
    """Sprint D review fix: the chip of a student linked to a REFERRAL PARTNER becomes that partner's
    code. Before Sprint D the bursary submit wrote its answer onto the chip, so a few such students
    show a bursary answer on the partner's Source column (production 2026-10-19: 1 of 254, `social`).
    From now on only the `?ref=` link writes the chip, and for a linked student the link's code IS
    the partner's code. The cutover backs the old values up first. Idempotent; returns the profile
    ids changed (for the test)."""
    StudentProfile = apps.get_model('courses', 'StudentProfile')
    PartnerOrganisation = apps.get_model('courses', 'PartnerOrganisation')
    changed = []
    for partner in PartnerOrganisation.objects.filter(is_referral_partner=True):
        stale = (StudentProfile.objects.filter(referred_by_org_id=partner.pk)
                 .exclude(referral_source=partner.code))
        ids = list(stale.values_list('pk', flat=True))
        StudentProfile.objects.filter(pk__in=ids).update(referral_source=partner.code)
        changed += ids
    return changed


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0081_partneradmin_permissions'),
        ('scholarship', '0174_application_source'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partnerorganisation',
            name='show_in_apply',
            field=models.BooleanField(default=False, db_default=False),
        ),
        migrations.RunPython(retire_old_source_rows, migrations.RunPython.noop),
        migrations.RunPython(align_partner_chips, migrations.RunPython.noop),
    ]
