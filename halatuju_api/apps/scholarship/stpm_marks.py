"""The cockpit's STPM check marks — STPM CGPA sprint C3 (2026-10-28).

Owner ruling (2026-10-28): an STPM student's subjects, grades and CGPA come from onboarding (the
CGPA is the PNGK worked out from the grades, `courses.stpm_pngk`), and are COUNTER-CHECKED against
the uploaded STPM results (`higher_results`, read Exact or by AI). A match gets a check mark, as the
SPM grades already do.

This module only PROJECTS for display what `higher_results` already reads. It owns no matcher: the
rows come from `higher_results.stpm_rows` (the walk `_compare_stpm` uses), the read state and the
document kind from `student_higher_check`. Nothing here feeds a verdict band or a red chip.

``stpm_marks`` on the officer's detail payload (None for anyone but an STPM-results student)::

    {'grades': {KEY: {'status': 'match' | 'differ', 'doc': 'B+'}},   # only subjects on the document
     'cgpa': 'match' | 'differ' | 'not_calculated' | None,
     'cgpa_doc': 3.67 | None}

* A grade: 'match' when the document shows the same grade for that subject, 'differ' (with the
  document's grade) when not; absent when there is no read document or the subject is not on it.
* The CGPA: 'not_calculated' when the grades hold fewer than Pengajian Am + three (the shown value
  is then the typed figure, so there is nothing of ours to check); else 'match' when the document's
  PNGK is within 0.01 of the calculated one; 'differ' only when the document's figure is labelled
  cumulative (a bare GPA may be one semester's — `higher_results` review fix 7); else None.
"""
from __future__ import annotations

from apps.courses.exam_questions import results_held

#: The calculated PNGK and the printed one are both two-place figures, so they agree exactly; the
#: 0.01 (plus float slack) only absorbs a print that rounds the last place the other way.
CGPA_MATCH_TOLERANCE = 0.01 + 1e-9


def _cgpa_mark(chk, calculated, fields):
    from .higher_results import _CUMULATIVE_LABEL
    if calculated is None:
        return 'not_calculated'
    slip = chk['cgpa_slip'] if chk else None
    if slip is None:
        return None
    if abs(slip - calculated) <= CGPA_MATCH_TOLERANCE:
        return 'match'
    return 'differ' if _CUMULATIVE_LABEL.search(str(fields.get('cgpa_label') or '')) else None


def stpm_marks(application):
    """The marks above for one application, or None when it does not hold STPM results."""
    profile = getattr(application, 'profile', None)
    if profile is None or results_held(profile) != 'stpm':
        return None
    from apps.courses.stpm_pngk import pngk_from_grades
    from .document_snapshot import latest_doc
    from .higher_results import _fields, entered_stpm, stpm_rows, student_higher_check
    calculated = pngk_from_grades(getattr(profile, 'stpm_grades', None))
    doc = latest_doc(application, 'higher_results')
    chk = student_higher_check(doc) if doc is not None else None
    # The same door `student_higher_check` opens for its own grade comparison: a read STPM page,
    # not an SPM slip filed in this card. Anything else shows no marks at all (never a wrong one).
    usable = bool(chk) and chk['grades_status'] != ''
    fields = _fields(doc)[1] if usable else {}
    grades = {}
    if usable:
        entered = entered_stpm(profile)
        for _name, key, slip in stpm_rows(fields):
            if key in entered and entered[key] and slip and key not in grades:
                grades[key] = {'status': 'match' if slip == entered[key] else 'differ', 'doc': slip}
    return {'grades': grades, 'cgpa': _cgpa_mark(chk if usable else None, calculated, fields),
            'cgpa_doc': chk['cgpa_slip'] if usable else None}


class ServesTheStpmMarks:
    """Adds ``stpm_marks`` to the officer's detail payload (before the family keys and the gift's
    ``programme``, which stays last)."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['stpm_marks'] = stpm_marks(instance)
        return data
