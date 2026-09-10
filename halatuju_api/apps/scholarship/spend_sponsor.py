"""What a SPONSOR may see about their student's spending. **Categories and totals. Nothing else.**

⚠⚠ **THIS MODULE IS A SEPARATE FILE FROM `spend_report.py` ON PURPOSE.** That one serves the
officer and names merchants and students deliberately; this one serves an outsider and must never
name anything. Two audiences that different should not share a payload, a helper, or a file — the
moment they do, a field added for the officer arrives on the sponsor card by accident, which is
exactly the failure the sponsor-pool serializers were built to make impossible.

Requirements: `docs/plans/2026-09-09-sponsor-spending-reports-brief.md` §4 (the owner's ruling) and
§4d (the assumptions note the card must carry).

────────────────────────────────────────────────────────────────────────────────────────────────
⚠⚠ **WHAT MAY NEVER APPEAR HERE, AT ALL:** a merchant name, a transaction id, a wallet id, a
transaction DATE, a time of day, a student name, an application id, a payment count per shop.
`test_spend_sponsor` plants a real one of each on the fixture and asserts none reaches the payload.
The values are **built one at a time from aggregates** — there is no model passthrough — so a field
added to `BursarySpendTxn` tomorrow cannot reach a sponsor unless somebody writes a line for it.

⚠ **THE "AS AT" STAMP IS THE LAST IMPORT, NOT THE LAST PURCHASE.** They look interchangeable and
are not: the newest `txn_date` is *the day this student last bought something*, which is a
transaction date wearing a different hat. `imported_at` answers the question the stamp actually
asks — how fresh is this? — and reveals nothing about the student.

⚠ **`transfer` AND `unsorted` ARE NEVER FOLDED INTO "Other"** (owner, 2026-09-10). The brief folds
everything past the top six, and these two are the exceptions: `transfer` is money sent to a person
— the one line a careful sponsor most needs to see — and `unsorted` is what stops the other nine
reading as complete when they are not. Hiding either inside "Other" would be quietly dropping the
honest categories.

⚠ **"SPENT" CAN EXCEED "RELEASED", AND THAT IS NOT A FAULT.** The Vircle wallet is the student's
own and a parent may top it up; we cannot tell our ringgit from theirs. `left` therefore FLOORS AT
ZERO — the arithmetic must never go negative on screen — and no copy anywhere may imply the student
overspent the sponsor's money.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from django.utils import timezone

logger = logging.getLogger(__name__)

_ZERO = Decimal('0.00')

#: Slices drawn individually; everything else folds into `other`.
TOP_SLICES = 6

#: ⚠ Never folded, however small. See the module docstring.
NEVER_FOLDED = ('transfer', 'unsorted')


def _rounded(value):
    return (value or _ZERO).quantize(Decimal('0.01'))


def category_rows(pairs, labels):
    """`[(category, amount)]` → the ranked list the card draws, with `other` already folded.

    Pure — no database, no application, nothing identifying can reach it. Returns
    `[{'code', 'label', 'total'}]` ordered by value, with `other` last when it exists.
    """
    totals: dict[str, Decimal] = {}
    for code, amount in pairs:
        code = code or 'unsorted'
        totals[code] = totals.get(code, _ZERO) + (amount or _ZERO)
    totals = {c: t for c, t in totals.items() if t > _ZERO}

    # ⚠ ONE sort, and the tie-break is the LABEL — what a reader actually sees, so two categories
    # on the same amount read in a stable, sensible order in every language's eyes.
    #
    # ⚠ There is deliberately NO second sort after the loop. An earlier draft had one, with a
    # comment claiming it re-ranked a never-folded category "rescued from below the cut" — and a
    # bite-check proved it could never change anything: `ranked` is already ordered and the loop
    # appends in that order, so `kept` is ordered by construction. **Dead code that looks like a
    # safeguard is worse than none, because it invites trust.** A rescued row sorts below the top
    # six for the honest reason that it is smaller than all of them.
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], labels.get(kv[0], kv[0])))
    kept, folded = [], _ZERO
    for index, (code, total) in enumerate(ranked):
        if index < TOP_SLICES or code in NEVER_FOLDED:
            kept.append({'code': code, 'label': labels.get(code, code), 'total': _rounded(total)})
        else:
            folded += total

    if folded > _ZERO:
        kept.append({'code': 'other', 'label': '', 'total': _rounded(folded)})
    return kept


def sponsor_card(application) -> dict | None:
    """The whole sponsor-facing payload for one student, or `None` when there is nothing to show.

    `None` — not an empty card — when no spending has ever been imported for this student. An
    empty donut beside four zeroes reads as *"they have spent nothing"*, which is a claim we cannot
    make: the far likelier truth is that no report has reached us yet. The panel is simply absent.
    """
    from django.utils import timezone

    from . import payments
    from .models import SPEND_CATEGORY_CHOICES, BursarySpendTxn

    labels = dict(SPEND_CATEGORY_CHOICES)

    # The caller is `SponsorMyStudentDetailSerializer`, reached only through
    # `SponsorMyStudentDetailView`, which resolves the application from the CALLER'S OWN
    # sponsorship and 404s otherwise — so a sponsor cannot probe a student they do not fund.
    # org-fence: the APPLICATION, resolved from the caller's own sponsorship.
    rows = list(BursarySpendTxn.objects
                .filter(application=application, tx_type='SPEND')
                .values_list('category', 'amount'))
    # org-fence: the same application, same gate.
    newest = (BursarySpendTxn.objects
              .filter(application=application)
              .order_by('-imported_at')
              .values_list('imported_at', flat=True)
              .first())
    if not rows or newest is None:
        return None

    spent = sum((amount or _ZERO for _c, amount in rows), _ZERO)
    promised = application.award_amount or _ZERO
    released = payments.paid_to_date(application)
    # ⚠ FLOORED AT ZERO. A parent top-up can make `spent` exceed `released`; the card must not show
    # a negative wallet and the copy must not imply the student overspent our money.
    left = released - spent
    if left < _ZERO:
        left = _ZERO

    # ⚠⚠ MONEY LEAVES AS A STRING, NOT A Decimal — and this line is written in blood. A bare
    # `Decimal` in a plain dict is encoded by DRF's JSON renderer as a FLOAT, so `30.00` reached
    # the wire as `30.0`. The unit test on this function was green throughout (the values ARE
    # Decimals here); only a test driving the real endpoint could see it. Every other money-bearing
    # payload in this feature stringifies at the boundary for the same reason.
    return {
        'promised': str(_rounded(promised)),
        'released': str(_rounded(released)),
        'spent': str(_rounded(spent)),
        'left': str(_rounded(left)),
        # ⚠ The IMPORT date, never the newest transaction date. See the module docstring.
        #
        # ⚠⚠ AND IT IS THE DATE IN MALAYSIA, NOT IN UTC. `imported_at` is stored UTC, so a bare
        # `.date()` is yesterday for the eight hours between midnight MYT and 08:00 MYT — a sponsor
        # opening the card over breakfast would be told the figures were "as at" the day before,
        # every single morning.
        #
        # ⚠ **TD-209's THIRD INSTANCE, and two agents fixed it within an hour of each other on
        # 2026-09-11** — one from the clock rolling past midnight mid-deploy, one from an unrelated
        # sprint running the full suite at 01:40 MYT. Neither was looking for it. **`.date()` on a
        # stored datetime in this codebase is almost always missing a `timezone.localtime()`**, and
        # the reason it survives review is that the two agree for two-thirds of every day. The test
        # beside this one now PINS THE CLOCK rather than comparing against `timezone.localtime()`,
        # which is the same moving clock as the bug and could only ever catch it in the small hours.
        'as_at': timezone.localtime(newest).date().isoformat(),
        'categories': [{'code': r['code'], 'label': r['label'], 'total': str(r['total'])}
                       for r in category_rows(rows, labels)],
    }
