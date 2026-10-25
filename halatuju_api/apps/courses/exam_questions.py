"""The two questions `StudentProfile.exam_type` used to answer — one accessor each (TD-218).

`exam_type` moves on a card tap at "Choose Your Exam" and needs no results behind it. So it is a
true answer to ONE question — *which exam is this student heading for?* — and an unreliable answer
to the other — *which results do we hold?* A Form Six student who taps STPM to explore programmes
is declared STPM with nothing behind it while ten SPM grades sit on file.

Every reader of the stored field must say which of the two it means, by calling one of these:

* ``heading_for(profile)`` — the DECLARED exam, verbatim ('' when there is no profile or no value).
  It is a faithful read of the stored field and changes no answer; callers keep their own
  fallbacks, so swapping a raw read for this one is behaviour-identical by construction.
* ``results_held(profile)`` — the results we HOLD. The recorded completion
  (`results_exam_type`) wins; otherwise the declaration, corrected only where ABSENCE is
  conclusive (declared STPM, no STPM results at all, SPM grades on file -> 'spm').

⚠ ABSENCE IS CONCLUSIVE, PRESENCE PROVES NOTHING. This profile is shared with the course guide,
where anyone may type STPM grades to explore. Application #15 carries a 4.0 CGPA and five STPM
subjects and sat none of them (SPM 2025, now on matriculation; owner 2026-08-18). So
``results_held`` never PROMOTES a declared-SPM student on the strength of STPM data alone — only a
recorded completion can say 'stpm' for her, and even that is "a results form was completed", never
"the exam was sat".

⚠ MOVING A READER FROM ``heading_for`` TO ``results_held`` IS AN OUTCOME CHANGE, NOT A RENAME.
The switch moves both directions: the Form Six explorer AND a student who declared SPM and has a
recorded STPM completion. And ``results_held`` is a GATE: the shortlist gate, the sponsor band and
the slip-parser gate read it, so widening it moves who is shortlisted, what a sponsor reads and
which parser runs — characterise first (`apps/scholarship/tests/test_exam_questions.py`).

History, as a dated sequence: BrightPath #14 (2026-08-18) wrote the results-held rule as
`serializers_admin.held_qualification` for the admin label and the merit source, "not a gate";
the `results_exam_type` column (2026-09) let a recorded completion win; Now sprint 4 (2026-10-02)
moved the rule here unchanged, left `held_qualification` as an alias of ``results_held``, gave
the other readers named accessors and HELD the shortlist gate, the sponsor band and the slip
parser on ``heading_for`` pending a production count; the same day the owner ruled "switch all
three" (TD-324: 68 live agree, 1 Form Six explorer, 0 the other way) and they read
``results_held``. Which question each reader answers, and why, is in docs/decisions.md
(2026-10-02, TD-218 and TD-324). The owner has also said (2026-10-02) that "results held" means
the HIGHEST completed qualification; when Matric / Asasi / Poly join the results page this rule
is to be written as "highest" outright (TD-326).

Third results route S2a (2026-10-25, TD-326 / requests #37 #38 #43): it now is. Matriculation, Asasi
(Foundation) and Diploma join SPM and STPM. ``completed_qualifications`` (a list each results form
writes ON COMPLETION) is what "highest" ranks over - still never the presence of data (#15). Every
legacy row has it blank, and a blank list leaves the rule above exactly as it was (D1: the 27 legacy
rows recorded SPM with STPM data on file are NOT promoted here; see docs/decisions.md).
``is_tertiary`` is the one "STPM-equivalent" test, ``overall_cgpa`` the one CGPA, ``merit_100`` the
one merit.
"""
from rest_framework import serializers


def heading_for(profile):
    """The exam this student DECLARED — what they are heading for. The stored value, verbatim.

    Deliberately not normalised (no strip, no lower-casing): callers were written against the raw
    field and apply their own fallbacks ('spm' when blank, a `.lower()`, and so on). Keeping this a
    faithful read is what lets a reader move onto it without any answer changing."""
    if profile is None:
        return ''
    return getattr(profile, 'exam_type', '') or ''


def has_stpm_results(profile):
    """⚠ TRUSTWORTHY IN ONE DIRECTION ONLY — read the module docstring before using it elsewhere.

    FALSE is conclusive: with no STPM grades and no CGPA on file there is nothing to hold.
    TRUE is not: the course guide lets anyone type STPM grades to explore, so the data can
    describe a hypothetical rather than a result (application #15)."""
    return bool(profile.stpm_grades or {}) or profile.stpm_cgpa is not None


