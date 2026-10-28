"""THE STPM CGPA (PNGK), worked out from the grades — STPM CGPA sprint C2 (2026-10-28).

Owner ruling (2026-10-28, `docs/plans/2026-10-28-stpm-cgpa-from-grades-roadmap.md`): an STPM
student's CGPA is worked out from the subjects and grades they entered, never typed. The rule is
the certificate's own — every certificate read Exact agrees with it:

    PNGK = (Pengajian Am + the best three other subjects) / 4, to 2 decimals

on the fixed MQA scale `stpm_engine.STPM_CGPA_POINTS` (A 4.00, A- 3.67 … D 1.00, F 0.00).

Fewer than Pengajian Am + three graded subjects: there is no PNGK to work out, so
`pngk_from_grades` answers None and `stpm_cgpa_of` falls back to the figure already stored on the
profile ("not calculated" — the student is asked to complete their grades).

⚠ This is NOT `stpm_engine.calculate_stpm_cgpa`. That one is the course guide's calculator (a plain
average of every grade entered), sits in a golden-master file and is left exactly as it is.

CGPA AND MERIT ARE DIFFERENT (owner ruling 2026-10-28). The CGPA is the PNGK above — display, the
`min_stpm_pngk` gate, the document comparison. The MERIT keeps co-curriculum, as it always did:
`stpm_merit_overall` = `exam_questions.overall_from(PNGK, stpm_koko)`, then / 4 x 100 in
`exam_questions.merit_100`.

Every reader of an STPM student's CGPA asks `stpm_cgpa_of` (or the model's `stpm_pngk`, which
calls it) — never `profile.stpm_cgpa` directly. The door list is in the sprint's pull request and
pinned by `tests/test_stpm_pngk_doors.py`.
"""
from decimal import ROUND_HALF_UP, Decimal

from .stpm_engine import STPM_CGPA_POINTS
from .stpm_subjects import PENGAJIAN_AM

#: How many subjects besides Pengajian Am count towards the PNGK.
BEST_OTHERS = 3


def _points(grade):
    """The grade's points as a Decimal, or None for a blank or unknown grade (the legacy `E` / `G`
    aliases included — they are not on the scale, so they never count)."""
    if not isinstance(grade, str):
        return None
    pts = STPM_CGPA_POINTS.get(grade.strip().upper())
    return None if pts is None else Decimal(str(pts))


def _best(grades):
    """(Pengajian Am's points, [(key, points)] of the best three others), or None when there is no
    PNGK to work out. Ties keep the order the grades were entered in (`sorted` is stable), so the
    subjects shown as counting never jump about; the sum is the same either way."""
    if not isinstance(grades, dict):
        return None
    pa = _points(grades.get(PENGAJIAN_AM))
    if pa is None:
        return None
    others = sorted(((k, p) for k, g in grades.items() if k != PENGAJIAN_AM
                     for p in [_points(g)] if p is not None), key=lambda kp: kp[1], reverse=True)
    if len(others) < BEST_OTHERS:
        return None
    return pa, others[:BEST_OTHERS]


