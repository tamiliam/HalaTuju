"""A HIGHER result in the SPM card — an STPM / Matriculation / Asasi / Diploma result uploaded as the
SPM results slip (third results route S4, 2026-10-27; org request #43, owner rulings D1 and D15).

Live (2026-10-27): 16 live documents in the `results_slip` slot are STPM results (#153's is an STPM
certificate) — and before S4 each was compared against the student's SPM grades, so the reviewer saw
"missing subjects" and grade mismatches the student never made, and an STPM "Lulus Penuh" read as an
SPM E (`academic_engine._BAND_TO_GRADE`).

WHAT THIS MODULE ANSWERS, read at READ TIME from what is already stored (free: no OCR, no model call,
never a re-read — `halatuju_never_reextract_locally`):

* ``higher_kind(doc)`` — the higher kind a `results_slip` document IS, or ''. Two witnesses:
    1. the routing detection of `results_kind.py` on the read's own ``exam`` title — but only on a
       document that read as a RESULT (subject rows or a CGPA), so a Matriculation OFFER letter in
       this slot (#77: "PROGRAM MATRIKULASI … SESI 2026/2027", no rows) stays the wrong document it
       is, under its own genuineness verdict;
    2. the corpus-gaps C3 score (`genuineness/stpm_doc.py`, MODEL_VERSION 1.9.0): an authenticity
       block whose best-fitting family is STPM (`doc_seen` 'stpm_slip' / 'stpm_certificate') and whose
       band is genuine or suspect. (A C3 `not_<type>` — the online checker page, ruling 1A — is not a
       result document and is NOT read as STPM results by this witness.)
* ``spm_genuineness_skipped(doc)`` — the SPM-family genuineness step is not applied to such a
  document UNLESS C3 already scored it. A model that knew STPM (1.9.0 and later) chose its family
  itself, so its verdict stands whatever it says (we never contradict C3); an older stored score was
  computed against the SPM lists alone, which is a measurement of the wrong thing — it is read as no
  signal ("not checked"), never as suspect.
* ``slip_check(doc, name)`` — the student's results-slip check for such a document: NO SPM
  comparison (no "missing subjects", no grade mismatch, never "change your grades"), the name still
  checked, and the D15 offer: "Move it to STPM results" — only where the applicant's Documents page
  shows the higher-results card (D12) and only before the Step-4 Submit.

The reverse move itself is `results_route.refile_to_higher`; the reviewer's line is the verdict
item ``results_slip_is_higher``.
"""
from __future__ import annotations

import re

from .genuineness.bands import canonical_status, stored_authenticity

#: The higher kinds, in the vocabulary of `exam_questions.QUALIFICATIONS`.
HIGHER_KINDS = ('stpm', 'matric', 'asasi', 'diploma')
#: The first `MODEL_VERSION` whose results scorer knew STPM (corpus-gaps C3).
_C3_FIRST = (1, 9)


def _parts(doc):
    vf = doc.vision_fields if isinstance(getattr(doc, 'vision_fields', None), dict) else {}
    f = vf.get('fields')
    return vf, (f if isinstance(f, dict) else {})


#: Titles that name something OTHER than a final result, whatever kind they mention: a trial
#: ("percubaan") examination, or an offer / registration letter (adversarial review, finding 3).
_NOT_A_RESULT = re.compile(r'\b(?:PERCUBAAN|TRIAL|TAWARAN|OFFER|PENDAFTARAN|REGISTRATION|LAPOR\s+DIRI)\b',
                           re.IGNORECASE)


def _reads_as_result(f) -> bool:
    """Did this read capture a RESULT — subject rows or a CGPA — under a title that is not a trial
    examination or an offer / registration letter? The same test for both cards' witnesses."""
    title = ' '.join(str(f.get(k) or '') for k in ('exam', 'qualification'))
    if _NOT_A_RESULT.search(title):
        return False
    return bool(f.get('results') or str(f.get('cgpa') or '').strip())


def _read(vf) -> bool:
    sv = vf.get('student_verdict')
    return bool(sv) and sv != 'review_manually'


def _version(raw) -> tuple:
    try:
        return tuple(int(p) for p in str(raw or '').split('.')[:2])
    except ValueError:
        return ()


def c3_scored(doc) -> bool:
    """Was this document's stored genuineness computed by a model that knew STPM (C3, 1.9.0+)?"""
    auth = stored_authenticity(getattr(doc, 'vision_fields', None))
    return bool(auth.get('status')) and _version(auth.get('model_version')) >= _C3_FIRST


def _c3_says_stpm(doc) -> bool:
    from .genuineness.stpm_doc import STPM_TYPES
    auth = stored_authenticity(getattr(doc, 'vision_fields', None))
    if (auth.get('doc_seen') or '') not in STPM_TYPES:
        return False
    return canonical_status(auth.get('status'), 'results_slip') in ('genuine', 'suspect')


def higher_kind(doc) -> str:
    """The higher kind of a READ `results_slip` document, or '' (an SPM slip, cannot tell, unread,
    or not a results slip at all)."""
    if doc is None or getattr(doc, 'doc_type', '') != 'results_slip':
        return ''
    vf, f = _parts(doc)
    if not _read(vf):
        return ''
    if not _reads_as_result(f):
        return ''
    from .results_kind import detect_from_fields
    seen = detect_from_fields(f)
    if seen in HIGHER_KINDS:
        return seen
    return 'stpm' if _c3_says_stpm(doc) else ''