#: The third results route (owner, 2026-10-25): STPM-equivalent qualifications with a CGPA on a
#: 4.00 scale. Diploma means a PUBLIC diploma only (ruling D5) - see ``diploma_is_public``.
THIRD_ROUTE = ('matric', 'asasi', 'diploma')
#: Every qualification a results form can complete, lowest first.
QUALIFICATIONS = ('spm', 'stpm') + THIRD_ROUTE
#: "STPM-equivalent": the results that face `min_stpm_pngk` and rank on a CGPA.
TERTIARY = frozenset(('stpm',) + THIRD_ROUTE)
#: When two tertiary qualifications are both completed (rare) and the last form completed is not
#: one of them, this order breaks the tie. Deterministic; not a claim that one outranks another.
_TERTIARY_TIE_ORDER = ('stpm',) + THIRD_ROUTE
#: Plain names, for reasons and the sponsor line. English, like 'SPM' / 'STPM' there.
QUALIFICATION_LABELS = {
    'spm': 'SPM', 'stpm': 'STPM', 'matric': 'Matriculation', 'asasi': 'Asasi', 'diploma': 'Diploma',
}
#: The model choices for `exam_type` / `results_exam_type` (one list, so the two cannot drift).
EXAM_CHOICES = [('spm', 'SPM'), ('stpm', 'STPM'), ('matric', 'Matriculation'),
                ('asasi', 'Asasi (Foundation)'), ('diploma', 'Diploma')]
#: Where a Diploma is from (D5). Only 'public' counts; '' = not stated.
INSTITUTION_TYPE_CHOICES = [('public', 'Public institution'), ('private', 'Private college')]


def is_tertiary(held):
    """THE "STPM-equivalent" test: STPM, Matriculation, Asasi or Diploma results. Every reader that
    means "faces the CGPA floor / ranks on a CGPA" asks this, never ``== 'stpm'`` (S2a)."""
    return (held or '').strip().lower() in TERTIARY


def completed_qualifications(profile):
    """The qualifications a results form was COMPLETED for, normalised: known values only, lower
    case, first occurrence kept. [] for a legacy row (the column is blank on every row before S2a),
    a non-list, or no profile."""
    raw = getattr(profile, 'completed_qualifications', None) if profile else None
    if not isinstance(raw, list):
        return []
    out = []
    for q in raw:
        q = q.strip().lower() if isinstance(q, str) else ''
        if q in QUALIFICATIONS and q not in out:
            out.append(q)
    return out


def _has_higher_results(profile):
    """FALSE is conclusive (no third-route CGPA on file); TRUE proves only that a form was filled."""
    return getattr(profile, 'higher_cgpa', None) is not None


def results_held(profile):
    """Which qualification we hold RESULTS for — NOT which exam the student is heading for.

    'spm' / 'stpm', or '' when there is no profile and nothing declared. The rule (moved verbatim
    from `serializers_admin.held_qualification`, BrightPath #14):

    1. a RECORDED completion (`results_exam_type`) wins — it moves only when a results form is
       completed, so it answers this question directly instead of inferring it;
    2. otherwise the declaration, except declared 'stpm' with NO STPM results and SPM grades on
       file reads 'spm' — the Form Six student (#106), whom the declared value had ranked on an
       STPM CGPA that does not exist;
    3. otherwise the declaration, normalised.

    Self-correcting: the day her STPM results land, this returns 'stpm' again with nobody
    remembering to change anything.

    "HIGHEST COMPLETED" (third results route S2a, 2026-10-25) is step 0, before the three above:
    when ``completed_qualifications`` is NOT blank, the answer is the highest qualification in it
    (the recorded completion counts too - it is itself a completion). Any tertiary one beats SPM;
    between two tertiary ones the recorded completion wins, else ``_TERTIARY_TIE_ORDER``. Only a
    completed FORM puts a value in that list (the sync drops an entry with no results behind it),
    so presence of data still never promotes (#15). The list is BLANK on every legacy row, so
    steps 1-3 answer for them exactly as before (`test_exam_questions.TABLE`).

    The third route also gets step 2's correction, for the same reason: declared Matriculation /
    Asasi / Diploma (the third card tapped) with no third-route CGPA and SPM grades on file reads
    'spm'. Values: 'spm', 'stpm', 'matric', 'asasi', 'diploma', or ''."""
    if not profile:
        return ''
    recorded = (getattr(profile, 'results_exam_type', '') or '').strip().lower()
    completed = completed_qualifications(profile)
    if completed:
        done = set(completed) | ({recorded} if recorded in QUALIFICATIONS else set())
        tertiary = [q for q in _TERTIARY_TIE_ORDER if q in done]
        if tertiary:
            return recorded if recorded in tertiary else tertiary[0]
        return 'spm'
    if recorded:
        return recorded
    declared = (getattr(profile, 'exam_type', '') or '').strip().lower()
    if declared == 'stpm' and not has_stpm_results(profile) and (profile.grades or {}):
        return 'spm'
    if declared in THIRD_ROUTE and not _has_higher_results(profile) and (profile.grades or {}):
        return 'spm'
    return declared


