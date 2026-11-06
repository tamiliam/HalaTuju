"""The Academic fact of the verdict (``verdict_engine._verdict_academic``), the results slip's card.

⚠ WHY THIS IS A MODULE (request #62, 2026-11-06). ``verdict_engine.py`` is on the oversize ledger
(`code-standards.json`) with no room left, and request #62 has to add a check to this fact. The
function below was MOVED here verbatim, in its own commit, with no behaviour change;
``verdict_engine._verdict_academic`` stays as a seam so ``build_verdict`` and every reader of that
name keep working. The same reason ``verdict_ladder.py`` and ``verdict_income_salary.py`` exist.
"""
from __future__ import annotations

from .verdict_engine import _fact, _item, _latest_doc


def _verdict_academic(application, spm_only=False):
    """The slip must be the student's (name match), every subject on it must be entered
    (completeness), and the typed grades must match the slip (accuracy). All three clean →
    'verified'. Two independent readings: agreement verifies, a disagreement pinpoints the cell.
    Third route S3 / #388: `higher_results.academic_fact` picks the card; `spm_only` = the SPM card."""
    from .academic_engine import read_slip, _slip_name_status, _SUBJECT_BM
    from apps.courses.exam_questions import spm_slip_comparable
    from . import higher_results, wrong_slip
    if not spm_only:      # the higher card (S3), or the SPM card capped while they are owed (#388)
        return higher_results.academic_fact(application, lambda: _verdict_academic(application, True))
    evidence, unresolved = [], []
    slip = _latest_doc(application, 'results_slip')
    if slip is None:
        return _fact('academic', 'gap', evidence, [_item('results_slip_missing')])

    # Name — use the slip's OWN sv-authoritative status (the candidate-name logic the
    # student checklist uses), NOT the supporting-doc `vision_name_match` column. That
    # column is an unreliable full-text heuristic for a results slip: a perfectly-read
    # slip can carry 'not_found' there for some name spellings, and must never be mistaken
    # for "the slip could not be read" (it falsely flagged Sharvani's clean, fully-read slip).
    name_status = _slip_name_status(slip)
    if name_status == 'mismatch':
        # A RED Name chip (owner 2026-07-07 ladder: −1, stacking with subject/grade chips + the genuineness
        # step), not a hard gap; still an `application_completeness` blocker. Continue: other chips surface.
        unresolved.append(_item('results_slip_name_mismatch'))
    elif name_status == 'partial':      # one letter off, a likely misread (#56): amber, never red
        unresolved.append(_item('results_slip_name_near'))
    name_ok = name_status == 'match'
    if name_status == 'unreadable':
        unresolved.append(_item('results_slip_unreadable'))
    elif name_status == 'match':        # 'pending' → not yet decided; make no claim either way
        evidence.append(_item('results_slip_name_ok'))
    if kind := wrong_slip.higher_kind(slip):                   # S4 (#43): not an SPM slip at all
        return wrong_slip.academic_fact(slip, kind, evidence, unresolved)
    data = read_slip(slip)
    if not spm_slip_comparable(application.profile, _SUBJECT_BM):   # #62 review 2: nothing to compare,
        return _fact('academic', 'review', evidence, unresolved)    # so an unread slip holds nothing back
    if not data['names']:
        # The slip hasn't been field-extracted yet (legacy upload) — grades
        # unread, so honest under-claim: review until it's re-OCR'd.
        unresolved.append(_item('grades_unverified'))
        return _fact('academic', 'review', evidence, unresolved)

    from .academic_compare import spm_slip_compare
    cmp = spm_slip_compare(application.profile, data)
    if not cmp['compared']:   # owner 2026-11-06: a tertiary holder with no SPM prereq - nothing to compare
        return _fact('academic', 'review', evidence, unresolved)
    if cmp['missing']:
        unresolved.append(_item('academic_missing_subjects',
                                entered=cmp['slip_count'] - len(cmp['missing']),
                                total=cmp['slip_count'],
                                subjects=', '.join(cmp['missing'])))
    if cmp['extra']:      # request #62: typed but not on the slip — "please check", never a block
        unresolved.append(_item('academic_extra_subjects', subjects=', '.join(cmp['extra'])))
    for m in cmp['mismatched']:
        # band_confirmed (#71, owner 2026-07-08): the slip's letter AND Malay band agree, so a
        # ±-modifier difference is NOT an OCR blind spot — the read is double-confirmed and the
        # TYPED grade is what's wrong. Distinct copy says so plainly instead of "check by eye".
        code = 'academic_grade_band_mismatch' if m.get('band_confirmed') else 'academic_grade_mismatch'
        unresolved.append(_item(code, subject=m['subject'], typed=m['typed'], slip=m['slip']))
    # The slip's letter and band disagree for this subject — the grade read can't be
    # trusted, so surface it as "check by eye", NOT a confident mismatch.
    for u in cmp['uncertain']:
        unresolved.append(_item('academic_grade_uncertain',
                                subject=u['subject'], typed=u['typed'], slip=u['slip'], band=u['band']))

    if not cmp['have_grades']:
        # Names extracted (so completeness is real) but no grades yet — accuracy
        # still pending. Confirmed-complete is progress, but not 'verified'.
        unresolved.append(_item('grades_unverified'))
        return _fact('academic', 'review', evidence, unresolved)

    if name_ok and cmp['complete'] and cmp['accurate']:
        evidence.append(_item('grades_verified', count=cmp['checked_count']))   # tertiary: entered only
        return _fact('academic', 'verified', evidence, unresolved)
    return _fact('academic', 'review', evidence, unresolved)
