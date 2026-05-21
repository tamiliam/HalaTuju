"""
B40 Assistance Programme — mechanical shortlisting engine.

Pure functions: given an application's fields and a cohort's thresholds, decide
FAIL / BUCKET_A / BUCKET_B and explain why. No DB access, so it is trivially
testable and deterministic (a small golden master). All thresholds come from the
cohort, so a round can be re-tuned without code changes.
"""
from dataclasses import dataclass

# How far over the income ceiling still counts as "marginal" (Bucket B).
INCOME_MARGIN_FACTOR = 1.15
# STPM PNGK band below the minimum that still counts as "marginal".
STPM_PNGK_MARGIN = 0.3

OK = 'ok'
MARGINAL = 'marginal'
FAIL = 'fail'


@dataclass
class ShortlistResult:
    status: str   # 'shortlisted' or 'rejected'
    bucket: str   # 'A', 'B' or ''
    reason: str   # human-readable explanation


def _academic_status(app, cohort):
    if app.qualification == 'stpm':
        p = app.stpm_pngk
        if p is None:
            return FAIL, 'STPM PNGK not provided'
        if p >= cohort.min_stpm_pngk:
            return OK, ''
        if p >= cohort.min_stpm_pngk - STPM_PNGK_MARGIN:
            return MARGINAL, f'PNGK {p} just below {cohort.min_stpm_pngk}'
        return FAIL, f'PNGK {p} below {cohort.min_stpm_pngk}'
    # SPM
    a = app.spm_a_count
    if a is None:
        return FAIL, 'SPM A-count not provided'
    if a >= cohort.min_spm_a_count:
        return OK, ''
    if a >= cohort.min_spm_a_count - cohort.bucket_b_margin:
        return MARGINAL, f"{a} A's (need {cohort.min_spm_a_count})"
    return FAIL, f"{a} A's (need {cohort.min_spm_a_count})"


def _income_status(app, cohort):
    ceiling = cohort.income_ceiling
    inc = app.household_income
    has_str = app.receives_str
    if ceiling is None:
        # Income band not configured for this cohort — not assessed here.
        return OK, ''
    if inc is None:
        # No income figure: trust STR (government-verified B40), else can't confirm.
        return (OK, '') if has_str else (FAIL, 'No income figure and no STR')
    if inc <= ceiling:
        return OK, ''
    if inc <= ceiling * INCOME_MARGIN_FACTOR:
        return MARGINAL, f'income RM{inc} just over RM{ceiling}'
    # Well over the ceiling: STR holders are flagged for review, not auto-rejected.
    if has_str:
        return MARGINAL, f'income RM{inc} over RM{ceiling} but holds STR'
    return FAIL, f'income RM{inc} over RM{ceiling}'


def _intent_status(app):
    return (OK, '') if app.intends_tertiary_2026 else (FAIL, 'not intending tertiary study this year')


def _consent_status(app):
    return (OK, '') if app.consent_to_contact else (FAIL, 'no consent to contact')


def evaluate(app, cohort):
    """Return a ShortlistResult for the application against the cohort thresholds."""
    checks = {
        'academic': _academic_status(app, cohort),
        'income': _income_status(app, cohort),
        'intent': _intent_status(app),
        'consent': _consent_status(app),
    }
    fails = {k: v[1] for k, v in checks.items() if v[0] == FAIL}
    marginals = {k: v[1] for k, v in checks.items() if v[0] == MARGINAL}

    if not fails and not marginals:
        return ShortlistResult('shortlisted', 'A', '')
    if not fails and len(marginals) == 1:
        k, why = next(iter(marginals.items()))
        return ShortlistResult('shortlisted', 'B', f'Marginal on {k}: {why}')
    bits = [f'{k}: {why}' for k, why in {**fails, **marginals}.items()]
    return ShortlistResult('rejected', '', '; '.join(bits))