def overall_from(academic_cgpa, koko):
    """THE overall-CGPA arithmetic: academic x 0.9 + co-curriculum (0-10, capped at 10) x 0.04,
    rounded to 2 decimals - i.e. 0.9 x CGPA + 0.1 x (koko / 10 x 4). The STPM calculator
    (`courses.views.CalculateCgpaView`) and the third route both call this; nothing else may
    restate it."""
    return round(academic_cgpa * 0.9 + min(koko, 10) * 0.04, 2)


def _as_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def third_route_overall(kind, cgpa, koko):
    """The overall CGPA for a third-route result, or None when it cannot be computed honestly.

    Diploma: the CGPA as is (no co-curriculum component). Matriculation / Asasi: ``overall_from``.
    A CGPA outside (0, 4] is not a CGPA (the guard `merit_100` applies to STPM since S1); a missing
    or negative co-curriculum score for Matriculation / Asasi gives None, never a made-up 0."""
    if kind not in THIRD_ROUTE:
        return None
    cgpa = _as_float(cgpa)
    if cgpa is None or not 0 < cgpa <= 4.0:
        return None
    if kind == 'diploma':
        return round(cgpa, 2)
    koko = _as_float(koko)
    if koko is None or koko < 0:
        return None
    return overall_from(cgpa, koko)


def overall_cgpa(profile):
    """THE overall CGPA of the tertiary results we hold - computed, never stored for the third
    route. STPM: the stored `stpm_cgpa` (already the overall figure). Third route:
    ``third_route_overall``. None for SPM, no profile, or nothing usable (a stored STPM value
    outside (0, 4] included - S1's guard)."""
    if not profile:
        return None
    held = results_held(profile)
    if held == 'stpm':
        cgpa = _as_float(getattr(profile, 'stpm_cgpa', None))
        if cgpa is None or not 0 < cgpa <= 4.0:
            return None
        return cgpa
    if held in THIRD_ROUTE:
        return third_route_overall(held, getattr(profile, 'higher_cgpa', None),
                                   getattr(profile, 'higher_koko', None))
    return None


def diploma_is_public(profile):
    """D5 (owner, 2026-10-25): only a diploma from a PUBLIC institution counts. True only when the
    student said so; 'private' and not-stated are both False (fail closed)."""
    kind = (getattr(profile, 'higher_institution_type', '') or '') if profile else ''
    return kind.strip().lower() == 'public'


def held_summary(profile):
    """The held results in a few words, for the AI sponsor-profile input (`profile_engine`).
    SPM / STPM keep the bare code they always had ('spm' / 'stpm'); a third-route holder is named,
    marked STPM-equivalent, with the overall CGPA — the prompt's `STPM PNGK:` slot reads
    `stpm_cgpa` and is 'n/a' for them. '' when nothing is held."""
    held = results_held(profile)
    if held not in THIRD_ROUTE:
        return held
    cgpa = overall_cgpa(profile)
    line = f'{QUALIFICATION_LABELS[held]} (STPM-equivalent)'
    return f'{line}, overall CGPA {cgpa:.2f}' if cgpa is not None else line


def third_route_payload(profile):
    """The profile payload's third-route keys (`courses.views.ProfileView.get`, S2a): the raw
    entries, what "highest" ranks over, and the overall CGPA from the ONE function — computed,
    never stored, so the web never restates the formula."""
    return {
        'higher_cgpa': profile.higher_cgpa,
        'higher_koko': profile.higher_koko,
        'higher_institution_type': profile.higher_institution_type,
        'completed_qualifications': profile.completed_qualifications,
        'overall_cgpa': overall_cgpa(profile),
    }


def third_route_calculation(data):
    """`CalculateCgpaView`'s answer for a third-route body ``{kind, higher_cgpa, koko_score}``:
    ``{cgpa, academic_cgpa, merit_percent}``, or None when the kind, the CGPA (0, 4] or a
    required co-curriculum score is missing or bad. Diploma = its CGPA as is."""
    kind = str(data.get('kind') or '').strip().lower()
    overall = third_route_overall(kind, data.get('higher_cgpa'), data.get('koko_score'))
    if overall is None:
        return None
    return {'cgpa': overall, 'academic_cgpa': round(float(data['higher_cgpa']), 2),
            'merit_percent': round(overall / 4.0 * 100, 2)}


