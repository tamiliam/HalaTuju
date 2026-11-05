"""The results-slip details the student's document coach names (``DocumentHelpView``).

The coach's verdict code says WHAT is wrong; these say WHICH subject, so the student is not left
hunting: the grades that differ (owner 2026-07-08) and, since request #62 (2026-11-06), the typed
subjects we could not find on the slip. Both come off ``student_slip_check`` — the same read the
checklist shows — so the coach and the checklist can never disagree. A module of its own because
``views.py`` is on the oversize ledger with no room.
"""
from __future__ import annotations

_SUBJECT_VERDICTS = ('slip_subjects_missing', 'slip_subjects_extra')


def coach_detail(doc, verdict: str) -> dict:
    """``{grade_diffs: [...], extra_subjects: [...]}`` for the help response; both empty for any
    verdict that names no subject (and no slip read is made for them)."""
    grade_diffs, extra = [], []
    if verdict == 'slip_grade_mismatch' or verdict in _SUBJECT_VERDICTS:
        from .academic_engine import student_slip_check
        chk = student_slip_check(doc)
        if verdict == 'slip_grade_mismatch':
            grade_diffs = chk.get('mismatched') or []
        else:      # missing AND extra can both be true (a subject typed under the wrong name)
            extra = chk.get('extra') or []
    return {'grade_diffs': grade_diffs, 'extra_subjects': extra}
