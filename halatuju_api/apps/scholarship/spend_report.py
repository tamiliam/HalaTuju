"""What the officer sees, and the one thing they can change.

The sorter (`spend_category.py`) decides; this module only READS what it decided and offers the
single write that outranks it. **No rule, threshold or category logic lives here** — if a question
is "how is this decided?", the answer is in `spend_category.py`.

Requirements: `docs/plans/2026-09-10-sponsor-spending-roadmap.md` S4 and
`docs/plans/2026-09-09-sponsor-spending-reports-brief.md` §4d (the assumptions note).

────────────────────────────────────────────────────────────────────────────────────────────────
⚠⚠ **THIS IS A ROW QUESTION, NOT A FIELD QUESTION, SO THE FENCE IS ON THE QUERY.** An allowlist
serializer protects a COLUMN; it does nothing about a row. Every function here takes a SCOPE and
filters `application__owning_organisation`, once, at the query — and the view
re-asserts it. Bypassing the fence has to fail twice (TD-201, 2026-07-31).

⚠ **THERE ARE EXACTLY TWO SCOPES: AN ORGANISATION, AND `ALL_ORGS`.** The second is the platform
view a super gets, added 2026-09-11 because a super was refused by their own console. It is a
sentinel object rather than `None` on purpose — see the note on `ALL_ORGS` — so no accident that
loses an organisation can widen a tenant's page into a platform-wide one.

⚠ **THE OFFICER MAY SEE MERCHANTS AND STUDENT NAMES; A SPONSOR MAY SEE NEITHER.** This is the
internal surface — oversight is the officer's job and a shop name is exactly what makes a wrong
category correctable. Nothing here is reachable from a sponsor or student endpoint, and no
serializer in this file is reused by one.

⚠ **NO TIME OF DAY EXISTS TO LEAK.** `txn_date` is a `DateField`; the hour was discarded at
import, deliberately and for ever. "Last seen" is a date because it cannot be anything else.

────────────────────────────────────────────────────────────────────────────────────────────────
⚠ **A MERCHANT VERDICT IS GLOBAL, AND THAT IS DELIBERATE.** `MerchantCategory` is unique on the
merchant name with no organisation column: "99 SPEEDMART sells groceries" is a fact about a shop,
not about a tenant, and duplicating it per tenant would ask every organisation to re-answer the
same question and pay the model again for it. **What is fenced is the LIST** — an officer only ever
sees shops their own students actually used. See `docs/decisions.md`.

⚠ **WHAT THIS SCREEN CANNOT SHOW, AND WHY.** A wallet that matches NO student is reported at
import and never stored (the row is skipped — money filed against nobody is worse than money we
have flagged). Showing those here would need a table, which would need a migration, which S4 does
not have. What IS derivable is the opposite gap and the ambiguous one — a funded student with no
wallet recorded, and a wallet claimed by two students — so those are what `wallet_gaps` returns.
The unknown wallet still reaches a human, by email, from the ingest job.
"""
from __future__ import annotations

import logging
from decimal import Decimal

from .spending_import import TX_SPEND, WALLET_EXPECTED_STATES, norm_text

logger = logging.getLogger(__name__)

_ZERO = Decimal('0.00')

#: A category the sorter actually placed. `''` (never sorted) and `'unsorted'` (sorted, unplaceable)
#: are both "not placed" for the purpose of the headline percentage — they are different states but
#: neither is an answer a sponsor could read.
UNPLACED = ('', 'unsorted')


class _AllOrganisations:
    """The platform-wide scope. See `ALL_ORGS`."""

    __slots__ = ()

    def __repr__(self):  # pragma: no cover - debugging affordance only
        return 'ALL_ORGS'