def spm_grades_for(profile):
    """The student's SPM grades, from ONE reader. SPM holders: `grades`, unchanged. Tertiary
    holders: `grades` merged over `spm_prereq_grades` (the STPM page's SPM block writes the
    latter; live, 42 of 64 STPM holders have `grades`, 54 `spm_prereq_grades`), `grades` winning a
    clash because it is the full SPM record the comparison reads today.

    S2a provides this; it does NOT yet feed `academic_engine.compare_academics`, which still reads
    `profile.grades` - the SPM comparison input is unchanged until S3b moves it, characterised."""
    if not profile:
        return {}
    grades = getattr(profile, 'grades', None)
    grades = dict(grades) if isinstance(grades, dict) else {}
    if not is_tertiary(results_held(profile)):
        return grades
    prereq = getattr(profile, 'spm_prereq_grades', None)
    merged = dict(prereq) if isinstance(prereq, dict) else {}
    merged.update(grades)
    return merged


def merit_100(profile):
    """THE merit, on ONE 0-100 scale for every route (third results route S1, 2026-10-25).

    Keyed on ``results_held`` (the results we HOLD), never the declaration:

    * **STPM and the third route** (S2a) — ``overall_cgpa`` / 4 x 100, rounded to 2 decimals: the course side's own rule
      (`courses.views.CalculateCgpaView`: ``merit_percent = round(overall / 4.0 * 100, 2)``).
      `stpm_cgpa` already holds the OVERALL CGPA (academic x 0.9 + koko x 0.04): the STPM results
      page stores the calculator's ``cgpa`` (the overall figure), never ``academic_cgpa``, and it
      is the only writer. So 3.70 -> 92.5, 4.00 -> 100.0.
    * **SPM** — the course-guide merit from the stored grades / stream / co-curriculum, rounded to
      1 decimal. Byte-identical to the admin merit before S1 (`tests/test_merit_100.py`).

    ``None`` when there is nothing to score — ABSENT, never 0 (#106): a blank merit is not a low
    score. Derived live; there is no stored merit column.

    ⚠ NOT A GATE. `shortlisting.spm_merit` (the `min_merit_score` test) keys on the declared exam
    and stays SPM-only by the owner's ruling D3 (2026-10-25); it shares the engine arithmetic, not
    this function (lessons, Sabah S2a 2026-09-02)."""
    if not profile:
        return None
    if is_tertiary(results_held(profile)):
        # STPM and the third route (S2a): overall CGPA / 4 x 100. `overall_cgpa` carries S1's guard
        # - outside (0, 4] is not a CGPA (a 0 stored before the calculator answered, or a hand-sent
        # value): absent, never a made-up figure that would top or sink the sort (S1 review).
        cgpa = overall_cgpa(profile)
        if cgpa is None:
            return None
        return round(cgpa / 4.0 * 100, 2)
    grades = dict(getattr(profile, 'grades', None) or {})
    if not grades:
        return None
    # The engine's core uses 'history'; profiles store it as 'hist'. The eligibility flow
    # renames it before scoring, so mirror that — else History reads as a fail (G) and the
    # merit is understated.
    if 'hist' in grades:
        grades['history'] = grades.pop('hist')
    from apps.courses.engine import prepare_merit_inputs, calculate_merit_score
    s1, s2, s3 = prepare_merit_inputs(grades, getattr(profile, 'stream_subjects', None) or None)
    coq = profile.coq_score if getattr(profile, 'coq_score', None) is not None else 0
    result = calculate_merit_score(s1, s2, s3, coq)
    return round(result['final_merit'], 1)


class ResultsHeldField(serializers.Field):
    """A read-only field serving ``results_held(<object>.profile)`` under whatever name it is
    declared as — so a serializer can switch a wire field onto the accessor in ONE line and keep
    its public name (the student payload's `exam_type`, which the web app reads). An object with
    no profile OMITS the key, exactly as the old `source='profile.exam_type'` did (DRF skips a
    read-only field whose dotted source breaks on None)."""

    def __init__(self, **kwargs):
        kwargs.setdefault('source', 'profile')
        kwargs['read_only'] = True
        super().__init__(**kwargs)

    def get_attribute(self, instance):
        profile = super().get_attribute(instance)
        if profile is None:
            raise serializers.SkipField()
        return profile

    def to_representation(self, profile):
        return results_held(profile)
