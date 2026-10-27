"""
B40 Assistance Programme — mechanical shortlisting engine (S8 redesign).

Pure functions, deterministic, no DB writes. Academic + income inputs are read
from the linked StudentProfile (the single source of truth); intent / consent /
IPTS from the application. All thresholds come from the cohort.

The rule (settled 2026-05-24 — see docs/scholarship/b40-decision-redesign-plan.md):
  1. Hard gates  — consent + intends public study + NOT IPTS-only
                   + BORN IN one of `allowed_birth_states`, when the intake sets any
                     (request #31: the IC's place-of-birth code; abroad, code 82 or an
                     unreadable IC fail — `birth_state.check`)                → else REJECT
  2. Academic    — SPM: >= min_spm_a_count at A- AND >= min_spm_bplus_count at B+
                        AND >= min_spm_credit_count at C or better
                        AND merit point >= min_merit_score;
                   STPM: PNGK >= min_stpm_pngk                            → else REJECT
                   Matriculation / Asasi / Diploma (third results route S2a): the OVERALL
                   CGPA (`exam_questions.overall_cgpa`) >= min_stpm_pngk  → else REJECT
                   STPM-level held but NO `min_stpm_pngk` (owner ruling D16c): the intake is
                   SPM-only, so the SPM GRADE bars above (A-, B+, credits; not the merit
                   point — D3) on their SPM grades                        → else REJECT
                   (a Diploma not from a PUBLIC institution is a hard gate, step 1: D5)
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

⚠ EXCEPT `min_stpm_pngk` (owner ruling D16c, 2026-10-27): blank no longer means "no STPM-level test,
pass" — it makes the intake SPM-ONLY, so an STPM / Matriculation / Asasi / Diploma holder is tested on
the SPM GRADE bars with their SPM grades (not `min_merit_score`, which stays SPM-only by D3).
The same blank tells the document rules the intake asks for no STPM-level results (`results_route.gift_asks_higher`).

Consequences worth stating rather than discovering:
  * No academic requirement set at all → the academic test passes. That is a legitimate shape for
    a programme to have, and it takes an admin clearing every box on a screen that shows them.
  * Neither income ceiling set → the financial test passes, with bucket '' (not 'B'): 'B' means
    "passed the income test", and there was no income test.
  * `min_merit_score` applies to SPM applicants only — an STPM applicant's comparable figure is
    the PNGK, which is `min_stpm_pngk`. The same holds for the third route (owner ruling D3,
    2026-10-25): Matriculation / Asasi / Diploma face the CGPA floor only.
  * `allowed_birth_states` is a LIST, so "off" is the EMPTY list rather than `None` — the same
    switch in list form. Off means the IC is not read at all, so an unreadable IC passes it.
"""
from dataclasses import dataclass

from apps.courses.exam_questions import (QUALIFICATION_LABELS, THIRD_ROUTE, diploma_is_public,
                                         results_held, spm_grades_for, third_route_overall)

from .birth_state import check as check_birth_state

# SPM grades that count as an "A" (A+/A/A- all count — A- is the minimum "A").
A_GRADES = {'A+', 'A', 'A-'}
# Grades at B+ or better (for the "+1 B+" floor → 5 strong subjects).
STRONG_GRADES = A_GRADES | {'B+'}
# Grades at C or better — the SPM credits (kepujian), request #30. SPM HAS NO C- (its grades are
# A+ A A- B+ B C+ C D E G), so "C or better" is exactly these seven; D, E, G and anything unknown
# do not count. The same set as `apps.courses.engine.CREDIT_GRADES` (drift-tested in
# `test_credit_floor.py`), kept here rather than imported so this module stays light at import.
CREDIT_GRADES = STRONG_GRADES | {'B', 'C+', 'C'}


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


def count_spm_credit_grades(grades):
    """Count grades at C or better — the TOTAL, A's and B's included, exactly as the B+ count
    includes the A's. Eight A's and no C's is eight credits, not zero (request #30)."""
    return _count(grades, CREDIT_GRADES)


