"""A funded student's STANDING (student maintenance Sprint 4a, 2026-10-29) — for STAFF.

Derived, never stored, from her latest ACCEPTED result (``results_review.accepted``) and the
organisation's settings (Organisation → Settings → Configuration, the ``maintenance`` group):

  * ``performing``      — CGPA at or above ``maintenance_min_cgpa`` (3.00 by default — the contract),
                          or the accepted result marks her graduation;
  * ``underperforming`` — below the minimum, at or above ``maintenance_failing_cgpa`` (2.00);
  * ``failing``         — below the failing line;
  * ``not_submitted``   — S4b: a result term is past its due date AND the grace
                          (``results_expectations``), and nothing is waiting for review;
  * ``awaiting_review`` — no accepted result yet, but one is waiting for an officer;
  * ``no_result_yet``   — nothing accepted and nothing waiting (or an accepted result with no CGPA).

⚠ STAFF ONLY. A student is never shown a standing word (her page shows her results and their review
status); a sponsor never sees it either. The sponsor band (``pool.derive_progress_state``) is a
coarser reading of the same accepted result, and its ``needs_attention`` IS this module's
``failing`` (``is_failing``) — ONE line for both audiences (S4a review M2). Changing a threshold on the settings page
moves every chip with no deploy: nothing here is hard-coded but the platform defaults in the registry.
"""
import re
from decimal import Decimal

PERFORMING = 'performing'
UNDERPERFORMING = 'underperforming'
FAILING = 'failing'
AWAITING_REVIEW = 'awaiting_review'
NO_RESULT_YET = 'no_result_yet'
NOT_SUBMITTED = 'not_submitted'
STANDINGS = (PERFORMING, UNDERPERFORMING, FAILING, NOT_SUBMITTED, AWAITING_REVIEW, NO_RESULT_YET)


def thresholds(organisation):
    """(minimum, failing) as Decimals, from the organisation's settings or the platform defaults."""
    from apps.courses import org_config
    return (Decimal(str(org_config.value(organisation, 'maintenance_min_cgpa'))),
            Decimal(str(org_config.value(organisation, 'maintenance_failing_cgpa'))))


def below(cgpa, line):
    """THE comparison, strictly below — a CGPA exactly ON a line is not below it."""
    return Decimal(str(cgpa)) < line


def is_failing(cgpa, organisation):
    """Below the organisation's failing CGPA — the staff `failing` standing AND the sponsor band's
    `needs_attention` (one rule, two audiences)."""
    from apps.courses import org_config
    return below(cgpa, Decimal(str(org_config.value(organisation, 'maintenance_failing_cgpa'))))


def standing_for(cgpa, graduated, *, has_accepted, has_pending, minimum, failing, overdue=False):
    """The pure rule, on facts a caller already holds (a list row's annotations, or one file).
    `overdue` (S4b): an open result term is past its due date and the grace. It wins over every
    CGPA reading — she owes a result — unless one is already waiting for the officer."""
    if overdue and not has_pending:
        return NOT_SUBMITTED
    if not has_accepted:
        return AWAITING_REVIEW if has_pending else NO_RESULT_YET
    if graduated:
        return PERFORMING
    if cgpa is None:
        return NO_RESULT_YET
    value = Decimal(str(cgpa))
    if below(value, failing):
        return FAILING
    if below(value, minimum):
        return UNDERPERFORMING
    return PERFORMING


def standing_of(application):
    """One application's standing (two small queries: the latest accepted result, any pending)."""
    from .results_expectations import not_submitted
    from .results_review import has_pending, latest_accepted
    latest = latest_accepted(application)
    minimum, failing = thresholds(application.owning_organisation)
    return standing_for(
        latest.cgpa if latest else None, bool(latest and latest.graduated),
        has_accepted=latest is not None, has_pending=has_pending(application),
        minimum=minimum, failing=failing, overdue=not_submitted(application))


# ── The contract guard ──────────────────────────────────────────────────────────────────────────
# A CGPA counts only when the text NAMES one — a bare "3.1" is as likely a clause number (the live
# BrightPath template's academic line sits in clause 4.1.V). The phrase, then up to 80 characters
# without a digit, then the number; or the number straight before the phrase ("3.00 CGPA").
_PHRASE = r'(?:\bC?GPA\b|\bPNGK\b|\bgrade[\s-]+point[\s-]+average\b|\bpurata\s+nilai\s+gred\b)'
_NUMBER = r'(?<![\d.])([0-4]\.\d{1,2})(?!\d)(?!\.\d)'
_CGPA_AFTER_PHRASE = re.compile(_PHRASE + r'[^\d]{0,80}?' + _NUMBER, re.IGNORECASE)
_CGPA_BEFORE_PHRASE = re.compile(_NUMBER + r'\s*\(?\s*' + _PHRASE, re.IGNORECASE)


def cgpas_in_text(text):
    """Every CGPA the text STATES (next to a GPA / CGPA / PNGK / grade point average phrase), as
    Decimals in order of appearance — empty when it states none."""
    found = []
    for rx in (_CGPA_AFTER_PHRASE, _CGPA_BEFORE_PHRASE):
        found += [(m.start(1), Decimal(m.group(1))) for m in rx.finditer(text or '')]
    return [value for _at, value in sorted(set(found))]


def contract_warnings(organisation):
    """For the settings page: each ACTIVE contract template whose English wording — the progress
    standard AND every clause body — states no CGPA equal to the organisation's minimum
    (`contract_differs`, naming the first it states), or states none (`contract_unstated`).
    A warning, never a block — the wording is the organisation's to write."""
    from .models import ContractTemplate
    if organisation is None:
        return []
    minimum, _failing = thresholds(organisation)
    out = []
    for tpl in (ContractTemplate.objects.filter(organisation=organisation, status='active')
                .prefetch_related('clauses').order_by('id')):
        clauses = sorted(tpl.clauses.all(), key=lambda c: c.order)
        stated = [v for text in [tpl.progress_standard_en] + [c.body_en for c in clauses]
                  for v in cgpas_in_text(text)]
        if not stated:
            out.append({'code': 'contract_unstated', 'key': 'maintenance_min_cgpa',
                        'template': tpl.title_en or '', 'stated': None})
        elif minimum not in stated:
            out.append({'code': 'contract_differs', 'key': 'maintenance_min_cgpa',
                        'template': tpl.title_en or '', 'stated': f'{stated[0]:.2f}'})
    return out
