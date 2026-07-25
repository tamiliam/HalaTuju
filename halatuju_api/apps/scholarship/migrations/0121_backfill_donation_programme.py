# Funds per programme — backfill (P2, 2026-07-26).
#
# Every donation predating the programme layer was given to the one gift that existed:
# the flagship. Point them at it so no money sits in the NULL bucket, where it would be
# invisible to every programme-scoped balance read and therefore unspendable.
#
# RECONCILIATION INVARIANT: this migration moves no money. The sum of donations before
# and after must be identical — only their attribution changes. The P2 test suite
# asserts this, and the prod runbook re-checks it either side of the apply.
from django.db import migrations

FLAGSHIP_CODE = 'brightpath-flagship'


def backfill_donation_programme(apps, schema_editor):
    Programme = apps.get_model('scholarship', 'Programme')
    Donation = apps.get_model('scholarship', 'Donation')

    programme = Programme.objects.filter(code=FLAGSHIP_CODE).first()
    if programme is None:
        # No flagship (a bare/partial test DB) — leave donations in the NULL bucket
        # rather than inventing a programme to attribute real money to.
        return
    Donation.objects.filter(programme__isnull=True).update(programme=programme)


def unbackfill_donation_programme(apps, schema_editor):
    Programme = apps.get_model('scholarship', 'Programme')
    Donation = apps.get_model('scholarship', 'Donation')
    programme = Programme.objects.filter(code=FLAGSHIP_CODE).first()
    if programme is not None:
        Donation.objects.filter(programme=programme).update(programme=None)


class Migration(migrations.Migration):

    dependencies = [
        ('scholarship', '0120_donation_programme'),
    ]

    operations = [
        migrations.RunPython(backfill_donation_programme, unbackfill_donation_programme),
    ]
