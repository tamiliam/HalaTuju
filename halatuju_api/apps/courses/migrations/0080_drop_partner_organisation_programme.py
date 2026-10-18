"""TD-379 contract (sources-and-referrals Sprint B, 2026-10-18): drop the deprecated single-gift
`partner_organisations.programme_id` column.

Nothing has read or written it since per-gift sources Sprint 1 (2026-10-08, scholarship 0172 seeded
`programme_referral_sources` from it); this sprint's image no longer has the field in its model.

⚠ IMAGE-FIRST — THE OPPOSITE OF MIGRATE-FIRST. Every image before this sprint SELECTs the column
(it is in `PartnerOrganisation`'s field list, so every read of the table names it): dropping it
while such an image serves 500s every organisation read. So the order is:
1. scholarship 0173 + courses 0079 by hand (migrate-first), push, and confirm the new revision is
   the one serving (`status.latestReadyRevisionName`);
2. THEN, and only then, this drop by hand with its ledger row — the "AFTER DEPLOY" section of
   `docs/scholarship/sources-b-cutover-sql.md`.
A rollback to a pre-Sprint-B image is impossible once this has run; that is the trigger TD-379
waited for (S1 + S2 live since 2026-10-09, no source incident since).
"""
from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0079_student_source_to_referral_sources'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='partnerorganisation',
            name='programme',
        ),
    ]
