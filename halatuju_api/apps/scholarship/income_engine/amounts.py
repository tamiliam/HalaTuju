"""What the household earns: the SGD conversion, the earner monthly figure, income per
capita, whether the income test is configured, and the headroom under the threshold.

Moved here VERBATIM from `income_engine.py` at code health H16 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from __future__ import annotations

import re

from .evidence import declared_amount, has_income_support_doc, has_valid_str
from .identity_checks import _cluster_docs
from .salary_figures import (_SLIP_EPF_HI, _SLIP_EPF_LO, _doc_fields, _epf_monthly_salary, _parse_rm,
                             _salary_monthly_amount, epf_band_salary)


# Foreign (Singapore) salary → MYR for the B40 means-test (owner 2026-07-05). A Malaysian working
# in Singapore submits an S$ payslip; counting the S$ figure as ringgit understates income ~3× and
# produces a FALSE B40 (e.g. #105: S$3,114 read as "RM3,114"). Convert an SGD slip to MYR at the
# configured rate — but ONLY while the application is still IN REVIEW; a case already decided
# (recommended and beyond) keeps its as-recorded basis, so the correction never disturbs a made
# decision (owner: "leave out #75").
_INCOME_CONVERT_STATUSES = frozenset({'submitted', 'shortlisted', 'profile_complete',
                                      'interviewing', 'interviewed'})
# The STRUCTURAL Singapore-company suffix: every Singapore company is a "Pte Ltd" / "Private
# Limited" (a Malaysian company is "Sdn Bhd"). This is the systemic anchor — NOT any particular
# company name — so ANY Singapore employer's payslip is detected. Dots/spacing normalised.
_SGD_EMPLOYER_RE = re.compile(r'\bpte\s*ltd\b|\bprivate\s+limited\b')


def _slip_is_sgd(fields):
    """True when a salary slip's amounts are in Singapore dollars, from two STRUCTURAL signals (no
    hard-coded company names):
      * the employer is a Singapore company — 'Pte Ltd' / 'Private Limited' (Malaysian = 'Sdn Bhd'),
      * OR the read ``currency`` is SGD / S$ — which the extractor sets from any Singapore tell-tale
        (an S$ sign, CPF / SDL deductions, a Singapore address / FIN), so a non-'Pte Ltd' issuer such
        as a statutory board or co-operative is still caught.
    The employer suffix is deterministic and stable across re-runs; the currency covers the rest."""
    emp = re.sub(r'[.\s]+', ' ', (fields.get('employer') or '').lower())
    if _SGD_EMPLOYER_RE.search(emp):
        return True
    cur = (fields.get('currency') or '').strip().upper()
    return 'SGD' in cur or 'S$' in cur


def sgd_to_myr_rate():
    from django.conf import settings
    try:
        return float(getattr(settings, 'SGD_TO_MYR_RATE', 3.15) or 3.15)
    except (TypeError, ValueError):
        return 3.15


def _to_myr(amt, fields, application):
    """A foreign (SGD) salary expressed in MYR for the means-test, at the configured rate — but only
    for an application still IN REVIEW. A decided case (recommended+) keeps its as-recorded figure."""
    if amt is None or not _slip_is_sgd(fields):
        return amt
    if (getattr(application, 'status', '') or '') not in _INCOME_CONVERT_STATUSES:
        return amt
    return amt * sgd_to_myr_rate()


def earner_monthly_income(application, member):
    """A working member's estimated MONTHLY income from their documents + the source.
    The salary slip's gross is primary; failing that, the EPF statement (the statutory-rate
    salary reverse, or 0 when unemployed); failing that, a DECLARED informal amount.
    Returns ``(amount: float | None, source)`` where source is
    ``'salary' | 'epf_estimate' | 'declared_str' | 'declared_evidenced' | 'declared_unproven' | 'unknown'``.

    Declared informal income (Phase 2A, P5b): a member with no payslip/EPF may declare an
    average monthly wage. It is ACCEPTED as a real figure when the household has a valid STR
    (``declared_str`` — the STR is the means-test) OR a supporting income document backs it
    (``declared_evidenced``); otherwise it is UNPROVEN — returns ``(None, 'declared_unproven')``
    so per-capita stays 'not all known' and the headroom band falls to Unsure until evidence
    lands (never inflates income on an unbacked self-report)."""
    for slip in _cluster_docs(application, member, 'salary_slip'):
        f = _doc_fields(slip)
        amt = _salary_monthly_amount(f)
        if amt:
            return _to_myr(amt, f, application), 'salary'   # SGD → MYR when the slip is Singaporean
    for epf in _cluster_docs(application, member, 'epf'):
        sal = epf_band_salary(_doc_fields(epf))     # TD-323: the floor, for the band figure only
        if sal is not None:
            return sal, 'epf_estimate'
    declared = declared_amount(application, member)
    if declared is not None:
        if has_valid_str(application):
            return float(declared), 'declared_str'
        if has_income_support_doc(application, member):
            return float(declared), 'declared_evidenced'
        return None, 'declared_unproven'
    return None, 'unknown'


def slip_epf_divergence(application, member):
    """#9: when a member has BOTH a salary slip (gross) AND an EPF statement (monthly
    contribution), cross-check the payslip salary against the EPF-implied salary
    (contribution ÷ 0.24). Returns ``{slip, epf_implied, ratio}`` only when they diverge
    beyond the generous ``_SLIP_EPF_LO``–``_SLIP_EPF_HI`` band, else None (also None when
    either figure is missing). A SOFT officer signal — overtime / late pay routinely move
    the two apart, so it is a 'verify at interview' nudge, never a gate."""
    slip = None
    for s in _cluster_docs(application, member, 'salary_slip'):
        amt = _parse_rm(_doc_fields(s).get('gross_income') or _doc_fields(s).get('net_income'))
        if amt:
            slip = amt
            break
    epf_implied = None
    for e in _cluster_docs(application, member, 'epf'):
        sal = _epf_monthly_salary(_doc_fields(e))
        if sal:                              # >0 (an unemployed EPF, 0.0, has no salary to compare)
            epf_implied = sal
            break
    if not slip or not epf_implied:
        return None
    ratio = slip / epf_implied
    if _SLIP_EPF_LO <= ratio <= _SLIP_EPF_HI:
        return None
    return {'slip': round(slip, 2), 'epf_implied': epf_implied, 'ratio': round(ratio, 2)}


def income_per_capita(application, members):
    """``(per_capita, all_known)`` — the document-derived household monthly income
    (sum of every working member's income) divided by the household size. ``all_known``
    is False when any member's income couldn't be read (so the per-capita is unreliable
    → the verdict falls to a human/interview). ``per_capita`` is None when income is
    unknown or there's no household size."""
    total, all_known = 0.0, True
    for m in (members or []):
        amt, _src = earner_monthly_income(application, m)
        if amt is None:
            all_known = False
        else:
            total += amt
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    if not all_known or not size:
        return None, all_known
    return total / size, all_known


# A breach-room below one person's share of the gift's line (RM/month) means one undeclared
# earner could plausibly push the household over the gift's income cut-off - so an uncorroborated
# household size can't carry a confident pass (str-proof-spec.md §7.1: "≈ one more head at the
# line"). Criteria S3a (owner, 26 Nov 2026): the yardstick is the gift's OWN line - its
# per-person line, or (a gift with only a household line) that line's share per person - never
# a universal RM1,584. See `_per_person_line`.


def income_test_configured(application):
    """Does this gift apply a household-income test AT ALL?

    ⚠ NOT the same question as "could we compute the household's income?", and until
    2026-09-10 the officer screen could not tell them apart. ``income_headroom`` returns
    'unknown' for BOTH — see its no-line guard — and 'unknown' prints
    *"income can't be document-verified (informal / no payslip)"*. On a gift that runs no
    means test that sentence is simply false: the payslips may be perfectly readable.

    Both ceilings NULL = the financial test is not applied (``Cohort.income_ceiling``'s own
    help_text). Measured on production 2026-09-09: BrightPath ``b40-2026`` sets 5860/1584,
    the ``test`` round sets NULL/NULL — so this is a live configuration, not a hypothetical.

    Deliberately a PREDICATE rather than a new ``income_headroom`` band: the band feeds the
    verdict tiles on both routes, and widening its return set would put every caller in
    scope of a wording sprint. This asks the cohort directly and changes no maths.
    """
    from apps.scholarship.criteria_read import income_ceilings
    gross_ceiling, pc_ceiling, _mode = income_ceilings(getattr(application, 'cohort', None))
    return bool(gross_ceiling or pc_ceiling)


def income_headroom(application, members):
    """Margin-graded B40 confidence for the SALARY route (docs/scholarship/str-proof-spec.md §7.1).

    Returns ``(band, ctx)`` where band is:
      'unknown'  — income or household size couldn't be computed → assess at interview.
      'over'     — household income clears BOTH the gross ceiling AND the per-capita safety net →
                   above the B40 line (never auto-rejected; → interview).
      'unsure'   — B40, but only thinly: an undeclared earner could plausibly breach the line
                   (breach-room < one per-capita head), OR an earner's income couldn't be read.
                   The household size isn't corroborated enough to bank the pass.
      'probable' — B40 with large breach-room: an undeclared earner would need an implausibly high
                   wage to breach → confident-enough for 🔵 (interview confirms; GREEN is reserved
                   for a corroborated household, which the family roster will later supply).

    The income test holds while gross ≤ the gift's household line OR gross ÷ size < its
    per-person line (TD-771: on the household line passes, on the per-person line does not) —
    the household line is primary, the per-person line a safety net above it. ``breach_room`` is how much more monthly
    income would tip the household out; grading by it is what separates #13 (thin → unsure) from the
    SARA case (large → probable). ``ctx`` carries the figures for the verdict copy / interview note."""
    # Criteria Sprint 2: the ceilings of the tree the gate reads ('any' meaning, see
    # `criteria.income_ceilings`), so every figure is the gift's own rule, never a universal one.
    # TD-771 (owner ruling, 26 Nov 2026): the income test passes on EITHER line, exactly as the
    # gate (`criteria.income_ok`) reads it - the household line passes ON the line (at most RM X),
    # the per-person line does NOT (income per person must be UNDER RM Y). 'over' only when BOTH
    # fail. Criteria S3a (owner, 26 Nov 2026): a gift with only ONE of the two lines is judged on
    # that line alone (it used to band 'unknown' without a per-person line), and the 'thin'
    # yardstick is the gift's own per-person figure (`_per_person_line`), never a fixed RM1,584.
    from apps.scholarship.criteria_read import income_ceilings
    gross_ceiling, pc_ceiling, _mode = income_ceilings(getattr(application, 'cohort', None))
    size = getattr(getattr(application, 'profile', None), 'household_size', None)
    pc, all_known = income_per_capita(application, members)
    if pc is None or not size or not (gross_ceiling or pc_ceiling):
        return 'unknown', {'all_known': all_known}
    gross = pc * size
    # The more generous line (either may be absent - code-health S4 #14 made this the shared
    # test for BOTH routes).
    ceiling = max([c for c in (gross_ceiling, (pc_ceiling or 0) * size) if c])
    breach_room = ceiling - gross
    per_person_line = _per_person_line(gross_ceiling, pc_ceiling, size)
    ctx = {'gross': int(round(gross)), 'per_capita': int(round(pc)), 'size': size,
           'breach_room': int(round(breach_room)), 'all_known': all_known,
           'gross_ceiling': int(gross_ceiling or 0), 'per_capita_ceiling': int(per_person_line)}
    # `gross` is pc x size, so round away the float noise before comparing it with a ringgit line.
    # Absent line = not tested, exactly as the gate (`criteria.income_ok`) reads `None`.
    passes_household = gross_ceiling is not None and round(gross, 6) <= gross_ceiling
    passes_per_person = pc_ceiling is not None and pc < pc_ceiling
    if not (passes_household or passes_per_person):
        return 'over', ctx
    if not all_known or breach_room < per_person_line:
        return 'unsure', ctx
    return 'probable', ctx


def _per_person_line(gross_ceiling, pc_ceiling, size):
    """One person's share of the gift's income cut-off (RM/month): its per-person line, or -
    a gift with only a household line - that line divided by the household size. It is both the
    'thin margin' yardstick (≈ one more head at the line) and the per-person figure the officer
    copy quotes (``ctx['per_capita_ceiling']``), so neither ever names a line the gift lacks."""
    return float(pc_ceiling) if pc_ceiling else float(gross_ceiling) / size