@dataclass
class ShortlistResult:
    verdict: str    # 'shortlisted' or 'rejected'
    bucket: str     # 'A' (STR), 'B' (income test), or ''
    reason: str     # human-readable explanation
    category: str = ''  # rejection bucket when rejected: 'merit'|'need'|'ineligible' (engine); '' if shortlisted


def spm_merit(profile):
    """The UPU merit point (0-100) for an SPM profile — grades plus co-curriculum. None when
    there is nothing to score.

    ⚠ THIS DOES NOT REUSE `serializers_admin._application_merit_score`. Dated: the Sabah S2
    programme screens (2026-09-03) kept them apart because that function keyed on
    `held_qualification`, then marked "NOT A GATE, AND MUST NOT BECOME ONE", while this gate keyed
    on the declared exam. Since 2026-10-02 (TD-324, the owner's ruling) `_academic_ok` asks the
    SAME question — `results_held`, of which `held_qualification` is an alias — so the reason is no
    longer a different exam. What still differs is the SHAPE of the answer: that function (since S1,
    2026-10-25, a delegate of `exam_questions.merit_100`) returns the STPM overall CGPA converted to
    0-100 for an STPM holder (a ranking figure), this one only ever scores SPM
    grades and is reached only on `_academic_ok`'s SPM branch, where the PNGK is `min_stpm_pngk`'s
    business. Merging them is a refactor with its own characterisation, not a tidy-up.

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
    The one exception is `min_stpm_pngk` (D16c): blank is "SPM-only", tested below, not a pass.

    ⚠ NO REQUIREMENT SET AT ALL => PASSES. The academic test is then simply not part of this
    programme, which is a legitimate thing for a programme to be. It is NOT a silent hole: it
    takes an admin clearing every box on a screen that shows what is ticked.
    """
    # A cohort floor tests the results an applicant HOLDS, so this reads `results_held` — held on
    # the declaration by Now sprint 4, switched the same day on the owner's ruling (2026-10-02,
    # TD-324: 68 live agree, 1 Form Six explorer now tested on the SPM bar instead of 'STPM PNGK not
    # provided', 0 the other way). It runs at submit, and again only through
    # `rescore_pending_decisions` (the `rescore-pending` cron door or by hand), which re-scores every
    # 'submitted' application with decision_released_at NULL in ANY cohort and resets
    # decision_due_at so the release job emails the new verdict — 0 such applications and no
    # Scheduler job on that door (lead, 2026-10-02).
    exam = (results_held(profile) or 'spm') if profile else 'spm'

    # ⚠ OWNER RULING D16c (2026-10-27): A BLANK `min_stpm_pngk` MAKES THE INTAKE SPM-ONLY. It used
    # to mean "no STPM-level test, so pass"; an STPM / Matriculation / Asasi / Diploma holder on such
    # an intake now faces the intake's SPM GRADE bars, on their SPM grades (`spm_grades_for`:
    # `grades` over the STPM page's SPM block). NOT the merit bar (D3: SPM applicants only — their
    # co-curriculum and stream are written only by the SPM grades step, so a merit would be guessed
    # low). With a floor set, both branches below are unchanged.
    spm_only = (exam == 'stpm' or exam in THIRD_ROUTE) and cohort.min_stpm_pngk is None
    if spm_only:
        return _spm_bars(profile, cohort, spm_grades_for(profile), spm_held=False)

    if exam == 'stpm':
        floor = cohort.min_stpm_pngk
        p = getattr(profile, 'stpm_cgpa', None) if profile else None
        if p is None:
            return False, 'STPM PNGK not provided'
        if p >= floor:
            return True, ''
        return False, f'PNGK {p} below {floor}'

    if exam in THIRD_ROUTE:
        # STPM-equivalent (third results route S2a): the same `min_stpm_pngk` floor, on the OVERALL
        # CGPA (Matriculation / Asasi 0.9 x CGPA + 0.1 x koko/10 x 4; Diploma as is). The STPM
        # branch above is left byte-identical (it compares the stored figure raw). The reason
        # names the qualification, because a reviewer reads it: "Matriculation CGPA 2.70 below 2.90".
        floor = cohort.min_stpm_pngk
        label = QUALIFICATION_LABELS[exam]
        raw = getattr(profile, 'higher_cgpa', None)
        if raw is None:
            return False, f'{label} CGPA not provided'
        overall = third_route_overall(exam, raw, getattr(profile, 'higher_koko', None))
        if overall is None:
            if exam != 'diploma' and getattr(profile, 'higher_koko', None) is None:
                return False, f'{label} co-curriculum score not provided'
            return False, f'{label} CGPA not readable ({raw})'
        if overall >= floor:
            return True, ''
        return False, f'{label} CGPA {overall:.2f} below {floor:.2f}'

    return _spm_bars(profile, cohort, getattr(profile, 'grades', None) if profile else None)


