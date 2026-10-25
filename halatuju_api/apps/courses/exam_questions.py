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
    remembering to change anything."""
    if not profile:
        return ''
    recorded = (getattr(profile, 'results_exam_type', '') or '').strip().lower()
    if recorded:
        return recorded
    declared = (getattr(profile, 'exam_type', '') or '').strip().lower()
    if declared == 'stpm' and not has_stpm_results(profile) and (profile.grades or {}):
        return 'spm'
    return declared


def merit_100(profile):
    """THE merit, on ONE 0-100 scale for every route (third results route S1, 2026-10-25).

    Keyed on ``results_held`` (the results we HOLD), never the declaration:

    * **STPM** — overall CGPA / 4 x 100, rounded to 2 decimals: the course side's own rule
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
    if results_held(profile) == 'stpm':
        cgpa = getattr(profile, 'stpm_cgpa', None)
        # Outside (0, 4] is not a CGPA: a 0 stored before the calculator answered, or a hand-sent
        # value. Absent, never a made-up figure that would top or sink the sort (S1 review).
        if cgpa is None or not 0 < float(cgpa) <= 4.0:
            return None
        return round(float(cgpa) / 4.0 * 100, 2)
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
