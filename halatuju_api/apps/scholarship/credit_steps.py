"""Whose signature a wallet credit waits for — the ONE home of the credit chain's step rule
(T5c P5b S1, 2026-11-05).

`sponsorship.sign_admin_credit` asks `step_refusal` before it writes a signature; the Overview's
`wallet_credits` card (`my_pending`) asks the same function to count the credits waiting for THIS
person. Pulled out of `sign_admin_credit` so the two can never disagree, and into a module of its
own because `sponsorship.py` sits at its `oversize_files` allowance.

The chain (see `sign_admin_credit`'s docstring for the why):

  * DRAFT -> the MAKER (role ``admin``, or super);
  * ADMIN_SIGNED with finance ACTIVE -> only the CHECKER (role ``finance``, or super); an org_admin is
    told ``finance_check_required``;
  * ADMIN_SIGNED with finance dormant, or FINANCE_CHECKED -> the APPROVER (``org_admin``, or super);
  * and nobody signs twice (``same_signer``, by email) — except the maker's step, which has no earlier
    signature to collide with.
"""
from .models import Donation

#: The statuses still waiting for a signature (`sign_admin_credit`'s ``bad_state`` is everything else).
SIGNING = (Donation.STATUS_DRAFT, Donation.STATUS_ADMIN_SIGNED, Donation.STATUS_FINANCE_CHECKED)


def collected_signer_emails(credit):
    """Every email that has already signed this credit, casefolded — the basis of the
    three-distinct-signers rule. Keyed on EMAIL, never on the displayed name: prod has two
    active admins sharing the name "Ve. Elanjelian", so a name key would be wrong in both
    directions (see the 0125 migration docstring). Mirrors
    ``payments._collected_signer_emails``."""
    return {
        (e or '').strip().casefold()
        for e in (credit.recorded_by_email, credit.finance_checked_by_email,
                  credit.confirmed_by_email)
        if (e or '').strip()
    }


def step_refusal(credit, admin, needs_finance):
    """Why `admin` may NOT sign `credit`'s next step — ``'wrong_role'``, ``'finance_check_required'``,
    ``'same_signer'`` — or None when they may. `credit` must be in `SIGNING` (the caller checks
    ``bad_state`` first); `needs_finance` is ``payments.credit_check_required(<the credit's org>)``."""
    is_super = bool(getattr(admin, 'is_super', False))
    if credit.status == Donation.STATUS_DRAFT:
        return None if (is_super or admin.role == 'admin') else 'wrong_role'
    if credit.status == Donation.STATUS_ADMIN_SIGNED and needs_finance:
        if not (is_super or admin.role == 'finance'):
            return 'finance_check_required' if admin.role == 'org_admin' else 'wrong_role'
    elif not (is_super or admin.role == 'org_admin'):
        return 'wrong_role'
    if (admin.email or '').strip().casefold() in collected_signer_emails(credit):
        return 'same_signer'
    return None


def checks_credits(admin):
    """Does this person hold the credit chain's CHECKER seat (role ``finance``)? The Overview's
    `wallet_credits` card is theirs (owner, 2026-11-05)."""
    return getattr(admin, 'role', '') == 'finance'


def waiting_for(admin, credits):
    """How many of `credits` (in `SIGNING`, each with ``programme__organisation`` selected) wait for
    `admin`'s signature now. ``credit_check_required`` is asked once per organisation."""
    from . import payments
    needs = {}
    n = 0
    for credit in credits:
        org = credit.programme.organisation if credit.programme_id else None
        key = getattr(org, 'pk', None)
        if key not in needs:
            needs[key] = payments.credit_check_required(org)
        if step_refusal(credit, admin, needs[key]) is None:
            n += 1
    return n
