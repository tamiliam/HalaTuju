# Sponsor programme membership — backfill (P3, 2026-07-26).
#
# Every existing sponsor was vetted when the flagship was the only gift, so their existing
# account status IS their flagship acceptance. Mirror it exactly: an approved sponsor gets an
# approved flagship membership, a pending one stays pending, a rejected/suspended one stays so.
#
# INVARIANT: **no sponsor gains or loses visibility.** Because the account-level gate
# (Sponsor.status) is unchanged and each membership copies it, what every existing sponsor can
# see the moment the P3 code deploys is exactly what they could see before. The P3 test suite
# asserts this, and the prod runbook re-checks the per-status counts either side.
from django.db import migrations

FLAGSHIP_CODE = 'brightpath-flagship'


def backfill_memberships(apps, schema_editor):
    Programme = apps.get_model('scholarship', 'Programme')
    Sponsor = apps.get_model('scholarship', 'Sponsor')
    SponsorProgrammeMembership = apps.get_model('scholarship', 'SponsorProgrammeMembership')

    programme = Programme.objects.filter(code=FLAGSHIP_CODE).first()
    if programme is None:
        # No flagship (a bare/partial test DB) — do not invent an acceptance.
        return

    existing = set(
        SponsorProgrammeMembership.objects
        .filter(programme=programme).values_list('sponsor_id', flat=True)
    )
    rows = [
        SponsorProgrammeMembership(
            sponsor=s, programme=programme,
            status=s.status,              # mirror the account status verbatim
            vetted_by='backfill 0123',
            vetted_at=s.created_at,
        )
        for s in Sponsor.objects.all() if s.id not in existing
    ]
    if rows:
        SponsorProgrammeMembership.objects.bulk_create(rows)


def unbackfill_memberships(apps, schema_editor):
    Programme = apps.get_model('scholarship', 'Programme')
    SponsorProgrammeMembership = apps.get_model('scholarship', 'SponsorProgrammeMembership')
    programme = Programme.objects.filter(code=FLAGSHIP_CODE).first()
    if programme is not None:
        SponsorProgrammeMembership.objects.filter(
            programme=programme, vetted_by='backfill 0123',
        ).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0122_sponsor_programme_membership'),
    ]

    operations = [
        migrations.RunPython(backfill_memberships, unbackfill_memberships),
    ]
