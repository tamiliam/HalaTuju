"""
B40 Assistance Programme — mechanical shortlisting engine (S8 redesign).

Pure functions, deterministic, no DB writes. Academic + income inputs are read
from the linked StudentProfile (the single source of truth); intent / consent /
IPTS from the application. All thresholds come from the cohort.

The rule (settled 2026-05-24 — see docs/scholarship/b40-decision-redesign-plan.md):
  1. Hard gates  — consent + intends public study + NOT IPTS-only        → else REJECT
  2. Academic    — SPM: >= min_spm_a_count at A- AND >= min_spm_bplus_count at B+;
                   STPM: PNGK >= min_stpm_pngk                            → else REJECT
  3. Income      — STR recipient → PASS (bucket A);
                   else per-capita (household_income / household_size)
                   < per_capita_ceiling → PASS (bucket B); else REJECT
  → SHORTLIST if all pass, else REJECT.  No score, no weights, no hardship flags —
    per-capita income already accounts for household size/dependents.
"""
from dataclasses import dataclass

# SPM grades that count as an "A" (A+/A/A- all count — A- is the minimum "A").
A_GRADES = {'A+', 'A', 'A-'}
# Grades at B+ or better (for the "+1 B+" floor → 5 strong subjects).
STRONG_GRADES = A_GRADES | {'B+'}


def _count(grades, allowed):
    if not isinstance(grades, dict):
        return 0
    return sum(
        1 for g in grades.values()
        if isinstance(g, str) and g.strip().upper() in allowed
    )


def count_spm_a_grades(grades):
    """Count A+/A/A- across an SPM grades dict like {'bm': 'A+', ...}."""
    return _count(grades, A_GRADES)


def count_spm_strong_grades(grades):
    """Count grades at B+ or better."""
    return _count(grades, STRONG_GRADES)


@dataclass
class ShortlistResult:
    verdict: str   # 'shortlisted' or 'rejected'
    bucket: str    # 'A' (STR), 'B' (income test), or ''
    reason: str    # human-readable explanation


def _academic_ok(profile, cohort):
    exam = (getattr(profile, 'exam_type', 'spm') or 'spm') if profile else 'spm'
    if exam == 'stpm':
        p = getattr(profile, 'stpm_cgpa', None) if profile else None
        if p is None:
            return False, 'STPM PNGK not provided'
        if p >= cohort.min_stpm_pngk:
            return True, ''
        return False, f'PNGK {p} below {cohort.min_stpm_pngk}'
    grades = getattr(profile, 'grades', None) if profile else None
    a = count_spm_a_grades(grades)
    strong = count_spm_strong_grades(grades)
    if a >= cohort.min_spm_a_count and strong >= cohort.min_spm_bplus_count:
        return True, ''
    return False, (f"{a} at A-, {strong} at B+ "
                   f"(need {cohort.min_spm_a_count} A- and {cohort.min_spm_bplus_count} at B+)")


def _income_ok(profile, cohort):
    """STR recipients pass (bucket A); otherwise per-capita income must clear the ceiling (bucket B)."""
    if profile and getattr(profile, 'receives_str', False):
        return True, 'A', 'STR recipient'
    inc = getattr(profile, 'household_income', None) if profile else None
    size = getattr(profile, 'household_size', None) if profile else None
    if not inc or not size or size <= 0:
        return False, '', 'no STR and household income/size not provided'
    per_capita = inc / size
    if per_capita < cohort.per_capita_ceiling:
        return True, 'B', f'per-capita RM{per_capita:.0f} < RM{cohort.per_capita_ceiling}'
    return False, '', f'per-capita RM{per_capita:.0f} >= RM{cohort.per_capita_ceiling}'


def evaluate(application, cohort):
    """Return a ShortlistResult for the application against the cohort thresholds."""
    profile = getattr(application, 'profile', None)

    # 1. Hard gates
    if not application.consent_to_contact:
        return ShortlistResult('rejected', '', 'no consent to contact')
    if not application.intends_tertiary_2026:
        return ShortlistResult('rejected', '', 'not intending tertiary study this year')
    if application.upu_status == 'ipts':
        return ShortlistResult('rejected', '', 'IPTS-only — outside programme scope')

    # 2. Academic floor
    ok, why = _academic_ok(profile, cohort)
    if not ok:
        return ShortlistResult('rejected', '', f'academic floor: {why}')

    # 3. Income (STR fast-path, else per-capita)
    ok, bucket, why = _income_ok(profile, cohort)
    if not ok:
        return ShortlistResult('rejected', '', f'income: {why}')

    return ShortlistResult('shortlisted', bucket, why)