def pngk_from_grades(grades):
    """THE PNGK from `{subject key: grade}`, or None when it cannot be worked out.

    None unless Pengajian Am has a grade on the scale AND at least three other subjects do. Of the
    others, the best three count. Rounded half-up to 2 decimals (the points are exact two-place
    figures, so the sum is exact and the rounding is the only step)."""
    best = _best(grades)
    if best is None:
        return None
    pa, others = best
    total = pa + sum(p for _, p in others)
    return float((total / (BEST_OTHERS + 1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


def counted_subjects(grades):
    """The subject keys the PNGK counts — Pengajian Am first, then the best three — or [] when
    there is no PNGK. The onboarding step marks these "counts" and the rest "not counted"."""
    best = _best(grades)
    return [] if best is None else [PENGAJIAN_AM] + [k for k, _ in best[1]]


def _koko(value):
    """A stored or sent co-curriculum score (0-10) as a float, or None when absent or not a score."""
    try:
        koko = None if value is None or value == '' else float(value)
    except (TypeError, ValueError):
        return None
    return koko if koko is not None and 0 <= koko <= 10 else None


def stpm_cgpa_is_calculated(profile):
    """True when this profile's STPM CGPA comes from its grades (PA + three graded subjects)."""
    return pngk_from_grades(getattr(profile, 'stpm_grades', None)) is not None


def stpm_cgpa_of(profile):
    """THE STPM CGPA every reader uses: the PNGK worked out from `stpm_grades`; when the grades are
    not complete enough for one, the figure stored in `stpm_cgpa` as it is ("not calculated"); None
    when there is neither (or no profile). Callers keep their own range guards — this returns a
    stored figure unchanged, as the readers saw it before."""
    if profile is None:
        return None
    pngk = pngk_from_grades(getattr(profile, 'stpm_grades', None))
    if pngk is not None:
        return pngk
    stored = getattr(profile, 'stpm_cgpa', None)
    try:
        return None if stored is None else float(stored)
    except (TypeError, ValueError):
        return None


def stpm_merit_overall(profile):
    """THE figure an STPM holder's MERIT is made from — never their CGPA (owner ruling 2026-10-28:
    "CGPA and merit are different; co-curriculum stays in merit"). It is the onboarding
    calculator's rule, unchanged: `exam_questions.overall_from(PNGK, koko)` = 0.9 x the PNGK +
    0.04 x the stored co-curriculum score (`stpm_koko`); `merit_100` turns it into / 4 x 100.

    * Not calculated (fewer than PA + three graded): the stored `stpm_cgpa` as it is — that figure
      IS the old calculator's overall, co-curriculum already inside (owner: the not-calculated
      rows keep the stored figure). Outside (0, 4] it is not a figure (S1's guard): None.
    * A PNGK with no co-curriculum score beside it: None — absent, never a made-up 0 (the third
      route's rule, `third_route_overall`). The backfill derives the score for existing students.
    * No profile: None."""
    if profile is None:
        return None
    pngk = pngk_from_grades(getattr(profile, 'stpm_grades', None))
    if pngk is None:
        stored = stpm_cgpa_of(profile)
        return stored if stored is not None and 0 < stored <= 4.0 else None
    koko = _koko(getattr(profile, 'stpm_koko', None))
    if koko is None:
        return None
    from .exam_questions import overall_from
    return overall_from(pngk, koko)


def stpm_calculation(grades, koko_score):
    """`CalculateCgpaView`'s STPM answer — the onboarding step reads it live and shows the CGPA and
    the merit SEPARATELY (owner, 2026-10-28):

        {cgpa: PNGK | None, counted: [keys], overall: 0.9 x PNGK + 0.04 x koko | None,
         merit_percent: overall / 4 x 100 | None}

    `cgpa` is None ("not calculated yet") below PA + three; `overall` / `merit_percent` are None
    until there is a PNGK AND a co-curriculum score in 0-10. The same arithmetic as the stored
    profile's merit (`stpm_merit_overall` -> `merit_100`), so the step and the console agree."""
    pngk = pngk_from_grades(grades)
    koko = _koko(koko_score)
    overall = None
    if pngk is not None and koko is not None:
        from .exam_questions import overall_from
        overall = overall_from(pngk, koko)
    return {'cgpa': pngk, 'counted': counted_subjects(grades), 'overall': overall,
            'merit_percent': None if overall is None else round(overall / 4.0 * 100, 2)}


def stpm_cgpa_payload(profile):
    """The student profile payload's STPM keys (`courses.views.ProfileView.get`): the CGPA every
    reader uses, whether it was worked out from the grades — False means "not calculated", the
    stored figure shown until the student completes their grades — and the stored co-curriculum
    score, so the onboarding step rebuilds on another device."""
    return {'stpm_cgpa': stpm_cgpa_of(profile), 'stpm_cgpa_calculated': stpm_cgpa_is_calculated(profile),
            'stpm_koko': getattr(profile, 'stpm_koko', None)}
