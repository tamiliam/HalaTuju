"""A funded student's STANDING (student maintenance Sprint 4a, 2026-10-29) — for STAFF.

Derived, never stored, from her latest ACCEPTED result (``results_review.accepted``) and the
organisation's settings (Organisation → Settings → Configuration, the ``maintenance`` group):

  * ``performing``      — CGPA at or above ``maintenance_min_cgpa`` (3.00 by default — the contract),
                          or the accepted result marks her graduation;
  * ``underperforming`` — below the minimum, at or above ``maintenance_failing_cgpa`` (2.00);
  * ``failing``         — below the failing line;
  * ``awaiting_review`` — no accepted result yet, but one is waiting for an officer;
  * ``no_result_yet``   — nothing accepted and nothing waiting (or an accepted result with no CGPA).

⚠ STAFF ONLY. A student is never shown a standing word (her page shows her results and their review
status); a sponsor never sees it either — the sponsor band (``pool.derive_progress_state``) is a
separate, coarser reading of the same accepted results. Changing a threshold on the settings page
moves every chip with no deploy: nothing here is hard-coded but the platform defaults in the registry.
"""
import re
from decimal import Decimal

PERFORMING = 'performing'
UNDERPERFORMING = 'underperforming'
FAILING = 'failing'
AWAITING_REVIEW = 'awaiting_review'
NO_RESULT_YET = 'no_result_yet'
STANDINGS = (PERFORMING, UNDERPERFORMING, FAILING, AWAITING_REVIEW, NO_RESULT_YET)


def thresholds(organisation):
    """(minimum, failing) as Decimals, from the organisation's settings or the platform defaults."""
    from apps.courses import org_config
    return (Decimal(str(org_config.value(organisation, 'maintenance_min_cgpa'))),
            Decimal(str(org_config.value(organisation, 'maintenance_failing_cgpa'))))


def standing_for(cgpa, graduated, *, has_accepted, has_pending, minimum, failing):
    """The pure rule, on facts a caller already holds (a list row's annotations, or one file)."""
    if not has_accepted:
        return AWAITING_REVIEW if has_pending else NO_RESULT_YET
    if graduated:
        return PERFORMING
    if cgpa is None:
        return NO_RESULT_YET
    value = Decimal(str(cgpa))
    if value < failing:
        return FAILING
    if value < minimum:
        return UNDERPERFORMING
    return PERFORMING


def standing_of(application):
    """One application's standing (two small queries: the latest accepted result, any pending)."""
    from .results_review import PENDING, latest_accepted
    latest = latest_accepted(application)
    minimum, failing = thresholds(application.owning_organisation)
    return standing_for(
        latest.cgpa if latest else None, bool(latest and latest.graduated),
        has_accepted=latest is not None,
        has_pending=application.semester_results.filter(review_status=PENDING).exists(),
        minimum=minimum, failing=failing)


# ── The contract guard ──────────────────────────────────────────────────────────────────────────
#: A CGPA written in prose ("a CGPA of at least 3.00", "PNGK 3.0"): one digit 0-4, a point, 1-2 digits.
_CGPA_IN_TEXT = re.compile(r'(?<![\d.])([0-4]\.\d{1,2})(?![\d.])')


def cgpa_in_text(text):
    """The CGPA a contract's progress standard states, as a Decimal — or None when it states none."""
    match = _CGPA_IN_TEXT.search(text or '')
    return Decimal(match.group(1)) if match else None


def contract_warnings(organisation):
    """For the settings page: each ACTIVE contract template whose progress standard states a CGPA
    other than the organisation's minimum (`contract_differs`), or states none (`contract_unstated`).
    A warning, never a block — the wording is the organisation's to write."""
    from .models import ContractTemplate
    if organisation is None:
        return []
    minimum, _failing = thresholds(organisation)
    out = []
    for tpl in ContractTemplate.objects.filter(organisation=organisation, status='active').order_by('id'):
        stated = cgpa_in_text(tpl.progress_standard_en)
        if stated is None:
            out.append({'code': 'contract_unstated', 'key': 'maintenance_min_cgpa',
                        'template': tpl.title_en or '', 'stated': None})
        elif stated != minimum:
            out.append({'code': 'contract_differs', 'key': 'maintenance_min_cgpa',
                        'template': tpl.title_en or '', 'stated': f'{stated:.2f}'})
    return out