#: **Every organisation's spending, pooled.** Only `_SpendingBase` may hand this out, and only to a
#: super with no organisation of their own.
#:
#: ⚠⚠ **IT IS A SENTINEL OBJECT AND MUST NEVER BECOME `None`.** The whole point is that the two
#: cannot be confused. `None` reaching `_txns` filters `application__owning_organisation=None`,
#: which matches applications belonging to NO organisation — an empty result on production, and a
#: safe one. If the platform scope were spelled `None`, then every bug that loses an organisation
#: (an unset attribute, a missed keyword, a `.get()` on a dict) would silently widen a tenant's
#: page into a platform-wide one. An `is ALL_ORGS` identity check cannot be arrived at by accident.
#:
#: ⚠ This REVERSES the S4a ruling that a super must pick an organisation first (`docs/decisions.md`,
#: 2026-09-10). That decision named its own trigger — *"a genuine platform-wide spending view is
#: ever wanted"* — and the owner asked for one on 2026-09-11 after being refused by their own
#: console. The reversal is recorded there; this is not a loosened fence, it is a second scope with
#: exactly one door into it.
ALL_ORGS = _AllOrganisations()


def _txns(org, programme=None):
    """Every spend transaction this scope may see. **The fence, in one place.**

    ⚠⚠ **`programme` NARROWS ALONGSIDE THE ORGANISATION FILTER, NEVER INSTEAD OF IT.** This is
    the same wording `payments.eligible_rows` carries, and it is load-bearing: the organisation
    is the SECURITY fence and the gift is a restriction inside it. Read the code below in that
    order — if a future edit ever makes the two an either/or, a caller naming a gift would escape
    the tenant wall. TD-241 (2026-09-11), when Spending moved to the Programme section.

    The gift itself is resolved by `_AdminBase._gift_narrowing`, which only ever finds one inside
    the caller's own organisation — so this filter cannot reach rows the fence had excluded.
    """
    from .models import BursarySpendTxn

    if org is ALL_ORGS:
        # ⚠ THE PRAGMA SITS DIRECTLY ABOVE THE QUERY BECAUSE THE GUARD LOOKS 200 CHARACTERS.
        # org-fence: DELIBERATELY UNFENCED — the platform scope, reachable only via `ALL_ORGS`,
        # which only `_SpendingBase` hands out and only to a super. See the note on the sentinel.
        qs = BursarySpendTxn.objects.all()
    else:
        # org-fence: application__owning_organisation, the same fence the Payments funding summary
        # uses. A caller with no organisation is refused by the view before reaching here.
        qs = BursarySpendTxn.objects.filter(application__owning_organisation=org)
    if programme is not None:
        # `application.programme` is a set-once denormalised copy of `cohort.programme`, so this
        # is one filter rather than a join — and it cannot drift when a cohort is later moved.
        qs = qs.filter(application__programme=programme)
    return qs


def totals(org, programme=None) -> dict:
    """The four figures above the table. Every one of them COMPUTED, never estimated."""
    rows = _txns(org, programme).filter(tx_type=TX_SPEND).values_list('category', 'amount')
    spent = _ZERO
    unplaced = _ZERO
    for category, amount in rows:
        amount = amount or _ZERO
        spent += amount
        if category in UNPLACED:
            unplaced += amount
    placed = spent - unplaced
    return {
        'spent': spent,
        'placed': placed,
        'unplaced': unplaced,
        # ⚠ Guarded: an organisation with no spending at all must read 0%, not crash and not 100%.
        'placed_pct': int((placed / spent * 100).to_integral_value()) if spent else 0,
        'merchants_to_check': len(merchants_to_check(org, programme)),
    }


def merchants_to_check(org, programme=None) -> list:
    """Merchants whose category no human has confirmed and no rule produced — the work queue.

    A `rule` verdict is code and needs no review. `inferred` and `ai` are estimates, and
    `unsorted` is an admission. Those three are what an officer is being asked to look at.
    """
    return sorted({
        merchant for merchant, decided_by in
        _txns(org, programme).exclude(decided_by='owner')
        .values_list('merchant', 'decided_by')
        if decided_by != 'rule' and merchant
    })