def _spm_bars(profile, cohort, grades, spm_held=True):
    """The intake's SPM bars on `grades`. `spm_held=False` is D16c's door (an STPM-level holder on
    an SPM-only intake): the GRADE bars only — `min_merit_score` stays SPM-only (D3) — no SPM
    grades at all against a set grade bar is said plainly, and the reason names the door."""
    min_a, min_strong = cohort.min_spm_a_count, cohort.min_spm_bplus_count
    min_credit = cohort.min_spm_credit_count
    if not spm_held and not grades and any(b is not None for b in (min_a, min_strong, min_credit)):
        return False, 'SPM-only intake: SPM grades not provided'
    a = count_spm_a_grades(grades)
    strong = count_spm_strong_grades(grades)
    credits = count_spm_credit_grades(grades)
    min_merit = getattr(cohort, 'min_merit_score', None) if spm_held else None

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
    if min_credit is not None and credits < min_credit:
        # A TOTAL, stated as one: the owner sets it as "6 at C or better" and it is read that way.
        failures.append(f'{credits} at C or better (need {min_credit})')
    if min_merit is not None:
        m = spm_merit(profile)
        if m is None:
            failures.append(f'merit point not available (need {min_merit})')
        elif m < min_merit:
            failures.append(f'merit point {m} below {min_merit}')

    if not failures:
        return True, ''
    if not spm_held:
        return False, 'SPM-only intake: ' + '; '.join(failures)
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
    # Request #31: born in a state this intake accepts. The NRIC is the PROFILE's — the application
    # keeps no copy of its own — read live, like every other input here. No profile fails closed.
    ok, why = check_birth_state(getattr(profile, 'nric', '') if profile else '',
                                getattr(cohort, 'allowed_birth_states', None))
    if not ok:
        return ShortlistResult('rejected', '', why, 'ineligible')

    # D5 (owner, 2026-10-25): only a PUBLIC diploma counts — a private-college diploma is not
    # accepted by UA, so it does not qualify for this route at all. Out of scope, not a shortfall:
    # 'ineligible', whatever the CGPA and whether or not the intake sets a CGPA floor. Not stated
    # fails closed (the form always asks; only a hand-sent profile lacks it).
    if profile is not None and results_held(profile) == 'diploma' and not diploma_is_public(profile):
        stated = (getattr(profile, 'higher_institution_type', '') or '').strip().lower()
        if stated == 'private':
            why = ('Diploma from a private college: only diplomas from public institutions count '
                   'for this programme')
        else:
            why = ('Diploma institution not stated: only diplomas from public institutions count '
                   'for this programme')
        return ShortlistResult('rejected', '', why, 'ineligible')

    # 2. Academic floor → 'merit'
    ok, why = _academic_ok(profile, cohort)
    if not ok:
        return ShortlistResult('rejected', '', f'academic floor: {why}', 'merit')

    # 3. Income (STR fast-path, else per-capita) → 'need'
    ok, bucket, why = _income_ok(profile, cohort)
    if not ok:
        return ShortlistResult('rejected', '', f'income: {why}', 'need')

    return ShortlistResult('shortlisted', bucket, why)
