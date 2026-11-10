"""Sponsorship: the sponsor wallet. The one spend authority (``sponsor_balance``), the
confirmed-credit seam and the wallet, ledger, impact and statement reads.

Moved unchanged out of ``sponsorship.py`` when audit A3.8 (2026-11-10) made it a package.
"""
from decimal import Decimal

from django.db.models import Sum

from .. import money
from .. import pool
from ..results_review import accepted_count
from ..models import Donation, Programme, Sponsorship


def sponsor_balance(sponsor, programme):
    """A sponsor's spendable balance **within one gift programme** = donated to that
    programme − allocations in that programme that still hold (offered/active).
    Lapsed/cancelled allocations free up again.

    ``programme`` is REQUIRED and is the whole point: money given to one programme is
    never spendable in another (decisions.md, "Restricted funds and sponsor acceptance
    attach to the Programme"). Passing ``None`` scopes to the NULL bucket — the same
    safe degenerate partition the org fence uses — so bare test fixtures self-partition
    rather than silently pooling with real money.

    **This is the only spend authority.** Anything choosing whether a sponsor can fund a
    student must call this with that student's application programme. For a
    cross-programme DISPLAY figure use ``sponsor_available_total`` — never for a spend
    decision.
    """
    donated = (sponsor.donations
               .filter(programme=programme, status=Donation.STATUS_CONFIRMED)
               .aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    held = (sponsor.sponsorships
            .filter(status__in=Sponsorship.HOLDING, application__programme=programme)
            .aggregate(s=Sum('amount'))['s'] or Decimal('0'))
    return donated - held


def visible_donations(sponsor):
    """**The ONE narrowing seam for every sponsor-facing read of the money-in ledger.**

    A sponsor sees a credit only once it is CONFIRMED. Before P4a every donation row was
    confirmed-by-existence, so `sponsor.donations.all()` was a safe spelling; the credit
    chain ended that — a `draft` / `admin_signed` / `cancelled` row is money that has NOT
    been signed off, and showing it to the sponsor would state, on their own statement,
    that we hold money we have not agreed we hold.

    Same shape and same reason as `pool.for_sponsor()`: one seam, so the next surface that
    lists donations narrows by construction instead of by remembering. A source guard
    (tests/test_wallet_credit.py) asserts every sponsor-facing donation read goes through
    here.

    NOT the spend authority — that is `sponsor_balance(sponsor, programme)`, which applies
    the same status filter *and* the programme restriction.
    """
    return sponsor.donations.filter(status=Donation.STATUS_CONFIRMED)


def _amount_str(value):
    """Money as a 2-decimal string, ALWAYS; an absent figure is RM0 on a sponsor card.

    A `DecimalField` read gives `'3000.00'` but a `Sum()` over the same column gives `'20000'`,
    so a payload mixing the two renders "RM 20000" beside "RM 3,000.00" on one card. Was `_money`
    until code health H7; `coerce=False` keeps it refusing anything not already a `Decimal`.
    """
    return money.format_money(value, blank='0.00', blank_when=money.BLANK_FALSY, coerce=False)


def _wallet_programmes(sponsor):
    """**The one home for "which wallets does this sponsor hold".** Every programme they
    have donated into or allocated within, resolved to `Programme` objects (None for the
    NULL bucket) and ordered by id so output is stable.

    Extracted so `sponsor_programme_balances` and `programme_ledger` cannot drift: the
    set of wallets a sponsor holds must be the same question wherever it is asked.
    """
    programme_ids = set(
        visible_donations(sponsor).values_list('programme_id', flat=True)
    ) | set(
        sponsor.sponsorships.filter(status__in=Sponsorship.HOLDING)
        .values_list('application__programme_id', flat=True)
    )
    by_id = {p.id: p for p in Programme.objects.filter(id__in=[i for i in programme_ids if i])}
    return [by_id.get(pid) for pid in sorted(programme_ids, key=lambda i: (i is None, i))]


def sponsor_programme_balances(sponsor):
    """Every wallet this sponsor holds: ``[(programme, balance), ...]``. Display +
    reconciliation; per-wallet figures here are each a real spend authority, the *sum*
    of them is not."""
    return [(p, sponsor_balance(sponsor, p)) for p in _wallet_programmes(sponsor)]


def programme_ledger(sponsor):
    """Per-wallet money, split three ways for an ADMIN reading one sponsor.

    ``[{'programme': p|None, 'given', 'committed', 'available', 'credits', 'students'}]``

    - **given** — CONFIRMED donations only (through `visible_donations`, so a draft or
      cancelled credit is money we have not agreed we hold and never appears).
    - **committed** — allocations still HOLDING (offered or active) in this programme.
    - **available** — `sponsor_balance`, i.e. given − committed. Recomputed by the
      authority rather than subtracted here, so this display can never disagree with
      the figure that actually authorises a spend.
    """
    out = []
    for programme in _wallet_programmes(sponsor):
        confirmed = visible_donations(sponsor).filter(programme=programme)
        holding = sponsor.sponsorships.filter(
            status__in=Sponsorship.HOLDING, application__programme=programme)
        out.append({
            'programme': programme,
            'given': _amount_str(confirmed.aggregate(s=Sum('amount'))['s']),
            'committed': _amount_str(holding.aggregate(s=Sum('amount'))['s']),
            'available': _amount_str(sponsor_balance(sponsor, programme)),
            'credits': confirmed.count(),
            'students': holding.count(),
        })
    return out


def sponsor_available_total(sponsor):
    """DISPLAY ONLY — the sum of every wallet this sponsor holds. **Never a spend
    authority**: a total across programmes is not spendable anywhere, because each
    ringgit is restricted to the programme it was given to. Use ``sponsor_balance``
    with an explicit programme for any funding decision."""
    return sum((bal for _p, bal in sponsor_programme_balances(sponsor)), Decimal('0'))


def sponsor_impact(sponsor):
    """R2 — aggregate giving impact for the My Giving dashboard. Counts + money only,
    **allowlist-safe by construction** (no student identity ever crosses): derived
    from the ledger (`sponsor_balance`) + the sponsor's ACTIVE allocations and their
    SemesterResults. A graduated student's allocation stays 'active' (graduation is a
    result flag, not a sponsorship status), so we split active giving into
    `completed` (graduated) vs `committed` (ongoing) via `pool.derive_progress_state`.
    """
    active = list(sponsor.sponsorships.filter(status='active').select_related('application'))
    committed = Decimal('0')
    completed = Decimal('0')
    graduated_count = 0
    semesters_completed = 0
    for sp in active:
        app = sp.application
        if pool.derive_progress_state(app) == 'graduated':
            completed += sp.amount
            graduated_count += 1
        else:
            committed += sp.amount
        semesters_completed += accepted_count(app)   # S4a: accepted only
    return {
        'total_given': str(committed + completed),
        'students_supported': len(active),
        'students_active': len(active) - graduated_count,
        'students_graduated': graduated_count,
        'semesters_completed': semesters_completed,
        'balance': {
            'committed': str(committed),
            'completed': str(completed),
            'available': str(sponsor_available_total(sponsor)),
        },
    }


def sponsor_statement(sponsor):
    """R4 — the giving statement's two ledgers. **Donations INTO the trust** (the
    sponsor's own deposit records — fine to show back to them) and **gifts OUT to
    students** (active allocations carrying the anonymous ``ref`` only — never the
    student's identity). Allowlist-safe; counts + money + refs only."""
    donations = [
        {'amount': str(d.amount), 'reference': d.reference, 'at': d.created_at}
        for d in visible_donations(sponsor).order_by('-created_at')
    ]
    gifts = []
    out_total = Decimal('0')
    for sp in (sponsor.sponsorships.filter(status='active')
               .select_related('application').order_by('-decided_at')):
        gifts.append({'ref': pool.pool_ref(sp.application_id), 'amount': str(sp.amount), 'at': sp.decided_at})
        out_total += sp.amount
    # Allocations that HOLD the balance but are not yet accepted by the student. Without
    # this line the statement contradicts the wallet: while award acceptance is switched
    # off nothing ever reaches 'active', so a sponsor with every ringgit allocated read
    # "RM172,000 in / RM0 out" beside a balance that said otherwise. Kept as its own
    # total rather than folded into `total_out` — committed is not yet given away, and
    # `gifts` is the settled record.
    committed = []
    committed_total = Decimal('0')
    for sp in (sponsor.sponsorships.filter(status='offered')
               .select_related('application').order_by('-offered_at')):
        committed.append({'ref': pool.pool_ref(sp.application_id),
                          'amount': str(sp.amount), 'at': sp.offered_at})
        committed_total += sp.amount
    in_total = sum((Decimal(d['amount']) for d in donations), Decimal('0'))
    return {
        'donations': donations,
        'gifts': gifts,
        'committed': committed,
        'total_in': str(in_total),
        'total_out': str(out_total),
        'total_committed': str(committed_total),
    }