def merchant_rows(org, programme=None) -> list:
    """One row per shop: what it was counted as, how that was decided, and the money.

    ⚠ `held_back` is the count of this shop's payments that the RM20 per-row ceiling kept out of
    `food` — the six real payments worth RM424 that a merchant-level verdict would have swept in.
    Surfacing it is the point: those rows are honestly `unsorted` and an officer is the only one
    who can place them.
    """
    from .models import MerchantCategory

    # ⚠ `decided_at` RIDES ALONG HERE SINCE S7 (2026-09-11), and it replaced a whole section.
    # There used to be a separate "what the model decided recently" list beside this table. The
    # owner asked what action it expected and the honest answer was NONE: it was this same data,
    # filtered to `ai` and 14 days, with no way to correct anything from it — so a reader found a
    # wrong guess there and had to scroll back up to fix it. The only fact it held that the table
    # did not was WHEN, which is a column. One list you can act on beats two you cannot.
    verdicts = {
        m: (c, d, when) for m, c, d, when in
        MerchantCategory.objects.values_list('merchant', 'category', 'decided_by', 'decided_at')
    }
    agg: dict[str, dict] = {}
    for merchant, category, decided_by, amount, when in _txns(org, programme).filter(
            tx_type=TX_SPEND).values_list(
            'merchant', 'category', 'decided_by', 'amount', 'txn_date'):
        row = agg.setdefault(merchant, {
            'merchant': merchant, 'visits': 0, 'total': _ZERO, 'last_seen': None,
            'held_back': 0, 'row_categories': {},
        })
        row['visits'] += 1
        row['total'] += amount or _ZERO
        if row['last_seen'] is None or (when and when > row['last_seen']):
            row['last_seen'] = when
        if category in UNPLACED:
            row['held_back'] += 1
        row['row_categories'][category] = row['row_categories'].get(category, 0) + 1

    out = []
    for merchant, row in agg.items():
        stored = verdicts.get(merchant)
        decided_at = None
        if stored:
            category, decided_by, decided_at = stored
        else:
            # No merchant verdict (a person-transfer shop, or nothing has run). Report what the
            # ROWS say rather than inventing a verdict: the commonest, ties broken by name so the
            # answer is stable between runs.
            ranked = sorted(row['row_categories'].items(), key=lambda kv: (-kv[1], kv[0]))
            category, decided_by = (ranked[0][0] if ranked else 'unsorted'), ''
        # `held_back` only means the ceiling when the shop IS a food-pattern shop; elsewhere the
        # unplaced rows simply are the shop's whole story, and repeating the count would mislead.
        held_back = row['held_back'] if decided_by == 'inferred' else 0
        out.append({
            'merchant': merchant,
            'category': category,
            'decided_by': decided_by,
            'visits': row['visits'],
            'total': row['total'],
            'last_seen': row['last_seen'],
            'held_back': held_back,
            # When the stored verdict was reached — `None` for a shop with no verdict at all.
            # ⚠ NOT the same question as `last_seen`, which is when a student last bought here.
            'decided_at': decided_at,
        })
    out.sort(key=lambda r: (-r['total'], r['merchant']))
    return out


def student_rows(org, programme=None) -> list:
    """One row per funded student: what they spent, and how much of it is placed.

    ⚠ Names appear here because this is the officer's own organisation's students on an admin-only
    surface. Nothing in this shape may be reused by a sponsor serializer.
    """
    agg: dict[int, dict] = {}
    for app_id, name, category, amount in _txns(org, programme).filter(
            tx_type=TX_SPEND).values_list(
            'application_id', 'application__profile__name', 'category', 'amount'):
        row = agg.setdefault(app_id, {
            'application_id': app_id, 'name': name or '', 'payments': 0,
            'spent': _ZERO, 'unplaced': _ZERO,
        })
        row['payments'] += 1
        row['spent'] += amount or _ZERO
        if category in UNPLACED:
            row['unplaced'] += amount or _ZERO
    out = sorted(agg.values(), key=lambda r: (-r['spent'], r['name']))
    return out


