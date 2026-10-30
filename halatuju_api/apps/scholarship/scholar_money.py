"""The scholar file's Money and Contract tabs (student maintenance Sprint 5a, 2026-10-30).

READS ONLY. Nothing here writes money or a contract; the doors are listed in docs/decisions.md (S5a).
The view (`views_admin/scholars.py`) is the fence — the Applications rule, org 404, a reviewer only
for an assigned scholar, finance and partner refused — and hands an application it may read.

MONEY. Award, paid, remaining and the last releases come from THE Payments rules and nowhere else:
`payments.paid_to_date` / `payments._remaining` (RELEASED disbursements are the one truth for "paid";
remaining floors at zero and is zero with no award), so this tab, the file's Overview card, her
My Bursary summary, the Payments funding summary and the sponsor card cannot disagree about one
student (`test_scholar_money.TestOneTruthForMoney`). Every amount leaves as a STRING — a bare Decimal
reaches the wire as a float through DRF's renderer.

SPENDING ("this term by category"). Only for a viewer holding the `spending` permission — the
Spending page's rule; without it the key is ABSENT from the payload, not null. Totals per category
CODE (the screen translates the code; no English label travels) from her `SPEND` transactions since
the start of the S4b result term she is IN — stored `term_starts_on` <= today <= `term_ends_on` —
else since she was funded. EVERY category is listed (no folding into "other": that is the sponsor
card's presentation, not the Spending page's). The officer sees the Spending page's arithmetic,
not the sponsor's floored "left".

CONTRACT. A platform-signed agreement only (owner ruling, 2026-10-29): COUNTERSIGNED — the student
and guarantor bind it and the organisation has signed (`bursary._maybe_activate`'s own rule; the
partner witness is NON-BLOCKING, so it is not required) — with its stored PDF; anything else is
"No contract on file". The signing feature flag is NOT read. The PDF is a signed URL into the
private bucket, minted ONLY when asked (`with_link`), expiring in `PDF_URL_SECONDS`, and refused
unless the path is this application's own (`<org>/<app>/…`). The parties carry names, roles and
dates — never an IC number; the witness row appears only once the witness has signed.
"""
from decimal import Decimal

from django.utils import timezone

#: How long a contract PDF link lives. Minted when the tab is read, never stored.
PDF_URL_SECONDS = 300
#: How many of her last released payments the tab lists.
LAST_RELEASES = 3

_CENTS = Decimal('0.01')


def _money(value):
    return str((value or Decimal('0')).quantize(_CENTS))


def _day(dt):
    return timezone.localtime(dt).date().isoformat() if dt else None


def spending_since(application, today=None):
    """`(date, basis)`: the start of the S4b result term she is in (`'term'`), else the day she was
    funded (`'funded'`), else `(None, 'all')`."""
    from .models import ResultsExpectation
    from .results_expectations import funded_since
    today = today or timezone.localdate()
    # The term she is IN: begun and not yet ended (review L5) — a lapsed term is not "this term".
    current = (ResultsExpectation.objects.filter(application=application, term_starts_on__lte=today,
                                                 term_ends_on__gte=today)
               .order_by('-term_starts_on', '-id').values_list('term_starts_on', flat=True).first())
    if current is not None:
        return current, 'term'
    start = funded_since(application)
    return (start, 'funded') if start else (None, 'all')


def spending_block(application, today=None):
    """Her spending by category since `spending_since` — the officer's figures."""
    from .models import SPEND_CATEGORY_CHOICES, BursarySpendTxn
    from .spend_sponsor import category_rows
    from .spending_import import TX_SPEND
    since, basis = spending_since(application, today)
    # org-fence: one application, already fenced by the view.
    txns = BursarySpendTxn.objects.filter(application=application, tx_type=TX_SPEND)
    if since is not None:
        txns = txns.filter(txn_date__gte=since)
    rows = list(txns.values_list('category', 'amount'))
    # org-fence: the same application.
    newest = (BursarySpendTxn.objects.filter(application=application)
              .order_by('-imported_at').values_list('imported_at', flat=True).first())
    spent = sum((amount or Decimal('0') for _c, amount in rows), Decimal('0'))
    return {
        'since': since.isoformat() if since else None,
        'basis': basis,
        'spent': _money(spent),
        'as_at': _day(newest),
        # By CODE only — the screen translates it (review M2); every category, unfolded.
        'categories': [{'code': r['code'], 'total': str(r['total'])}
                       for r in category_rows(rows, dict(SPEND_CATEGORY_CHOICES), fold=False)],
    }


def money_payload(application, *, may_see_spending, today=None):
    from .models import Disbursement
    from .payments import _remaining, paid_to_date
    releases = (Disbursement.objects.filter(application=application, status__in=Disbursement.PAID)
                .order_by('-released_at', '-id')[:LAST_RELEASES])
    out = {
        'award_amount': _money(application.award_amount) if application.award_amount is not None else None,
        'paid_to_date': _money(paid_to_date(application)),
        'remaining': _money(_remaining(application)),
        'releases': [{'amount': _money(d.amount), 'released_on': _day(d.released_at),
                      'label': d.label or '', 'reference': d.reference or ''} for d in releases],
    }
    if may_see_spending:
        out['spending'] = spending_block(application, today)
    return out


def _agreement(application):
    from .models import BursaryAgreement
    return (BursaryAgreement.objects.select_related('witness_org')
            .filter(application=application).first())


def own_path(path, application):
    """The agreement PDF lives at `<org>/<app>/…` (`storage.build_doc_key`); anything else is not this
    application's file (review L3 — `resolve_org_for_path` reads no org from a 3-segment key)."""
    parts = (path or '').split('/')
    return (len(parts) >= 3 and parts[0] == str(application.owning_organisation_id)
            and parts[1] == str(application.id) and '..' not in parts)


