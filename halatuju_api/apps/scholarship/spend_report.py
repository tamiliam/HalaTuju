"""What the officer sees, and the one thing they can change.

The sorter (`spend_category.py`) decides; this module only READS what it decided and offers the
single write that outranks it. **No rule, threshold or category logic lives here** — if a question
is "how is this decided?", the answer is in `spend_category.py`.

Requirements: `docs/plans/2026-09-10-sponsor-spending-roadmap.md` S4 and
`docs/plans/2026-09-09-sponsor-spending-reports-brief.md` §4d (the assumptions note).

────────────────────────────────────────────────────────────────────────────────────────────────
⚠⚠ **THIS IS A ROW QUESTION, NOT A FIELD QUESTION, SO THE FENCE IS ON THE QUERY.** An allowlist
serializer protects a COLUMN; it does nothing about a row. Every function here takes an
organisation and filters `application__owning_organisation`, once, at the query — and the view
re-asserts it. Bypassing the fence has to fail twice (TD-201, 2026-07-31).

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
from datetime import timedelta

from .spending_import import TX_SPEND, WALLET_EXPECTED_STATES, norm_text

logger = logging.getLogger(__name__)

_ZERO = Decimal('0.00')

#: A category the sorter actually placed. `''` (never sorted) and `'unsorted'` (sorted, unplaceable)
#: are both "not placed" for the purpose of the headline percentage — they are different states but
#: neither is an answer a sponsor could read.
UNPLACED = ('', 'unsorted')

#: How far back "what the model decided recently" looks. A window, not a stored flag — the same
#: reasoning as the staleness nudge: a flag set on a day the job failed means nobody is ever told.
MODEL_REVIEW_DAYS = 14


def _txns(org):
    """Every spend transaction this organisation may see. **The fence, in one place.**"""
    from .models import BursarySpendTxn

    # org-fence: application__owning_organisation, the same fence the Payments funding summary
    # uses. A caller with no organisation is refused by the view before reaching here.
    return BursarySpendTxn.objects.filter(application__owning_organisation=org)


def totals(org) -> dict:
    """The four figures above the table. Every one of them COMPUTED, never estimated."""
    rows = _txns(org).filter(tx_type=TX_SPEND).values_list('category', 'amount')
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
        'merchants_to_check': len(merchants_to_check(org)),
    }


def merchants_to_check(org) -> list:
    """Merchants whose category no human has confirmed and no rule produced — the work queue.

    A `rule` verdict is code and needs no review. `inferred` and `ai` are estimates, and
    `unsorted` is an admission. Those three are what an officer is being asked to look at.
    """
    return sorted({
        merchant for merchant, decided_by in
        _txns(org).exclude(decided_by='owner').values_list('merchant', 'decided_by')
        if decided_by != 'rule' and merchant
    })


def merchant_rows(org) -> list:
    """One row per shop: what it was counted as, how that was decided, and the money.

    ⚠ `held_back` is the count of this shop's payments that the RM20 per-row ceiling kept out of
    `food` — the six real payments worth RM424 that a merchant-level verdict would have swept in.
    Surfacing it is the point: those rows are honestly `unsorted` and an officer is the only one
    who can place them.
    """
    from .models import MerchantCategory

    verdicts = {
        m: (c, d) for m, c, d in
        MerchantCategory.objects.values_list('merchant', 'category', 'decided_by')
    }
    agg: dict[str, dict] = {}
    for merchant, category, decided_by, amount, when in _txns(org).filter(
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
        if stored:
            category, decided_by = stored
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
        })
    out.sort(key=lambda r: (-r['total'], r['merchant']))
    return out


def student_rows(org) -> list:
    """One row per funded student: what they spent, and how much of it is placed.

    ⚠ Names appear here because this is the officer's own organisation's students on an admin-only
    surface. Nothing in this shape may be reused by a sponsor serializer.
    """
    agg: dict[int, dict] = {}
    for app_id, name, category, amount in _txns(org).filter(tx_type=TX_SPEND).values_list(
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


def model_decisions(org, days=MODEL_REVIEW_DAYS) -> list:
    """What the model decided lately, so it is checked while it is fresh.

    ⚠ Only merchants THIS organisation's students actually used — the verdict table is global but
    the list is not (see the module docstring).
    """
    from django.utils import timezone

    from .models import MerchantCategory

    mine = set(_txns(org).values_list('merchant', flat=True).distinct())
    if not mine:
        return []
    since = timezone.now() - timedelta(days=days)
    rows = (MerchantCategory.objects
            .filter(decided_by='ai', decided_at__gte=since, merchant__in=mine)
            .order_by('-decided_at')
            .values_list('merchant', 'category', 'reason', 'decided_at'))
    return [{'merchant': m, 'category': c, 'reason': r, 'decided_at': d} for m, c, r, d in rows]


def wallet_gaps(org) -> dict:
    """The two wallet faults that ARE derivable from what we store. See the module docstring for
    the third one, which is not, and reaches a human by email instead."""
    from .models import ScholarshipApplication

    # org-fence: owning_organisation, the same fence _txns uses.
    scope = ScholarshipApplication.objects.filter(owning_organisation=org)
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


def set_owner_category(merchant, category, email, org):
    """The one write. A person's verdict, which outranks every rung of the ladder for ever.

    Returns `(rows_changed, error_code)`. The error codes are deliberately narrow — an unknown
    category or a merchant this organisation has never used is a refusal, not a silent no-op.

    ⚠ **THE MERCHANT MUST BE ONE THIS ORGANISATION ACTUALLY USED.** Without that check the endpoint
    would let any tenant's admin write a verdict for any shop in the platform by guessing a name —
    the verdict is global (by design), so the FENCE has to be on who may set it.

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

    mine = _txns(org).filter(merchant=merchant)
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
