"""
B40 Assistance Programme — mechanical shortlisting engine.

Pure functions. The academic + income inputs are read from the linked
StudentProfile (the single source of truth); intent + consent are per-application.
No DB writes, deterministic, all thresholds from the cohort.
"""
from dataclasses import dataclass

# How far over the income ceiling still counts as "marginal" (Bucket B).
INCOME_MARGIN_FACTOR = 1.15
# STPM PNGK band below the minimum that still counts as "marginal".
STPM_PNGK_MARGIN = 0.3

OK = 'ok'
MARGINAL = 'marginal'
FAIL = 'fail'

# SPM grades that count as an "A" (A+, A and A- all count, matching how the B40
# candidate profiles tally "10 A's incl. A+ and A-").
A_GRADES = {'A+', 'A', 'A-'}


def count_spm_a_grades(grades):
    """Count A+/A/A- across an SPM grades dict like {'bm': 'A+', ...}."""
    if not isinstance(grades, dict):
        return 0
    return sum(
        1 for g in grades.values()
        if isinstance(g, str) and g.strip().upper() in A_GRADES
    )


@dataclass
class ShortlistResult:
    status: str   # 'shortlisted' or 'rejected'
    bucket: str   # 'A', 'B' or ''
    reason: str   # human-readable explanation


def _academic_status(profile, cohort):
    exam = (getattr(profile, 'exam_type', 'spm') or 'spm') if profile else 'spm'
    if exam == 'stpm':
        p = getattr(profile, 'stpm_cgpa', None) if profile else None
        if p is None:
            return FAIL, 'STPM PNGK not provided'
        if p >= cohort.min_stpm_pngk:
            return OK, ''
        if p >= cohort.min_stpm_pngk - STPM_PNGK_MARGIN:
            return MARGINAL, f'PNGK {p} just below {cohort.min_stpm_pngk}'
        return FAIL, f'PNGK {p} below {cohort.min_stpm_pngk}'
    a = count_spm_a_grades(getattr(profile, 'grades', None) if profile else None)
    if a >= cohort.min_spm_a_count:
        return OK, ''
    if a >= cohort.min_spm_a_count - cohort.bucket_b_margin:
        return MARGINAL, f"{a} A's (need {cohort.min_spm_a_count})"
    return FAIL, f"{a} A's (need {cohort.min_spm_a_count})"


def _income_status(profile, cohort):
    ceiling = cohort.income_ceiling
    inc = getattr(profile, 'household_income', None) if profile else None
    has_str = bool(getattr(profile, 'receives_str', False)) if profile else False
    if ceiling is None:
        return OK, ''
    if inc is None:
        return (OK, '') if has_str else (FAIL, 'No income figure and no STR')
    if inc <= ceiling:
        return OK, ''
    if inc <= ceiling * INCOME_MARGIN_FACTOR:
        return MARGINAL, f'income RM{inc} just over RM{ceiling}'
    if has_str:
        return MARGINAL, f'income RM{inc} over RM{ceiling} but holds STR'
    return FAIL, f'income RM{inc} over RM{ceiling}'


def _intent_status(application):
    return (OK, '') if application.intends_tertiary_2026 else (FAIL, 'not intending tertiary study this year')


def _consent_status(application):
    return (OK, '') if application.consent_to_contact else (FAIL, 'no consent to contact')


def evaluate(application, cohort):
    """Return a ShortlistResult for the application against the cohort thresholds.
    Academic + income are read from application.profile; intent + consent from the application."""
    profile = getattr(application, 'profile', None)
    checks = {
        'academic': _academic_status(profile, cohort),
        'income': _income_status(profile, cohort),
        'intent': _intent_status(application),
        'consent': _consent_status(application),
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