def pdf_url(agreement, application):
    """A short-lived signed link to the signed PDF, or None (no file, not this application's path,
    or storage refused)."""
    from .storage import create_signed_download_url
    if not agreement.pdf_storage_path or not own_path(agreement.pdf_storage_path, application):
        return None
    return create_signed_download_url(agreement.pdf_storage_path, expires_in=PDF_URL_SECONDS)


def platform_signed(agreement):
    """Countersigned: it binds (student + guarantor) and the organisation has signed. The witness
    is non-blocking (`bursary._maybe_activate`), so it is never required here (review H1)."""
    return bool(agreement is not None and agreement.binds and agreement.foundation_signed_at
                and agreement.pdf_storage_path)


def contract_payload(application, *, with_link=False):
    """`{'exists': False}` unless she has a platform-signed agreement with its PDF. The link is
    minted only `with_link` (the tab asks when someone opens the PDF). No IC number anywhere."""
    agreement = _agreement(application)
    if not platform_signed(agreement):
        return {'exists': False}
    signed = [d for d in (agreement.foundation_signed_at, agreement.witness_signed_at) if d]
    parties = [
        {'role': 'student', 'name': agreement.student_signed_name,
         'signed_on': _day(agreement.student_signed_at)},
        {'role': 'guarantor', 'name': agreement.guarantor_name,
         'relationship': agreement.guarantor_relationship,
         'signed_on': _day(agreement.guarantor_signed_at)},
        {'role': 'foundation', 'name': agreement.foundation_signed_by or agreement.foundation_signatory_name,
         'title': agreement.foundation_signatory_title,
         'signed_on': _day(agreement.foundation_signed_at)},
    ]
    if agreement.witness_signed_at:
        # ⚠ Never `witness_signed_by` — that is the officer who RECORDED the witness (review L4).
        org = agreement.witness_org.name if agreement.witness_org else ''
        parties.append({'role': 'witness', 'name': agreement.witness_name or org, 'organisation': org,
                        'signed_on': _day(agreement.witness_signed_at)})
    return {
        'exists': True,
        'executed_on': _day(max(signed)),   # the organisation's date, or the witness's if later
        'witnessed': bool(agreement.witness_signed_at),
        'version': agreement.version or '',
        'parties': parties,
        'pdf_url': pdf_url(agreement, application) if with_link else None,
        'pdf_expires_in': PDF_URL_SECONDS,
    }


# ── The STUDENT's own Funds tab (S5b, 2026-10-30) ──────────────────────────────────────────────────

def student_funds(application):
    """Her OWN money and spending — owner ruling (a), 2026-10-30: totals plus categories, the same
    card her sponsor sees, with NO merchant, NO transaction, NO transaction date. Money by the
    Payments rules (S3's figures), as strings. `spending` is None — not four zeroes — when no
    spending report has reached us for her (the sponsor card's own rule: an empty card would claim
    she has spent nothing). Categories are EVERY category, by code (the screen translates), all time
    — the sponsor card's period, "since your award began" (the officer's Money tab shows THIS TERM, so
    the two Spent figures differ on purpose); `left` floors at zero (a parent may top her wallet up).
    A CLOSED file sends `closed: true` and `remaining: null` — never a promise."""
    from .models import Disbursement, SPEND_CATEGORY_CHOICES, BursarySpendTxn
    from .payments import _remaining, paid_to_date
    from .spend_sponsor import category_rows
    from .spending_import import TX_SPEND
    released = paid_to_date(application)
    releases = (Disbursement.objects.filter(application=application, status__in=Disbursement.PAID)
                .order_by('-released_at', '-id')[:LAST_RELEASES])
    # org-fence: her own application, resolved from her own login by the view.
    rows = list(BursarySpendTxn.objects.filter(application=application, tx_type=TX_SPEND)
                .values_list('category', 'amount'))
    newest = (BursarySpendTxn.objects.filter(application=application)
              .order_by('-imported_at').values_list('imported_at', flat=True).first())
    spending = None
    if rows and newest is not None:
        spent = sum((amount or Decimal('0') for _c, amount in rows), Decimal('0'))
        left = released - spent
        spending = {
            'promised': _money(application.award_amount),
            'released': _money(released),
            'spent': _money(spent),
            'left': _money(left if left > 0 else Decimal('0')),
            'as_at': _day(newest),
            'categories': [{'code': r['code'], 'total': str(r['total'])}
                           for r in category_rows(rows, dict(SPEND_CATEGORY_CHOICES), fold=False)],
        }
    # A CLOSED file promises nothing (review M1): "RM X still to come" would be untrue for a
    # terminated or withdrawn student. `payments._remaining` is unchanged (Payments shares it); this
    # payload simply does not send it once the file has closed.
    from .maintenance_scope import is_in_maintenance
    closed = not is_in_maintenance(application)
    return {
        'closed': closed,
        'award_amount': _money(application.award_amount) if application.award_amount is not None else None,
        'received': _money(released),
        'remaining': None if closed else _money(_remaining(application)),
        # Her own payments: the amount and the day it reached her (never a purchase).
        'releases': [{'amount': _money(d.amount), 'released_on': _day(d.released_at)} for d in releases],
        'spending': spending,
    }


def student_contract(application, *, with_link=False):
    """Her platform-signed contract — `contract_payload` without the version or the recording trail.
    The witness appears only once signed (never the recording officer); no IC number, ever."""
    out = contract_payload(application, with_link=with_link)
    out.pop('version', None)
    return out