def spm_genuineness_skipped(doc) -> bool:
    """A higher result in the SPM card whose stored score was NOT computed by C3 — its SPM-family
    genuineness is no signal (the reviewer is told what the document is instead)."""
    return bool(higher_kind(doc)) and not c3_scored(doc)


def move_offered(application) -> bool:
    """D15 + D12: is the "Move it to … results" action on offer for this applicant? Only where the
    Documents page shows the higher-results card (a degree, or no course chosen while holding higher
    results), and only before the Step-4 Submit (the S3 actions' rule: 409 after it)."""
    from . import requirements, results_route
    if application is None or getattr(application, 'profile_completed_at', None) is not None:
        return False
    if not results_route.gift_asks_higher(application):     # D16: an SPM-only gift has no card
        return False
    return requirements.resolve(application, 'document').get('higher_results') in ('required', 'optional')


def slip_check(doc, name) -> dict | None:
    """`academic_engine.student_slip_check` for a higher result in the SPM card, or None for any
    other document (the SPM checks then run as before). Subjects / results read 'not_spm' — not a
    match, not a mismatch, not pending — so no reader compares, coaches or holds on them."""
    kind = higher_kind(doc)
    if not kind:
        return None
    _vf, f = _parts(doc)
    app = getattr(doc, 'application', None)
    offered = move_offered(app)
    return {
        'name': name, 'subjects': 'not_spm', 'results': 'not_spm',
        'candidate_name': f.get('candidate_name') or '', 'exam': (f.get('exam') or '').strip(),
        'exam_year': '', 'exam_year_status': '', 'was_skewed': False,
        'missing': [], 'mismatched': [], 'uncertain': [], 'slip_count': 0,
        'higher_kind': kind, 'move_offered': offered,
        'actions_open': getattr(app, 'profile_completed_at', None) is None,
    }


def academic_fact(slip, kind, evidence, unresolved):
    """The SPM card's Academic fact when its document is a higher result: the reviewer is told what
    it is, and nothing is compared. 'review' (Probable at best): the SPM slip is not on file.

    Review finding 2: for an applicant the SPM slip is REQUIRED of who holds no tertiary results,
    the higher result does not fill that slot — `results_slip_missing` stays (so its system ticket is
    never closed by it). A tertiary holder is never asked for SPM by the system (D9)."""
    from apps.courses.exam_questions import QUALIFICATION_LABELS, is_tertiary, results_held
    from . import requirements
    from .verdict_engine import _fact, _item
    unresolved.append(_item('results_slip_is_higher', kind=QUALIFICATION_LABELS.get(kind, kind)))
    app = getattr(slip, 'application', None)
    if (app is not None and requirements.resolve(app, 'document').get('results_slip') == 'required'
            and not is_tertiary(results_held(getattr(app, 'profile', None)))):
        unresolved.append(_item('results_slip_missing'))
    return _fact('academic', 'review', evidence, unresolved)


def fills_spm_slot(doc) -> bool:
    """Review finding 2: may this document count as a USABLE SPM slip — for promotion (it must never
    push a real SPM slip into history) and for closing a results-slip item? Not when it is a higher
    result. Any other document type → True (unchanged)."""
    return not higher_kind(doc)


def stpm_results_on_file(profile) -> bool:
    """D1 (owner 2026-10-25, (b)): a LIVE document of this student's that is recognised as STPM
    results — `higher_kind` in the SPM card, or a higher-results upload read (or filed) as STPM.
    The witness `exam_questions.results_held` asks before promoting a legacy SPM row that has STPM
    data on file. One query, only for that rare row; memoised on the profile instance."""
    pk = getattr(profile, 'pk', None)
    if pk is None:
        return False
    memo = getattr(profile, '_d1_stpm_doc', None)
    if memo is not None:
        return memo
    from .models import ApplicantDocument
    docs = ApplicantDocument.objects.filter(
        application__profile_id=pk, superseded_at__isnull=True,
        doc_type__in=('results_slip', 'higher_results')).select_related('application')
    found = False
    for doc in docs:
        if doc.doc_type == 'results_slip':
            found = higher_kind(doc) == 'stpm'
        else:
            # Read: the detection decides, on a document that read as a RESULT (review finding 3).
            # Not read yet (or our outage): only a document MOVED out of the SPM card — its earlier
            # read already recognised STPM — counts, by the kind it was filed as, so the student does
            # not fall back to SPM while the live sweep re-reads it (review finding 1). A fresh or
            # request-keyed upload never promotes until it has actually been read as STPM.
            vf, f = _parts(doc)
            if _read(vf):
                found = f.get('results_kind_detected') == 'stpm' and _reads_as_result(f)
            else:
                found = getattr(doc, 'results_kind', '') == 'stpm' and _moved_here(doc)
        if found:
            break
    try:
        profile._d1_stpm_doc = found
    except AttributeError:
        pass
    return found


def _moved_here(doc) -> bool:
    """Was this higher-results upload MOVED out of the SPM card (`refile_to_higher`, or the team's
    move once its note is written)? Read off the application's own `refiled_higher` notes."""
    notes = getattr(getattr(doc, 'application', None), 'results_change_notes', None)
    return any(isinstance(n, dict) and n.get('kind') == 'refiled_higher'
               and n.get('document_id') == doc.id for n in (notes if isinstance(notes, list) else []))
