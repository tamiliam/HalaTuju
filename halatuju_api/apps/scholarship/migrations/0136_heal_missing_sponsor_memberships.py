# Sponsor programme membership — heal the ones migration 0123 could not reach (2026-07-29).
#
# 0123 backfilled a flagship membership for every sponsor alive on 2026-07-25, mirroring their
# account status. No code was ever written to do the same for a sponsor registering AFTER it, so
# everyone who joined in the gap holds ZERO memberships — invisible to `pool.for_sponsor` (an
# empty student pool, no digest) and un-creditable (`record_admin_credit` refuses
# `sponsor_not_in_programme`). On production that is sponsor 10, who registered on 28/07.
#
# The write path is fixed in the same change (`sponsorship.sync_account_membership`, called from
# registration and from vetting), so this closes the window rather than becoming a habit.
#
# INVARIANT, same as 0123: **no sponsor gains or loses visibility beyond what their ACCOUNT
# status already grants.** Each healed row copies `Sponsor.status` verbatim, so a pending or
# rejected sponsor gets a pending or rejected membership and sees nothing new. Only sponsors with
# NO row for the flagship are touched — an existing membership is never overwritten, because by
# then it may carry a real acceptance decision.
from django.db import migrations

FLAGSHIP_CODE = 'brightpath-flagship'


def heal_memberships(apps, schema_editor):
    Programme = apps.get_model('scholarship', 'Programme')
    Sponsor = apps.get_model('scholarship', 'Sponsor')
    SponsorProgrammeMembership = apps.get_model('scholarship', 'SponsorProgrammeMembership')

    programme = Programme.objects.filter(code=FLAGSHIP_CODE).first()
    if programme is None:
        # No flagship (a bare/partial test DB) — do not invent an acceptance.
        return

    have = set(
        SponsorProgrammeMembership.objects
        .filter(programme=programme).values_list('sponsor_id', flat=True)
    )
    rows = [
        SponsorProgrammeMembership(
            sponsor=s, programme=programme,
            status=s.status,              # mirror the account status verbatim
            vetted_by='heal 0136',
            vetted_at=s.reviewed_at or s.created_at,
        )
        for s in Sponsor.objects.all() if s.id not in have
    ]
    if rows:
        SponsorProgrammeMembership.objects.bulk_create(rows)


def unheal_memberships(apps, schema_editor):
    SponsorProgrammeMembership = apps.get_model('scholarship', 'SponsorProgrammeMembership')
    SponsorProgrammeMembership.objects.filter(vetted_by='heal 0136').delete()


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0135_application_catalogue'),
    ]

    operations = [
        migrations.RunPython(heal_memberships, unheal_memberships),
    ]
