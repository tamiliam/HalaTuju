"""WHICH results upload an application must carry, and the two student actions that change it.
Third results route S3a + S3b (2026-10-26; roadmap §5 S3, owner rulings D6 D9 D12 D13).

⚠ THE REQUIRED UPLOAD FOLLOWS THE CHOSEN COURSE (D12), not the results held alone:

    a university DEGREE chosen      → `higher_results` required, `results_slip` (SPM) optional
                                      (an SPM-only holder bound for a degree: BOTH required —
                                      owner ruling 2026-10-26, see `higher_need`)
    a post-SPM pathway chosen       → `results_slip` required, no `higher_results` card — even if
      (Matriculation, Form Six,       higher results were entered (the course needs SPM entry)
       Asasi, Polytechnic, Kolej
       Komuniti, PISMP, ILJTM, ILKBS)
    no course chosen ("not sure")   → by the results held: tertiary → as a degree; SPM → SPM slip

The answer is applied ON TOP of the catalogue by `requirements.resolve` for an application that has
NOT been submitted; `requirements.freeze` then stores it in `requirements_snapshot` at the Step-4
Submit, so a submitted application keeps the requirement it was gated on (a pre-S3a snapshot has no
`higher_results` key and keeps "SPM slip required" for ever). The SPM slip is a CORE catalogue item,
so the mapping only ever relabels it; it never invents a requirement for a programme that asks for
no results (state 'off' → untouched).

The two actions (D13, after the detection notes in `higher_results.py`) are open ONLY BEFORE the
Step-4 Submit (adversarial review, fixes 1+2): after it the frozen requirement, the reviewed slip
and any award stand, and the reviewer's own request route is the way. Each leaves a note the
reviewer sees (`results_change_notes`, fix 3) — a student shortlisted on a CGPA must never arrive
silently as SPM.
  * ``refile_to_spm`` — "Move it to SPM results slip": an SPM slip uploaded into the higher-results
    card is re-filed into the SPM slot (the file kept, read again as an SPM slip).
  * ``clear_to_spm`` — "Continue with SPM results only": the higher results ENTERED are removed,
    explicitly — the one door that may move a profile down from tertiary results it still holds
    (the sync's `_never_demote_held_results` guards every other door).
"""
from __future__ import annotations

import logging

from django.utils import timezone

logger = logging.getLogger('apps.scholarship.results_route')

DEGREE, POST_SPM, UNDECIDED = 'degree', 'post_spm', ''

#: The apply form's post-SPM pathway codes (`PATHWAY_ORDER` less 'university'), plus the offer
#: autofill's 'diploma'. PISMP is a degree by name but SPM-entry, so post-SPM (D13).
POST_SPM_CODES = frozenset({'matric', 'stpm', 'asasi', 'poly', 'kkom', 'pismp', 'iljtm', 'ilkbs',
                            'diploma'})
#: `offer_pathway.detect_pathway_type` answers that name a post-SPM programme.
_POST_SPM_TYPES = frozenset({'stpm', 'matric', 'asasi', 'pismp', 'diploma'})
#: Lead's ruling (review fix 4): pre-university pathways a TERTIARY holder has already completed or
#: passed. Stored as her pathway with no course, it is a stale autofill (her own Form Six / college
#: letter), not where she is going → undecided, so the results held decide (live #196, #147).
_PASSED_PRE_U = frozenset({'stpm', 'matric', 'asasi'})