def wallet_gaps(org, programme=None) -> dict:
    """The two wallet faults that ARE derivable from what we store. See the module docstring for
    the third one, which is not, and reaches a human by email instead."""
    from .models import ScholarshipApplication

    if org is ALL_ORGS:
        # org-fence: DELIBERATELY UNFENCED — the platform scope. Same door as `_txns`.
        scope = ScholarshipApplication.objects.all()
    else:
        # org-fence: owning_organisation, the same fence _txns uses.
        scope = ScholarshipApplication.objects.filter(owning_organisation=org)
    if programme is not None:
        # ⚠ Narrows INSIDE the fence, exactly as in `_txns`. A wallet gap belongs to the gift
        # whose money the student is waiting for, so a gift-scoped page must not list another
        # gift's missing wallets as though they were this one's work.
        scope = scope.filter(programme=programme)
    without = list(scope.filter(status__in=WALLET_EXPECTED_STATES, vircle_id='')
                   .values_list('id', flat=True))
    owners: dict[str, list] = {}
    for app_id, wallet in scope.exclude(vircle_id='').values_list('id', 'vircle_id'):
        key = ''.join(ch for ch in str(wallet or '') if ch.isdigit())
        if key:
            owners.setdefault(key, []).append(app_id)
    return {
        'students_without_wallet': sorted(without),
        'shared_wallets': {w: sorted(ids) for w, ids in owners.items() if len(ids) > 1},
    }


def set_owner_category(merchant, category, email, org, programme=None):
    """The one write. A person's verdict, which outranks every rung of the ladder for ever.

    Returns `(rows_changed, error_code)`. The error codes are deliberately narrow — an unknown
    category or a merchant this organisation has never used is a refusal, not a silent no-op.

    ⚠ **THE MERCHANT MUST BE ONE THIS ORGANISATION ACTUALLY USED.** Without that check the endpoint
    would let any tenant's admin write a verdict for any shop in the platform by guessing a name —
    the verdict is global (by design), so the FENCE has to be on who may set it.

    ⚠ Under `ALL_ORGS` that check widens to "a shop SOMEBODY's students used", which is the correct
    reading for a super: the verdict was always global, and a super is the one caller entitled to
    every organisation's list. It is still not a free-text write — an invented shop name is
    `unknown_merchant` for a super exactly as it is for a tenant.

    ⚠ Both stored strings are length-capped to their columns here. `MerchantCategory.reason` is
    varchar(255) and `decided_by_email` varchar(254); a plain `Serializer` does not inherit a
    model's `max_length`, and an over-long value is a rollback rather than a clean 400.
    """
    from django.db import transaction

    from .models import SPEND_CATEGORY_CHOICES, BursarySpendTxn, MerchantCategory

    merchant = norm_text(merchant)
    if not merchant:
        return 0, 'merchant_required'
    if category not in {c for c, _ in SPEND_CATEGORY_CHOICES}:
        return 0, 'unknown_category'

    # ⚠ NARROWED BY THE GIFT TOO. An officer looking at one gift may only correct shops that
    # gift's own students used — the verdict is still global (a shop's category is a fact
    # about the shop), so the fence is on WHO MAY SET IT, and the gift is part of who.
    mine = _txns(org, programme).filter(merchant=merchant)
    if not mine.exists():
        return 0, 'unknown_merchant'

    with transaction.atomic():
        MerchantCategory.objects.update_or_create(
            merchant=merchant,
            defaults={
                'category': category,
                'decided_by': 'owner',
                'reason': '',
                'decided_by_email': (email or '')[:254],
            },
        )
        # The caller was already fenced above — `mine.exists()` proves this organisation actually
        # used the shop. The UPDATE below is global on purpose: a merchant verdict is a fact about
        # the shop, not about a tenant, and leaving another tenant's rows on the old category
        # would make one shop read two ways on two screens with nothing to explain it. It moves a
        # CATEGORY and nothing else; no row crosses a boundary and no tenant reads another's data.
        # Widening this to any other field would be a different decision.
        #
        # ⚠ THE PRAGMA IS ON THE LINE ABOVE THE QUERY BECAUSE THE GUARD LOOKS 200 CHARACTERS. The
        # explanation goes above it, never between — that is what makes this fail, correctly.
        # org-fence: DELIBERATELY CROSS-ORGANISATION; the only such write in the feature.
        changed = BursarySpendTxn.objects.filter(merchant=merchant).update(
            category=category, decided_by='owner')
    return changed, None
