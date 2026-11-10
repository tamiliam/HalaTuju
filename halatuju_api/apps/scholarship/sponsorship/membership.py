"""Sponsorship: a benefactor's membership of a gift (synced from the account, or set by hand).

Moved unchanged out of ``sponsorship.py`` when audit A3.8 (2026-11-10) made it a package.
"""
from django.db import transaction
from django.utils import timezone


def sync_account_membership(sponsor, programme, vetted_by=''):
    """Create or refresh this sponsor's membership of ONE gift, mirroring their ACCOUNT status.

    ⚠ `programme` IS REQUIRED AND POSITIONAL, with no default. That is the P2a discipline the money
    model already uses (`sponsor_balance`, `payments.create_run`): a default would compile, pass
    every test written before a second gift existed, and quietly file somebody against the wrong
    one. **None is handled here** — it writes nothing rather than falling back. Registration and
    vetting call it through `sponsor_signup.open_signup_memberships` / `settle_signup_memberships`.

    Migration ``0123`` gave every sponsor alive on 2026-07-25 a flagship membership copied from
    their account status — and **nothing was ever written to do the same for a sponsor who
    registers afterwards**. The first one to arrive (28/07) landed with zero memberships, which
    made them invisible to ``pool.for_sponsor`` (an empty student pool, no digest — see
    ``sponsor_notifications``) and un-creditable, because ``record_admin_credit`` refuses
    ``sponsor_not_in_programme``. This is that missing write.

    It mirrors ``0123`` EXACTLY — same programme, same "the membership copies the account
    status" rule — so a sponsor who registers today ends in the state they would have been in
    had they registered a week earlier. Called from registration (which opens it ``pending``)
    and from vetting (which settles it), and it is idempotent, so calling it on an existing
    sponsor heals a missing row rather than duplicating one.

    **Only the ONE gift passed in is touched, and that rule predates the parameter.** A membership
    of another gift is a separate acceptance decision by the organisation running it, and must
    never be flipped as a side-effect of platform-level account vetting. Vetting therefore passes
    the SAME gifts the registration resolved (`signup_programmes_for` is stable — the invitation
    outlives the registration), so the account's own rows settle and nobody else's moves.

    Best-effort: an unresolvable programme (a bare test DB, as ``0123`` allows) returns None rather
    than inventing an acceptance — but database errors are NOT swallowed.
    """
    from ..models import SponsorProgrammeMembership
    if programme is None:
        return None
    settled = sponsor.status != 'pending'
    # ⚠ LOCKED and decided under the lock, as in `set_programme_membership` (I3 third review): a
    # concurrent Take back and account approval cannot end at `approved`. No savepoint, no query.
    with transaction.atomic(savepoint=False):
        membership, created = SponsorProgrammeMembership.objects.select_for_update().get_or_create(
            sponsor=sponsor, programme=programme,
            defaults={
                'status': sponsor.status,
                'vetted_by': vetted_by if settled else '',
                'vetted_at': timezone.now() if settled else None,
            },
        )
        # ⚠ A GIFT REJECTED BY HAND (`rejected_by_hand_at`) IS NEVER CHANGED BY ACCOUNT VETTING;
        # a cascaded rejection follows the account back. `record_admin_credit` reads this row.
        by_hand = membership.status == 'rejected' and membership.rejected_by_hand_at is not None
        if not created and membership.status != sponsor.status and not by_hand:
            membership.status = sponsor.status
            membership.vetted_by = vetted_by
            membership.vetted_at = timezone.now()
            membership.save(update_fields=['status', 'vetted_by', 'vetted_at', 'updated_at'])
    return membership


MEMBERSHIP_STATUSES = ('pending', 'approved', 'rejected', 'suspended')


class MembershipError(Exception):
    """Raised with a machine-readable code the endpoint turns into a 400."""


def set_programme_membership(sponsor, programme, status, vetted_by=''):
    """An organisation ACCEPTS a benefactor into one of its gifts — or takes it back.

    ⚠ THIS IS THE VERB THAT UNBLOCKS THE MONEY. `record_admin_credit` refuses
    `sponsor_not_in_programme` unless an APPROVED row exists here, and until today nothing but a
    migration and a hard-coded flagship literal could write one. A gift's first benefactor could
    not be recorded without an engineer.

    ⚠ IT IS A DELIBERATE, PER-GIFT DECISION AND MUST STAY SEPARATE FROM ACCOUNT VETTING. The
    account gate ("is this a real, legitimate person") is `Sponsor.status` and is settled once,
    platform-wide; this is the second gate, and the owner's rule for it is that a sponsor sees a
    gift's students only if they were *"specifically onboarded into both and accepted into both —
    and that is not a given"*. So approving somebody here says nothing about any other gift, and
    `sync_account_membership` deliberately touches only the one gift a registration resolved.

    ⚠ THE POOL IS FAIL-CLOSED AND THIS DOES NOT CHANGE THAT. Visibility narrows through the single
    seam `pool.for_sponsor` / `pool.approved_programme_ids`, which every one of the five
    sponsor-facing channels already uses — list, detail, the weekly digest, the real-time alert and
    standing gifts. This writes the row that seam reads; it adds no channel and bypasses none. Do
    not add a sixth reader without extending P3's source guard.

    The caller is responsible for the ORGANISATION fence: `programme` must belong to the admin's
    own organisation, which the endpoint checks by resolving it through `_programmes_for`.
    """
    from ..models import SponsorProgrammeMembership
    if programme is None:
        raise MembershipError('programme_required')
    if status not in MEMBERSHIP_STATUSES:
        raise MembershipError('bad_status')
    # ⚠ THE ACCOUNT GATE COMES FIRST AND IS NOT NEGOTIABLE HERE. Accepting an unvetted or rejected
    # account into a gift would produce a row that reads "approved" while `Sponsor.status` still
    # refuses them everything — a screen saying yes and a system saying no. Vet the account, then
    # accept them into the gift.
    if status == 'approved' and sponsor.status != 'approved':
        raise MembershipError('account_not_approved')

    settled = status != 'pending'
    # BY HAND: a rejection is stamped, so account vetting never overturns it; any other status
    # clears the stamp. Locked and decided under the lock (I3 reviews; `sync_account_membership`).
    hand = timezone.now() if status == 'rejected' else None
    with transaction.atomic(savepoint=False):
        membership, created = SponsorProgrammeMembership.objects.select_for_update().get_or_create(
            sponsor=sponsor, programme=programme,
            defaults={
                'status': status,
                'vetted_by': vetted_by if settled else '',
                'vetted_at': timezone.now() if settled else None,
                'rejected_by_hand_at': hand,
            },
        )
        stamped = membership.rejected_by_hand_at is not None
        if not created and (membership.status, stamped) != (status, hand is not None):
            membership.status, membership.rejected_by_hand_at = status, hand
            membership.vetted_by = vetted_by if settled else ''
            membership.vetted_at = timezone.now() if settled else None
            membership.save(update_fields=['status', 'vetted_by', 'vetted_at',
                                           'rejected_by_hand_at', 'updated_at'])
    return membership
