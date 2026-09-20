"""The officer's spending screen (sponsor spending S4).

Moved verbatim from the package root at code health H12. Part of the `views_admin`
package: every name below is re-exported from `views_admin/__init__.py`, so `urls.py`
and every importer are unchanged.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase


# ⚠ THE PACKAGE'S name, spelled out — never `__name__`. A submodule logger reads
# `apps.scholarship.views_admin.<module>` and drops every audit line it carries out
# of the Cloud Logging scrape metric. Guarded by `AuditLoggerNameTest` (H11).
logger = logging.getLogger('apps.scholarship.views_admin')


# ── the officer's spending screen (sponsor spending S4) ──────────────────────
#
# ⚠ READ AND WRITE ARE BOTH admin / org_admin, AND `finance` IS DELIBERATELY ABSENT.
# `_b40_scope` states that a finance admin never sees an applicant file, document, income
# figure or verdict, and that its ONLY student data is the Payments funding summary allowlist.
# This screen carries student names beside what they bought, which is welfare oversight rather
# than disbursement — adding finance here would quietly widen a boundary another docstring
# promises is closed.
_SPENDING_ROLES = ('admin', 'org_admin')


class _SpendingBase(_AdminBase):
    """Shared gate for the spending endpoints: an active admin, the right role, and the SCOPE to
    read within.

    ⚠ The scope is returned rather than looked up again downstream, so there is exactly ONE place
    the fence can be forgotten. **This method is the only door to the platform-wide scope in the
    whole feature** — `spend_report.ALL_ORGS` appears nowhere else outside its own module.

    ⚠⚠ **A SUPER GETS `ALL_ORGS`; EVERYONE ELSE GETS THEIR OWN ORGANISATION OR NOTHING.** Until
    2026-09-11 a super was refused `no_org`, on the reasoning that "defaulting to unfenced is how a
    super with no org context sees the platform" — which is true of a DEFAULT and not of an
    explicit scope. The owner opened their own console as super, was refused, and asked for the
    platform view (`docs/decisions.md`, 2026-09-11, superseding the S4a ruling). It is spelled as
    a sentinel object precisely so that it can only ever be chosen, never fallen into.

    ⚠ A super's own `owning_organisation`, if they have one, is deliberately IGNORED here. A super
    who saw one tenant on this page and every tenant on the neighbouring Payments list would have
    to work out which screens narrow and which do not; `admin.is_super` means the same thing on
    both. An `org_admin` with no organisation is still `no_org` — that is a broken account, not a
    scope.
    """

    def _spending_admin(self, request):
        """`(admin, scope, programme, error)`.

        ⚠ The GIFT is resolved here too (TD-241) so this stays the ONE door: a screen that
        read the scope from here and the gift from somewhere else would have two answers to
        'what am I looking at', and only one of them fenced.
        """
        from .. import spend_report

        admin = self.get_admin(request)
        if not admin:
            return None, None, None, self._deny()
        if not (admin.is_super or admin.role in _SPENDING_ROLES):
            return None, None, None, self._deny_role()
        programme, err = self._gift_narrowing(request, admin)
        if err:
            return None, None, None, err
        if admin.is_super:
            return admin, spend_report.ALL_ORGS, programme, None
        org = admin.owning_organisation
        if org is None:
            return None, None, None, Response({'error': 'no_org', 'code': 'no_org'},
                                              status=status.HTTP_400_BAD_REQUEST)
        return admin, org, programme, None


def _spending_gaps(gaps):
    """`wallet_gaps` with its money stringified.

    ⚠ A bare `Decimal` in a plain dict is rendered by DRF's JSON renderer as a FLOAT — `30.00`
    reached a sponsor's screen as `30.0` in S5, and the unit test was green throughout because
    the values ARE Decimals until the boundary. Every money-bearing payload in this feature
    stringifies here, at the edge, for that reason.
    """
    return {
        **gaps,
        'unseen_students': [
            {'application_id': r['application_id'], 'name': r['name'],
             'paid': str(r['paid']), 'spent': str(r['spent'])}
            for r in gaps['unseen_students']
        ],
    }


class AdminSpendingView(_SpendingBase):
    """GET /api/v1/admin/scholarship/spending/ — the officer's view of what students spent.

    Four computed figures, the merchant table, the per-student table, what the model decided
    lately, and the two wallet gaps that are derivable. Everything comes from
    `spend_report`, which holds the organisation fence.

    ⚠ **THE PAYLOAD IS BUILT KEY BY KEY FROM PLAIN DICTS — there is no model passthrough**, so
    a field added to `ScholarshipApplication` or `StudentProfile` tomorrow cannot reach this
    response unless somebody writes a line for it. That is the same guarantee a hand-written
    allowlist serializer gives, and `test_spend_report.py` proves it the way the sponsor pool
    serializers are proved: a real NRIC, phone, address, email and school are planted on the
    fixture and asserted ABSENT from the rendered JSON. The student NAME is present on purpose
    — this is the officer's own organisation's students, on an admin-only surface.

    ⚠ Money is rendered as a STRING, never a float. It is summed, compared against a released
    total and shown to a person.

    tenancy: org-fenced on `application__owning_organisation` inside `spend_report._txns`, and
    the organisation is resolved once by `_spending_admin`. Classified in test_org_fence.py.
    """

    def get(self, request):
        admin, org, programme, err = self._spending_admin(request)
        if err:
            return err
        from .. import spend_report
        from ..models import SPEND_CATEGORY_CHOICES

        totals = spend_report.totals(org, programme)
        return Response({
            'totals': {
                'spent': str(totals['spent']),
                'placed': str(totals['placed']),
                'unplaced': str(totals['unplaced']),
                'placed_pct': totals['placed_pct'],
                'merchants_to_check': totals['merchants_to_check'],
            },
            'merchants': [{
                'merchant': r['merchant'],
                'category': r['category'],
                'decided_by': r['decided_by'],
                'visits': r['visits'],
                'total': str(r['total']),
                'last_seen': r['last_seen'].isoformat() if r['last_seen'] else None,
                'held_back': r['held_back'],
                # ⚠ WHEN THE VERDICT WAS REACHED, not when a student last shopped here. Added S7
                # when the separate "what the model decided recently" list was deleted: that list
                # held exactly one fact this table did not, and a fact is a column.
                'decided_at': r['decided_at'].isoformat() if r['decided_at'] else None,
            } for r in spend_report.merchant_rows(org, programme)],
            'students': [{
                'application_id': r['application_id'],
                'name': r['name'],
                # ⚠ TRANSACTIONS — things the student BOUGHT. It was called `payments`,
                # which beside the new `paid`/`balance` read as the number of
                # disbursements: two different money words on one row (owner, 2026-09-12).
                'transactions': r['transactions'],
                'spent': str(r['spent']),
                'unplaced': str(r['unplaced']),
                'paid': str(r['paid']),
                # ⚠ NOT floored at zero, unlike the sponsor card's. A negative is real —
                # the wallet is the student's own and a parent may top it up — and the
                # officer is exactly the person who should notice and ask.
                'balance': str(r['balance']),
            } for r in spend_report.student_rows(org, programme)],
            # ⚠ `model_decisions` WAS HERE AND IS DELETED (S7, 2026-09-11). It was this same data
            # filtered to `ai` within 14 days, rendered read-only beside a table that CAN be
            # corrected — so a reader found a wrong guess there and had to scroll up to fix it.
            # The owner asked what action it expected; the answer was none. Filter the shops table
            # by "how we decided" instead. Do not reintroduce it.
            'wallet_gaps': _spending_gaps(spend_report.wallet_gaps(org, programme)),
            'categories': [{'code': c, 'label': label} for c, label in SPEND_CATEGORY_CHOICES],
        })


class AdminSpendingCategoryView(_SpendingBase):
    """POST /api/v1/admin/scholarship/spending/category/ — correct one shop's category.

    Body: `{"merchant": "...", "category": "..."}`. Writes a `decided_by='owner'` verdict,
    which outranks every rung of the sorter and survives a full `--all` re-sort for ever.

    ⚠ The merchant must be one THIS organisation's students actually used. The verdict itself
    is global — a shop's category is a fact about the shop — so the fence has to be on who may
    SET it, or any tenant's admin could write a verdict for any shop by guessing a name.

    ⚠ An unknown category or an unused merchant is a 400 with a code, never a silent no-op: a
    correction screen that quietly does nothing is worse than one that refuses.

    tenancy: org-fenced inside `spend_report.set_owner_category` via the same `_txns` filter.
    Classified in test_org_fence.py.
    """

    def post(self, request):
        admin, org, programme, err = self._spending_admin(request)
        if err:
            return err
        from .. import spend_report

        merchant = request.data.get('merchant') or ''
        category = request.data.get('category') or ''
        changed, code = spend_report.set_owner_category(
            merchant, category, admin.email, org, programme)
        if code:
            return Response({'error': code, 'code': code},
                            status=status.HTTP_400_BAD_REQUEST)
        # ⚠ ON THE AUDIT LINE because it is the part nobody can reconstruct later: the stored
        # row says who decided and when, but "and it moved 42 payments" is the fact a reader
        # would otherwise have to guess at.
        logger.info('AUDIT spend_category_corrected merchant=%r category=%s rows=%s by=%s',
                    merchant, category, changed, admin.email or '')
        return Response({'merchant': merchant.strip().upper(), 'category': category,
                         'decided_by': 'owner', 'rows_changed': changed})
