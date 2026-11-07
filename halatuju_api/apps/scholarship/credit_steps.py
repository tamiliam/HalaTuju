"""Whose signature a wallet credit waits for — the ONE home of the credit chain's step rule
(T5c P5b S1, 2026-11-05).

`sponsorship.sign_admin_credit` asks `step_refusal` before it writes a signature; the Overview's
`wallet_credits` card (`my_pending`) asks the same function to count the credits waiting for THIS
person. Pulled out of `sign_admin_credit` so the two can never disagree, and into a module of its
own because `sponsorship.py` sits at its `oversize_files` allowance.

The chain (see `sign_admin_credit`'s docstring for the why):

  * DRAFT -> the MAKER (role ``admin``, or super);
  * ADMIN_SIGNED with finance ACTIVE -> only the CHECKER (a holder of ``payments_approve``, or super); an
    org_admin is told ``finance_check_required``;
  * ADMIN_SIGNED with finance dormant, or FINANCE_CHECKED -> the APPROVER (``org_admin``, or super);
  * and nobody signs twice (``same_signer``, by email) — except the maker's step, which has no earlier
    signature to collide with.

TD-475 (A1.10a, 2026-11-07): the CHECKER seat is the permission ``payments_approve`` (`CHECKER_KEY`), no
longer the retired ``finance`` ROLE label. Owner rulings 4 and 8 made a finance person "an Admin with
``payments_approve``", so a new finance person now both arms and performs the credit check, as they
already do for payment runs. Every existing ``finance`` row holds it by its preset, so today's checkers
keep the seat; the maker and approver steps are unchanged. Review fix (same sprint): the check is armed
PER CREDIT, only while a holder who has not signed it exists, so a keyed maker never strands their own
credit (the guard `payments_chain.check_required_for` keeps on runs).
"""
from apps.courses import staff_permissions
from .models import Donation

#: The statuses still waiting for a signature (`sign_admin_credit`'s ``bad_state`` is everything else).
SIGNING = (Donation.STATUS_DRAFT, Donation.STATUS_ADMIN_SIGNED, Donation.STATUS_FINANCE_CHECKED)

#: TD-475: the key that IS the credit checker seat, and whose ACTIVE holder in an organisation arms the
#: check (`payments_chain.credit_check_required`). A super passes it but is never a holder.
CHECKER_KEY = 'payments_approve'


def holds_checker_seat(admin):
    """True when `admin` (a team member, never a super) holds `CHECKER_KEY`."""
    return (admin is not None and not getattr(admin, 'is_super', False)
            and staff_permissions.holds(admin, CHECKER_KEY))


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
    ``bad_state`` first); `needs_finance` is ``payments.credit_check_required(<the credit's org>,
    credit)`` — armed only while a holder who has NOT signed this credit exists (A1.10a review fix)."""
    is_super = bool(getattr(admin, 'is_super', False))
    if credit.status == Donation.STATUS_DRAFT:
        return None if (is_super or admin.role == 'admin') else 'wrong_role'
    if credit.status == Donation.STATUS_ADMIN_SIGNED and needs_finance:
        if not (is_super or holds_checker_seat(admin)):        # TD-475: the key, not the role
            return 'finance_check_required' if admin.role == 'org_admin' else 'wrong_role'
    elif not (is_super or admin.role == 'org_admin'):
        return 'wrong_role'
    if (admin.email or '').strip().casefold() in collected_signer_emails(credit):
        return 'same_signer'
    return None


def checks_credits(admin):
    """Does this person hold the credit chain's CHECKER seat (`CHECKER_KEY`, TD-475; was role
    ``finance``)? The Overview's `wallet_credits` card is theirs (owner, 2026-11-05)."""
    return holds_checker_seat(admin)


def waiting_for(admin, credits):
    """How many of `credits` (in `SIGNING`, each with ``programme__organisation`` selected) wait for
    `admin`'s signature now. The checker holders are read once per organisation; whether the check is
    armed is per credit (a holder who signed it does not count, `credit_check_required`)."""
    from . import payments
    held = {}
    n = 0
    for credit in credits:
        org = credit.programme.organisation if credit.programme_id else None
        key = getattr(org, 'pk', None)
        if key not in held:
            held[key] = staff_permissions.holders(org, CHECKER_KEY) if org is not None else []
        needs = payments.credit_check_required(org, credit, held[key])
        if step_refusal(credit, admin, needs) is None:
            n += 1
    return n