def destination(application) -> str:
    """Where the student is going: DEGREE, POST_SPM or UNDECIDED ('').

    The chosen PROGRAMME decides first, because it is the most specific thing on file and the
    stored pathway code can lag it (live: an STPM holder with `chosen_pathway='stpm'` — the Form Six
    letter's autofill — and a degree picked from the STPM list). A `course_id` in the post-STPM
    degree catalogue (`stpm_courses`) is a degree; any other `course_id` comes from the SPM
    catalogue, which holds only SPM-entry courses (UA diplomas, Asasi, PISMP, polytechnic …).
    Then the pathway code; then the programme's NAME (an offer read with no catalogue id).
    'university' with nothing else is ambiguous (the SPM form's UA courses are diplomas) → ''."""
    memo = getattr(application, '_results_destination', None)
    if memo is not None:
        return memo
    prog = getattr(application, 'chosen_programme', None)
    prog = prog if isinstance(prog, dict) else {}
    code = (getattr(application, 'chosen_pathway', '') or '').strip().lower()
    course_id = str(prog.get('course_id') or '').strip()
    if course_id:
        from apps.courses.models import StpmCourse
        out = DEGREE if StpmCourse.objects.filter(course_id=course_id).exists() else POST_SPM
    elif code == 'degree':
        out = DEGREE
    elif code in POST_SPM_CODES and _already_passed(application, code):
        out = UNDECIDED
    elif code in POST_SPM_CODES:
        out = POST_SPM
    elif (prog.get('course_name') or '').strip():
        from .offer_pathway import detect_pathway_type
        kind = detect_pathway_type(prog.get('course_name') or '', prog.get('institution') or '')
        out = DEGREE if kind == 'degree' else POST_SPM if kind in _POST_SPM_TYPES else UNDECIDED
    else:
        out = UNDECIDED
    try:
        application._results_destination = out
    except AttributeError:
        pass
    return out


def _already_passed(application, code) -> bool:
    """A pre-U code (or her own held kind) recorded as the pathway of a TERTIARY holder."""
    from apps.courses.exam_questions import is_tertiary
    kind = held(application)
    return is_tertiary(kind) and (code in _PASSED_PRE_U or code == kind)


def held(application) -> str:
    """The results held (`exam_questions.results_held`) for this application's student."""
    from apps.courses.exam_questions import results_held
    return results_held(getattr(application, 'profile', None))


def higher_need(application) -> str:
    """How this application treats the higher-results upload: 'required' (and the SPM slip
    becomes optional, D9), 'required_with_slip' (both required) or '' (not shown).

    Owner ruling (2026-10-26, overriding the builder's interim "offer it"): a university DEGREE
    needs post-SPM results, so a degree-bound student holding ONLY SPM is REQUIRED to upload them
    too — before submit; a submitted application keeps its frozen requirement. Her SPM slip stays
    REQUIRED as well, so she always has academic evidence on file, and the card tells her plainly
    to enter her higher results or choose a post-SPM pathway."""
    from apps.courses.exam_questions import is_tertiary
    dest = destination(application)
    if dest == POST_SPM:
        return ''
    tertiary = is_tertiary(held(application))
    if dest == DEGREE:
        return 'required' if tertiary else 'required_with_slip'
    return 'required' if tertiary else ''


def map_documents(application, resolved: dict) -> dict:
    """`resolved` (the catalogue's document states) with the per-applicant results rule applied.
    Called by `requirements.resolve` on the LIVE path of an application not yet submitted only."""
    state = resolved.get('results_slip')
    if state not in ('required', 'optional'):
        return resolved                    # off, or anything unknown: the programme asks for no results
    need = higher_need(application)
    if not need:
        return resolved
    # Never escalate beyond what the programme set (review fix 5): a programme that made the
    # results OPTIONAL makes the higher results optional too.
    higher = 'required' if state == 'required' else 'optional'
    out = {**resolved, 'higher_results': higher}
    if higher == 'required' and need == 'required':
        out['results_slip'] = 'optional'          # D9: optional only for a tertiary holder
    return out


def upload_kind(application) -> str:
    """The `results_kind` a new higher-results upload carries: the results held, when tertiary
    (D13 — the card shows it read-only and "Change" opens the results page). '' otherwise."""
    from apps.courses.exam_questions import is_tertiary
    kind = held(application)
    return kind if is_tertiary(kind) else ''


# ── The two student actions (D13) ──────────────────────────────────────────────────────────────


def submitted(application) -> bool:
    """Past the Step-4 Submit — both actions are closed (fixes 1+2)."""
    return getattr(application, 'profile_completed_at', None) is not None


def _note(application, kind, **fields):
    """Append a reviewer-visible note (`results_change_notes`, fix 3) — ALWAYS, before submit too."""
    note = {'at': timezone.now().isoformat(), 'kind': kind, 'submitted': submitted(application),
            **fields}
    application.results_change_notes = list(application.results_change_notes or []) + [note]
    application.save(update_fields=['results_change_notes'])
    return note


