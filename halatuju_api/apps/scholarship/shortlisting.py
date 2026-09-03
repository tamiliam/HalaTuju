"""
B40 Assistance Programme — mechanical shortlisting engine (S8 redesign).

Pure functions, deterministic, no DB writes. Academic + income inputs are read
from the linked StudentProfile (the single source of truth); intent / consent /
IPTS from the application. All thresholds come from the cohort.

The rule (settled 2026-05-24 — see docs/scholarship/b40-decision-redesign-plan.md):
  1. Hard gates  — consent + intends public study + NOT IPTS-only        → else REJECT
  2. Academic    — SPM: >= min_spm_a_count at A- AND >= min_spm_bplus_count at B+
                        AND merit point >= min_merit_score;
                   STPM: PNGK >= min_stpm_pngk                            → else REJECT
  3. Income      — STR recipient → PASS (bucket A);
                   else gross household income <= income_ceiling (the DOSM B40 line)
                   → PASS (bucket B);
                   else (above the B40 ceiling) the large-family safety net:
                   per-capita (household_income / household_size) < per_capita_ceiling
                   → PASS (bucket B); else REJECT
  → SHORTLIST if all pass, else REJECT.  No score, no weights, no hardship flags.
  (2026-06: anyone at/under the B40 gross ceiling is in; per-capita now only rescues
   ABOVE-ceiling households with many dependents — it is no longer the primary gate.)

⚠⚠ EVERY THRESHOLD IS OPTIONAL: `None` MEANS THAT TEST IS NOT APPLIED (Sabah S2a, 2026-09-02).
Until now each column was NOT NULL with a default, so every test always ran and an organisation
had no way to say "we do not use this one". BrightPath never asked for an STPM requirement, and a
PNGK floor of 2.90 was nevertheless applied to all nine of its STPM applicants for a whole intake.
The admin screen ticks a requirement by writing a value and unticks it by clearing one — **the
value IS the switch**, deliberately with no companion boolean, because two columns can disagree
and one cannot.

Consequences worth stating rather than discovering:
  * No academic requirement set at all → the academic test passes. That is a legitimate shape for
    a programme to have, and it takes an admin clearing every box on a screen that shows them.
  * Neither income ceiling set → the financial test passes, with bucket '' (not 'B'): 'B' means
    "passed the income test", and there was no income test.
  * `min_merit_score` applies to SPM applicants only — an STPM applicant's comparable figure is
    the PNGK, which is `min_stpm_pngk`.
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
    verdict: str    # 'shortlisted' or 'rejected'
    bucket: str     # 'A' (STR), 'B' (income test), or ''
    reason: str     # human-readable explanation
    category: str = ''  # rejection bucket when rejected: 'merit'|'need'|'ineligible' (engine); '' if shortlisted


def spm_merit(profile):
    """The UPU merit point (0-100) for an SPM profile — grades plus co-curriculum. None when
    there is nothing to score.

    ⚠ THIS DELIBERATELY DOES NOT REUSE `serializers_admin._application_merit_score`, and the
    reason is written on that module: it keys on `held_qualification`, whose own docstring says
    **"NOT A GATE, AND MUST NOT BECOME ONE"** — widening it re-bands live applicants. That
    function answers a DISPLAY question (what to rank this person by in the admin list); this one
    answers a GATE question (does this applicant clear the programme's merit requirement), and the
    engine keys on `exam_type` like every other test here. Same arithmetic, different question.

    The arithmetic itself is not copied — `prepare_merit_inputs` / `calculate_merit_score` in
    `apps.courses.engine` are the single source, and are what the course selector uses too.
    """
    grades = dict((getattr(profile, 'grades', None) or {}) if profile else {})
    if not grades:
        return None
    # The engine's core uses 'history'; profiles store it as 'hist'. Without the rename History
    # reads as a fail and the merit is understated — the same fix the admin list carries.
    if 'hist' in grades:
        grades['history'] = grades.pop('hist')
    from apps.courses.engine import prepare_merit_inputs, calculate_merit_score
    s1, s2, s3 = prepare_merit_inputs(grades, getattr(profile, 'stream_subjects', None) or None)
    coq = getattr(profile, 'coq_score', None)
    result = calculate_merit_score(s1, s2, s3, coq if coq is not None else 0)
    return round(result['final_merit'], 1)


def _academic_ok(profile, cohort):
    """The results test, applying only the requirements this cohort actually sets.

    ⚠ A THRESHOLD OF `None` MEANS THE TEST IS NOT APPLIED (Sabah S2a). Before this, every column
    was NOT NULL with a default, so every test always ran — BrightPath never asked for an STPM
    floor and PNGK >= 2.90 was applied to all nine of its STPM applicants for a whole intake.
    An organisation must be able to say "we do not use this one", and a missing value is how.

    ⚠ NO REQUIREMENT SET AT ALL => PASSES. The academic test is then simply not part of this
    programme, which is a legitimate thing for a programme to be. It is NOT a silent hole: it
    takes an admin clearing every box on a screen that shows what is ticked.
    """
    exam = (getattr(profile, 'exam_type', 'spm') or 'spm') if profile else 'spm'

    if exam == 'stpm':
        floor = cohort.min_stpm_pngk
        if floor is None:
            return True, ''          # this programme sets no STPM requirement
        p = getattr(profile, 'stpm_cgpa', None) if profile else None
        if p is None:
            return False, 'STPM PNGK not provided'
        if p >= floor:
            return True, ''
        return False, f'PNGK {p} below {floor}'

    grades = getattr(profile, 'grades', None) if profile else None
    a = count_spm_a_grades(grades)
    strong = count_spm_strong_grades(grades)
    min_a, min_strong = cohort.min_spm_a_count, cohort.min_spm_bplus_count
    min_merit = getattr(cohort, 'min_merit_score', None)

    failures = []
    if min_a is not None and a < min_a:
        failures.append(f'{a} at A- (need {min_a})')
    if min_strong is not None and strong < min_strong:
        # Stated the way the requirement is set, not the way it is stored: the column holds the
        # TOTAL strong count, and "4 A- and 5 at B+" has been read as nine subjects.
        extra = min_strong - (min_a or 0)
        need = (f'{min_a} at A- plus {extra} more at B+' if min_a is not None and extra > 0
                else f'{min_strong} at B+ or better')
        failures.append(f'{strong} at B+ or better (need {need})')
    if min_merit is not None:
        m = spm_merit(profile)
        if m is None:
            failures.append(f'merit point not available (need {min_merit})')
        elif m < min_merit:
            failures.append(f'merit point {m} below {min_merit}')

    if not failures:
        return True, ''
    return False, '; '.join(failures)


def _income_ok(profile, cohort):
    """Income qualification (2026-06 policy):
      • STR recipient → PASS (bucket A).
      • Gross household income <= the B40 ``income_ceiling`` → PASS (bucket B):
        anyone at or below the DOSM B40 line is in, regardless of household size.
      • Above the B40 ceiling → the large-family safety net: per-capita
        (income / size) < ``per_capita_ceiling`` → PASS (bucket B); else REJECT (need).
    """
    ceiling = cohort.income_ceiling
    pc_ceiling = cohort.per_capita_ceiling

    # ⚠ NEITHER CEILING SET => THE FINANCIAL TEST IS NOT APPLIED (Sabah S2a). The bucket is ''
    # rather than 'B': 'B' means "passed the income test", and there was no income test to pass.
    # The bucket is an admin filter label, never a gate (`views_admin` filters on it, nothing
    # authorises on it), so an honest blank is safe where a borrowed 'B' would be a false record.
    if ceiling is None and pc_ceiling is None:
        return True, '', 'no financial requirement set for this programme'

    # ⚠ STR IS TAKEN AS DECLARED, BY DESIGN (owner, 2026-09-02): the apply form is not where
    # documents are asked for, and shortlisting runs on what the student states. This deliberately
    # differs from `income_engine.has_valid_str` and `profile_engine._gated_str`, which both read
    # the STR *document* — those answer "may we assert this as established fact in writing?", a
    # different question from "does the applicant clear the programme's own need test?".
    if profile and getattr(profile, 'receives_str', False):
        return True, 'A', 'STR recipient'

    inc = getattr(profile, 'household_income', None) if profile else None
    if not inc:
        return False, '', 'no STR and household income not provided'

    # B40 by gross income — at or below the ceiling is in, whatever the family size.
    if ceiling is not None and inc <= ceiling:
        return True, 'B', f'household income RM{inc:.0f} <= RM{ceiling} (B40)'

    # Above the gross ceiling (or none set) — the large-family rescue, if this programme offers it.
    if pc_ceiling is None:
        return False, '', f'income RM{inc:.0f} > RM{ceiling}'
    size = getattr(profile, 'household_size', None) if profile else None
    if not size or size <= 0:
        return False, '', (f'income RM{inc:.0f} > RM{ceiling} '
                           f'and household size not provided')
    per_capita = inc / size
    if per_capita < pc_ceiling:
        return True, 'B', (f'income RM{inc:.0f} above B40 ceiling but per-capita '
                           f'RM{per_capita:.0f} < RM{pc_ceiling}')
    return False, '', (f'income RM{inc:.0f} > RM{ceiling} and per-capita '
                       f'RM{per_capita:.0f} >= RM{pc_ceiling}')


def evaluate(application, cohort):
    """Return a ShortlistResult for the application against the cohort thresholds."""
    profile = getattr(application, 'profile', None)

    # 1. Hard gates → 'ineligible' (out of scope, not a merit/need shortfall)
    if not application.consent_to_contact:
        return ShortlistResult('rejected', '', 'no consent to contact', 'ineligible')
    if not application.intends_tertiary_2026:
        return ShortlistResult('rejected', '', 'not intending tertiary study this year', 'ineligible')
    if application.upu_status == 'ipts':
        return ShortlistResult('rejected', '', 'IPTS-only — outside programme scope', 'ineligible')

    # 2. Academic floor → 'merit'
    ok, why = _academic_ok(profile, cohort)
    if not ok:
        return ShortlistResult('rejected', '', f'academic floor: {why}', 'merit')

    # 3. Income (STR fast-path, else per-capita) → 'need'
    ok, bucket, why = _income_ok(profile, cohort)
    if not ok:
        return ShortlistResult('rejected', '', f'income: {why}', 'need')

    return ShortlistResult('shortlisted', bucket, why)
