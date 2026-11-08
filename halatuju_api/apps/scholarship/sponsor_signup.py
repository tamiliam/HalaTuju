"""Which gifts a REGISTERING sponsor joins, and the memberships registration opens and account vetting
settles (Invitations I3, 2026-11-08).

Moved here, unchanged, from `sponsorship.py` when the merge of main put that file over its
`oversize_files` allowance (2026-11-08). The per-gift writers stay in `sponsorship.py`:
`sync_account_membership` (account vetting, one gift; it never overturns a rejection by hand) and
`set_programme_membership` (the organisation's own acceptance). This module only decides WHICH gifts
and calls the first; it writes no membership status of its own except registration's create-only
PENDING row.
"""
from django.utils import timezone

from .sponsorship import sync_account_membership


def signup_programmes_for(sponsor, *, freeze=False):
    """WHICH GIFTS a registering sponsor is joining — a list, empty when we genuinely cannot say.

    ⚠ THIS REPLACED A TENANT LITERAL (``DEFAULT_PROGRAMME_CODE = 'brightpath-flagship'``, until
    2026-09-04), which filed a benefactor invited into Sabah against the flagship and then refused
    their credit (``record_admin_credit`` → ``sponsor_not_in_programme``). Since Invitations I3
    (2026-11-08) an invitation names several gifts or Every gift, so the answer is a list.

    Two sources, in order, and both are EVIDENCE rather than a guess:

    1. **The invitation they answered** (`sponsor_invite_gifts.stating_invitation`), matched on
       email — a sponsor invitation creates no account, so the address is the only thread (the key
       ``_close_admin_invitation`` uses). Its gifts, or for Every gift each gift active in its
       organisation when first resolved — ONCE, by ``freeze`` (registration, or vetting for an
       invitation never frozen), even to none; after that every read returns what was frozen.
    2. **The platform's sole ACTIVE gift.** With one there is nothing to get wrong. ``is_active``:
       a gift created but not switched on takes nobody, so it must not make the answer ambiguous.

    ⚠ EMPTY IS A REAL ANSWER AND MUST STAY ONE. Several active gifts and no invitation means a
    stranger off the public form: guessing files them — and their money — against the wrong gift;
    ``[]`` leaves them with no membership and an org_admin who accepts them by hand. PF-1's rule.
    """
    from .models import Programme
    from . import sponsor_invite_gifts
    invited = sponsor_invite_gifts.stating_invitation(getattr(sponsor, 'email', ''))
    if invited is not None:
        return sponsor_invite_gifts.joined_on_registration(invited, freeze=freeze)
    live = list(Programme.objects.filter(is_active=True)[:2])
    return live if len(live) == 1 else []


def open_signup_memberships(sponsor):
    """REGISTRATION: one membership per gift they are joining, opened at the account's status
    (``pending`` for a newcomer). CREATE-ONLY: an existing row of any status is left alone, so a
    registration can never downgrade an approved, rejected or suspended membership (I3)."""
    from .models import SponsorProgrammeMembership
    for programme in signup_programmes_for(sponsor, freeze=True):
        settled = sponsor.status != 'pending'
        SponsorProgrammeMembership.objects.get_or_create(
            sponsor=sponsor, programme=programme,
            defaults={'status': sponsor.status, 'vetted_at': timezone.now() if settled else None})


def settle_signup_memberships(sponsor, vetted_by):
    """ACCOUNT VETTING: settle each signup gift's membership to the account's status, exactly as
    `sync_account_membership` does for one — the same gifts registration opened, and only those.
    ``freeze``: Every gift is never resolved live here; it reads what registration froze, and only
    an invitation registered unfrozen (the old image, in a rollback) is resolved — and frozen — now."""
    for programme in signup_programmes_for(sponsor, freeze=True):
        sync_account_membership(sponsor, programme, vetted_by=vetted_by)