def refile_to_spm(application, doc) -> 'object':
    """Move a higher-results upload that reads as an SPM slip into the SPM slot, BEFORE submit only
    (the caller refuses otherwise). The FILE is kept; its higher-results READ is cleared (fix 6) so
    the live service reads it again as an SPM slip — the self-heal sweep picks up a document whose
    run stamps are NULL and whose `vision_fields` is empty (`services.blockers`); it is never
    re-read from a local checkout. One live slip per slot: the moved slip and any live SPM slip are
    compared by `promotion.should_promote` and the weaker becomes history (Old / Replaced). The
    higher-results card then asks again. A reviewer note records the move. Returns the document."""
    from . import promotion
    from .document_snapshot import live_docs
    from .models import ApplicantDocument
    existing = live_docs(application, 'results_slip').exclude(id=doc.id).first()
    doc.doc_type, doc.results_kind, doc.request_code = 'results_slip', '', ''
    doc.vision_fields, doc.vision_fields_run_at, doc.vision_run_at = {}, None, None
    doc.vision_name_match, doc.vision_address_match, doc.vision_error = '', '', ''
    doc.save(update_fields=['doc_type', 'results_kind', 'request_code', 'vision_fields',
                            'vision_fields_run_at', 'vision_run_at', 'vision_name_match',
                            'vision_address_match', 'vision_error'])
    now = timezone.now()
    if existing is None or promotion.should_promote(doc, existing, usable=True):
        ApplicantDocument.objects.filter(
            application=application, doc_type='results_slip', superseded_at__isnull=True,
        ).exclude(id=doc.id).update(superseded_at=now, superseded_by=doc)
    else:
        ApplicantDocument.objects.filter(id=doc.id).update(superseded_at=now, superseded_by=existing)
    doc.refresh_from_db()
    _note(application, 'refiled_spm', document_id=doc.id)
    logger.info('AUDIT results_refiled_to_spm app=%s doc=%s kept_existing=%s', application.id,
                doc.id, bool(doc.superseded_at))
    from .resolution import sync_resolution_items
    sync_resolution_items(application)
    return doc


def clear_to_spm(application, *, by: str = 'student') -> dict:
    """"Continue with SPM results only" (D13): remove the higher results ENTERED — STPM grades and
    CGPA, the third route's CGPA, co-curriculum and institution — and leave every SPM grade as it
    is. The student is then assessed on SPM: the recorded completion becomes 'spm' and, when her
    SPM grades sit only in the STPM page's SPM block (`spm_prereq_grades`), they are copied into
    `grades` (the field every SPM reader reads) — copied, never altered.

    BEFORE submit only (the caller refuses otherwise, fixes 1+2) and NOT a gate run: the gate ran
    at the first submit on the results she had then. A note is ALWAYS recorded for the reviewer
    (`results_change_notes`, shown on the cockpit's Academic card, fix 3) — she may have been
    shortlisted on the CGPA she now removes. Audited. Returns the note."""
    from apps.courses.exam_questions import overall_cgpa, results_held
    profile = application.profile
    before = results_held(profile)
    cgpa = overall_cgpa(profile)
    grades = dict(profile.grades or {})
    if not grades and isinstance(profile.spm_prereq_grades, dict) and profile.spm_prereq_grades:
        grades = dict(profile.spm_prereq_grades)
    profile.grades = grades
    profile.stpm_grades, profile.stpm_cgpa = {}, None
    profile.higher_cgpa, profile.higher_koko, profile.higher_institution_type = None, None, ''
    profile.completed_qualifications = ['spm'] if grades else []
    profile.results_exam_type = 'spm' if grades else ''
    profile.exam_type = 'spm'
    profile.save(update_fields=['grades', 'stpm_grades', 'stpm_cgpa', 'higher_cgpa', 'higher_koko',
                                'higher_institution_type', 'completed_qualifications',
                                'results_exam_type', 'exam_type'])
    note = _note(application, 'only_spm', cleared=before, cgpa=cgpa, by=by)
    try:
        del application._requirements_memo
    except AttributeError:
        pass
    application._results_destination = None
    logger.info('AUDIT results_cleared_to_spm app=%s profile=%s cleared=%s submitted=%s',
                application.id, profile.pk, before, application.profile_completed_at is not None)
    return note
