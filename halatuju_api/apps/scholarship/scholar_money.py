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
Spending page's rule; without it the key is ABSENT from the payload, not null. Categories and totals
from her `SPEND` transactions since the start of the S4b result term she is IN (its STORED
`term_starts_on`), else since she was funded. The officer sees the Spending page's arithmetic, not
the sponsor's floored "left".

CONTRACT. A platform-signed agreement only (owner ruling, 2026-10-29): an EXECUTED `BursaryAgreement`
with its stored PDF; anything else is "No contract on file". The signing feature flag is NOT read —
an executed agreement stays viewable when signing is switched off. The PDF is a signed URL into the
private bucket, minted per request, expiring in `PDF_URL_SECONDS`, and refused when the storage
path's organisation is not the application's (the tenant path check every document reader uses).
The parties carry names, roles and dates — never an IC number.
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
    current = (ResultsExpectation.objects.filter(application=application, term_starts_on__lte=today)
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
        'categories': [{'code': r['code'], 'label': r['label'], 'total': str(r['total'])}
                       for r in category_rows(rows, dict(SPEND_CATEGORY_CHOICES))],
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


def pdf_url(agreement, application):
    """A short-lived signed link to the executed PDF, or None (no file, a path from another
    organisation, or storage refused)."""
    from .storage import create_signed_download_url, resolve_org_for_path
    if not agreement.pdf_storage_path:
        return None
    path_org = resolve_org_for_path(agreement.pdf_storage_path)
    if path_org is not None and path_org != application.owning_organisation_id:
        return None
    return create_signed_download_url(agreement.pdf_storage_path, expires_in=PDF_URL_SECONDS)


def contract_payload(application):
    """`{'exists': False}` unless she has an EXECUTED agreement with its PDF. No IC number anywhere."""
    agreement = _agreement(application)
    if agreement is None or not agreement.is_executed or not agreement.pdf_storage_path:
        return {'exists': False}
    executed = max(d for d in (agreement.foundation_signed_at, agreement.witness_signed_at) if d)
    return {
        'exists': True,
        'executed_on': _day(executed),
        'version': agreement.version or '',
        'parties': [
            {'role': 'student', 'name': agreement.student_signed_name,
             'signed_on': _day(agreement.student_signed_at)},
            {'role': 'guarantor', 'name': agreement.guarantor_name,
             'relationship': agreement.guarantor_relationship,
             'signed_on': _day(agreement.guarantor_signed_at)},
            {'role': 'foundation', 'name': agreement.foundation_signed_by or agreement.foundation_signatory_name,
             'title': agreement.foundation_signatory_title,
             'signed_on': _day(agreement.foundation_signed_at)},
            {'role': 'witness', 'name': agreement.witness_name or agreement.witness_signed_by,
             'organisation': agreement.witness_org.name if agreement.witness_org else '',
             'signed_on': _day(agreement.witness_signed_at)},
        ],
        'pdf_url': pdf_url(agreement, application),
        'pdf_expires_in': PDF_URL_SECONDS,
    }
