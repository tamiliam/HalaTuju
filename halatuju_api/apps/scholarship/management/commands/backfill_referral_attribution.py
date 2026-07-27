"""
One-off: close the invitations that were answered by a DIRECT sign-up.

Until 2026-07-28 a referral was attributed only when the invitee came back through the
``/sponsor?ref=<code>`` link. Most people didn't — they read the invite and then registered
on their own — so every one of those rows sat at "Invited" for ever and a real conversion
read as none. ``referrals.attribute_referral_by_email`` fixes it from now on; this command
repairs the history that accumulated before it.

Matching is the same as the live path (invitee email, still-``invited`` row, never a
self-referral) plus ONE extra guard the live path does not need: the sponsor must have
registered AFTER the invitation went out. At registration time that is true by
construction; reading history it is not, and someone who was already a sponsor before
being invited is not a conversion of that invite.

``joined_at`` is stamped with the sponsor's own ``created_at`` — the real moment they
joined — not today, so the record stays honest about when it happened.

    python manage.py backfill_referral_attribution            # report only
    python manage.py backfill_referral_attribution --apply
"""
from django.core.management.base import BaseCommand
from django.db import connection

from apps.scholarship import referrals as referral_service
from apps.scholarship.models import Sponsor, SponsorReferral


class Command(BaseCommand):
    help = "Close still-'invited' referrals whose invitee has since registered directly."

    def add_arguments(self, parser):
        parser.add_argument('--apply', action='store_true',
                            help='Write the attributions. Without it, report only.')

    def handle(self, *args, **options):
        apply = options['apply']
        db = connection.settings_dict
        self.stdout.write(f"DB: {db.get('ENGINE')} -> {db.get('HOST') or db.get('NAME')}")

        # One pass over the sponsors, keyed by email, so this is two queries not N.
        by_email = {}
        for s in Sponsor.objects.exclude(email='').order_by('created_at', 'id'):
            by_email.setdefault((s.email or '').strip().lower(), s)

        pending = (SponsorReferral.objects
                   .filter(status='invited')
                   .exclude(invitee_email='')
                   .select_related('inviter')
                   .order_by('created_at', 'id'))

        matched = skipped_self = skipped_early = 0
        for referral in pending:
            sponsor = by_email.get((referral.invitee_email or '').strip().lower())
            if sponsor is None:
                continue
            if sponsor.id == referral.inviter_id:
                skipped_self += 1
                continue
            if sponsor.created_at and referral.created_at and sponsor.created_at < referral.created_at:
                self.stdout.write(
                    f"  skip referral #{referral.id} ({referral.invitee_email}) — sponsor #{sponsor.id} "
                    f"registered {sponsor.created_at:%Y-%m-%d}, BEFORE the invite "
                    f"({referral.created_at:%Y-%m-%d})"
                )
                skipped_early += 1
                continue
            self.stdout.write(
                f"  {'' if apply else '[report] '}referral #{referral.id} "
                f"({referral.invitee_name or referral.invitee_email}) invited by "
                f"{referral.inviter.name if referral.inviter else '?'} -> joined as "
                f"sponsor #{sponsor.id} on {sponsor.created_at:%Y-%m-%d}"
            )
            if apply:
                referral_service._mark_joined(referral, sponsor, when=sponsor.created_at)
            matched += 1

        self.stdout.write(self.style.SUCCESS(
            f"{matched} referral(s) {'attributed' if apply else 'would be attributed'}; "
            f"{skipped_self} self-referral(s) and {skipped_early} pre-dating sponsor(s) left alone."
        ))
        if matched and not apply:
            self.stdout.write("Re-run with --apply to write them.")
