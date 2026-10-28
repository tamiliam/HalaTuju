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


def pngk_from_grades(grades):
    """THE PNGK from `{subject key: grade}`, or None when it cannot be worked out.

    None unless Pengajian Am has a grade on the scale AND at least three other subjects do. Of the
    others, the best three count. Rounded half-up to 2 decimals (the points are exact two-place
    figures, so the sum is exact and the rounding is the only step)."""
    if not isinstance(grades, dict):
        return None
    pa = _points(grades.get(PENGAJIAN_AM))
    if pa is None:
        return None
    others = sorted((p for k, g in grades.items() if k != PENGAJIAN_AM
                     for p in [_points(g)] if p is not None), reverse=True)
    if len(others) < BEST_OTHERS:
        return None
    total = pa + sum(others[:BEST_OTHERS])
    return float((total / (BEST_OTHERS + 1)).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP))


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


def stpm_cgpa_payload(profile):
    """The student profile payload's STPM CGPA keys (`courses.views.ProfileView.get`): the CGPA
    every reader uses, and whether it was worked out from the grades — False means "not
    calculated", the stored figure shown until the student completes their grades."""
    return {'stpm_cgpa': stpm_cgpa_of(profile), 'stpm_cgpa_calculated': stpm_cgpa_is_calculated(profile)}
