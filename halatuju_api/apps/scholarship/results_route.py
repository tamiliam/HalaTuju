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

The student actions (D13, after the detection notes in `higher_results.py`) are open ONLY BEFORE the
Step-4 Submit (adversarial review, fixes 1+2): after it the frozen requirement, the reviewed slip
and any award stand, and the reviewer's own request route is the way. Each leaves a note the
reviewer sees (`results_change_notes`, fix 3) — a student shortlisted on a CGPA must never arrive
silently as SPM.
  * ``refile_to_spm`` — "Move it to SPM results slip": an SPM slip uploaded into the higher-results
    card is re-filed into the SPM slot (the file kept, read again as an SPM slip).
  * ``refile_to_higher`` (S4, D15) — "Move it to STPM results": the mirror of ``refile_to_spm``, for
    a higher result uploaded into the SPM card (note kind ``refiled_higher``).
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
                            'mara', 'tvet_other', 'diploma'})
#: `offer_pathway.detect_pathway_type` answers that name a post-SPM programme.
_POST_SPM_TYPES = frozenset({'stpm', 'matric', 'asasi', 'pismp', 'diploma'})
#: Lead's ruling (review fix 4): pre-university pathways a TERTIARY holder has already completed or
#: passed. Stored as her pathway with no course, it is a stale autofill (her own Form Six / college
#: letter), not where she is going → undecided, so the results held decide (live #196, #147).
_PASSED_PRE_U = frozenset({'stpm', 'matric', 'asasi'})


def gift_asks_higher(application) -> bool:
    """Owner rulings D16 + D16c (2026-10-27): does this application's gift ask for STPM-level
    results? INFERRED from its INTAKE — the ONE place the instruction lives: `cohort.min_stpm_pngk`
    set → it asks; blank → SPM only. (D16's per-gift `Programme.asks_higher_results` switch is
    superseded and no longer read; its column waits for a later drop.)

    False (BrightPath flagship's b40-2026, floor cleared — a post-SPM programme): SPM-only for
    academic evidence — no D12/D14 mapping (`map_documents`), no `higher_owed` slot / cap / ask, no
    "Move it to STPM results" (`wrong_slip.move_offered`); and the gate tests an STPM-level holder
    on the SPM bars (`shortlisting._academic_ok`). True — and no intake at all (the platform floor)
    — is every rule as before. A submitted application's frozen snapshot is never rewritten."""
    cohort = getattr(application, 'cohort', None) if application is not None else None
    if cohort is None or not hasattr(cohort, 'min_stpm_pngk'):     # a stub carrying no floor field
        return True
    return cohort.min_stpm_pngk is not None


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


def degree_bound(application) -> bool:
    """Bound for (or studying for) a university degree: `destination` DEGREE; or, with no catalogue
    `course_id` (the catalogue decides when there is one), the chosen programme's NAME reads as a
    degree even under a post-SPM pathway code (#251: a stale 'stpm' code; the name is the offer's own,
    autofilled). A UA diploma / PISMP reads 'diploma' / 'pismp'. No document is read: the offer
    letter's programme was assessed and adds nothing the autofilled name does not carry.

    Promoted from `higher_owed._degree_bound` (2026-11-07, moves only) so the funding estimate
    (`funding_estimate.classify_pathway`) and the award rule (`award.proposed_award_amount`) ask the
    same question the higher-results route does."""
    if destination(application) == DEGREE:
        return True
    prog = getattr(application, 'chosen_programme', None)
    prog = prog if isinstance(prog, dict) else {}
    if str(prog.get('course_id') or '').strip():
        return False
    name = (prog.get('course_name') or '').strip()
    from .offer_pathway import detect_pathway_type
    return bool(name) and detect_pathway_type(name, prog.get('institution') or '') == 'degree'


def _already_passed(application, code) -> bool:
    """A pre-U code (or her own held kind) recorded as the pathway of a TERTIARY holder."""
    from apps.courses.public import is_tertiary
    kind = held(application)
    return is_tertiary(kind) and (code in _PASSED_PRE_U or code == kind)


def held(application) -> str:
    """The results held (`exam_questions.results_held`) for this application's student."""
    from apps.courses.public import results_held
    return results_held(getattr(application, 'profile', None))


def higher_need(application) -> str:
    """How this application treats the higher-results upload: 'required' (and the SPM slip
    becomes optional, D9), 'required_with_slip' (both required) or '' (not shown).

    Owner ruling (2026-10-26, overriding the builder's interim "offer it"): a university DEGREE
    needs post-SPM results, so a degree-bound student holding ONLY SPM is REQUIRED to upload them
    too — before submit; a submitted application keeps its frozen requirement. Her SPM slip stays
    REQUIRED as well, so she always has academic evidence on file, and the card tells her plainly
    to enter her higher results or choose a post-SPM pathway."""
    from apps.courses.public import is_tertiary
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
    if not gift_asks_higher(application):
        return resolved                    # D16: an SPM-only gift — the SPM slip as the programme set it
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


def held_kind(application) -> str:
    """The results held, when tertiary; '' otherwise."""
    from apps.courses.public import is_tertiary
    kind = held(application)
    return kind if is_tertiary(kind) else ''


def upload_kind(application, request_code: str = '') -> str:
    """The `results_kind` a new higher-results upload carries: the results held, when tertiary
    (D13 — the card shows it read-only and "Change" opens the results page). S4 (#37): an upload
    answering an officer's request for named results carries THAT request's kind
    (`results_requests.requested_kind`), so it lands in the right slot whatever the results page
    holds. '' otherwise."""
    from . import higher_owed
    from .results_requests import requested_kind
    # 2026-11-07: a submitted legacy row owing them carries the kind she ENTERED (held SPM, STPM grades)
    return requested_kind(application, request_code) or held_kind(application) or higher_owed.upload_kind(application)


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


def is_team_note(note) -> bool:
    """A note the TEAM wrote (owner, 2026-11-06: "They have served their purpose"): a split of a
    combined upload (`team_split`, always the team) or a refile done by the team (`by == 'team'`)."""
    return isinstance(note, dict) and (note.get('kind') == 'team_split' or (
        note.get('kind') in ('refiled_higher', 'refiled_spm') and note.get('by') == 'team'))


def cockpit_notes(notes) -> list:
    """The `results_change_notes` the cockpit is SERVED: the student's own (a refile, "SPM results
    only"), never the team's housekeeping (`is_team_note`). The stored list is untouched -
    `wrong_slip` still reads the team's `refiled_higher` notes to know a document was moved."""
    return [n for n in (notes if isinstance(notes, list) else []) if not is_team_note(n)]


class ServesTheStudentsResultsNotes:
    """The officer's detail payload serves `results_change_notes` through `cockpit_notes` (the
    value replaced in place, so the key keeps its position; `serializers_admin.py` is at its size
    allowance, the reason `serializers_admin_gift` gives for appending in `to_representation`)."""

    def to_representation(self, instance):
        data = super().to_representation(instance)
        if 'results_change_notes' in data:
            data['results_change_notes'] = cockpit_notes(data['results_change_notes'])
        return data


_MOVE_FIELDS = ['doc_type', 'results_kind', 'request_code', 'vision_fields', 'vision_fields_run_at',
                'vision_run_at', 'vision_name_match', 'vision_address_match', 'vision_error']


def _move_into_slot(application, doc, existing, doc_type, promotion, ApplicantDocument):
    """Save a re-filed ``doc`` (its new slot fields already set in memory) into ``doc_type``'s slot.
    Returns True when moved, False when a rival kept clashing (the doc stays where it was — no 500).
    The weaker of it and ``existing`` becomes history, as before. TD-115 (A1.8): the slot's unique
    index admits ONE live row, so nothing goes live while another is: on a promote the other live
    copies are superseded FIRST and then the doc is saved; on a keep the doc is saved already
    superseded (one write). Same decision as before — `should_promote` reads only the in-memory doc."""
    from django.db import IntegrityError, transaction
    for attempt in (1, 2):
        try:
            with transaction.atomic():      # savepoint: a clash must not poison the caller's transaction
                now = timezone.now()
                if existing is None or promotion.should_promote(doc, existing, usable=True):
                    ApplicantDocument.objects.filter(
                        application=application, doc_type=doc_type, superseded_at__isnull=True,
                    ).exclude(id=doc.id).update(superseded_at=now, superseded_by=doc)
                    doc.save(update_fields=_MOVE_FIELDS)
                else:
                    doc.superseded_at, doc.superseded_by = now, existing
                    doc.save(update_fields=_MOVE_FIELDS + ['superseded_at', 'superseded_by'])
            doc.refresh_from_db()
            return True
        except IntegrityError:
            # A rival went live in the target slot meanwhile. Retry once (the supersede above then
            # takes it too, as the upload door does); a second clash leaves the document where it was.
            logger.warning('AUDIT results_refile_slot_conflict app=%s doc=%s into=%s attempt=%s',
                           application.id, doc.id, doc_type, attempt)
    doc.refresh_from_db()                   # the write rolled back: back to the slot it came from
    return False


def refile_to_spm(application, doc, *, by: str = '', **note_fields) -> 'object':
    """Move a higher-results upload that reads as an SPM slip into the SPM slot, BEFORE submit only
    (the caller refuses otherwise). The FILE is kept; its higher-results READ is cleared (fix 6) so
    the live service reads it again as an SPM slip — the self-heal sweep picks up a document whose
    run stamps are NULL and whose `vision_fields` is empty (`services.blockers`); it is never
    re-read from a local checkout. One live slip per slot: the moved slip and any live SPM slip are
    compared by `promotion.should_promote` and the weaker becomes history (Old / Replaced). The
    higher-results card then asks again. A reviewer note records the move. Returns the document.

    ``by`` / ``note_fields`` (2026-10-28, `split_combined_results`): the TEAM's move records
    ``by='team'`` and its own fields on the note; a student's move passes neither, so its note is
    exactly as before."""
    from django.db import transaction
    from . import promotion
    from .document_snapshot import live_docs
    from .models import ApplicantDocument
    with transaction.atomic():
        # Lock the row (as refile_to_higher does), so a double tap moves it - and notes it - once.
        locked = ApplicantDocument.objects.select_for_update().filter(pk=doc.pk).first()
        if locked is None or locked.doc_type == 'results_slip' or locked.superseded_at is not None:
            return locked or doc
        doc = locked
        existing = live_docs(application, 'results_slip').exclude(id=doc.id).first()
        doc.doc_type, doc.results_kind, doc.request_code = 'results_slip', '', ''
        doc.vision_fields, doc.vision_fields_run_at, doc.vision_run_at = {}, None, None
        doc.vision_name_match, doc.vision_address_match, doc.vision_error = '', '', ''
        if not _move_into_slot(application, doc, existing, 'results_slip', promotion, ApplicantDocument):
            return doc
    _note(application, 'refiled_spm', document_id=doc.id, **({'by': by} if by else {}), **note_fields)
    logger.info('AUDIT results_refiled_to_spm app=%s doc=%s kept_existing=%s', application.id,
                doc.id, bool(doc.superseded_at))
    from .resolution import sync_resolution_items
    sync_resolution_items(application)
    return doc


def refile_to_higher(application, doc, kind, *, by: str = 'student', **note_fields) -> 'object':
    """D15 (S4, 2026-10-27) — the mirror of `refile_to_spm`: "Move it to STPM results". A document
    in the SPM card that reads as a higher result (`wrong_slip.higher_kind`) is re-filed into the
    higher-results card with that kind, BEFORE submit only (the caller refuses otherwise, and offers
    it only where the higher card is shown, D12). The FILE is kept; its SPM-slip READ is cleared so
    the live service reads it again as higher results — the hourly sweep picks up a document whose
    run stamps are NULL and whose `vision_fields` is empty; it is never re-read from a local
    checkout. One live higher-results upload: the moved document and any live one are compared by
    `promotion.should_promote` and the weaker becomes history. If the kind differs from the results
    page, the S3 "Different results" note then speaks in the higher card. A reviewer note of its own
    kind (`refiled_higher`) records the move, ``by`` the student unless the team's command
    (`split_combined_results`, ``by='team'`` plus its own ``note_fields``) says so. Returns the document."""
    from django.db import transaction
    from . import promotion
    from .document_snapshot import live_docs
    from .models import ApplicantDocument
    with transaction.atomic():
        # Review finding 5: lock the row, so a double tap moves it — and notes it — once.
        locked = ApplicantDocument.objects.select_for_update().filter(pk=doc.pk).first()
        if locked is None or locked.doc_type != 'results_slip' or locked.superseded_at is not None:
            return locked or doc
        return _refile_to_higher_locked(application, locked, kind, promotion, live_docs, ApplicantDocument,
                                        by=by, **note_fields)


def _refile_to_higher_locked(application, doc, kind, promotion, live_docs, ApplicantDocument, *,
                             by='student', **note_fields):
    existing = live_docs(application, 'higher_results').exclude(id=doc.id).first()
    doc.doc_type, doc.results_kind, doc.request_code = 'higher_results', kind, ''
    doc.vision_fields, doc.vision_fields_run_at, doc.vision_run_at = {}, None, None
    doc.vision_name_match, doc.vision_address_match, doc.vision_error = '', '', ''
    if not _move_into_slot(application, doc, existing, 'higher_results', promotion, ApplicantDocument):
        return doc
    _note(application, 'refiled_higher', document_id=doc.id, results_kind=kind, by=by, **note_fields)
    logger.info('AUDIT results_refiled_to_higher app=%s doc=%s kind=%s kept_existing=%s',
                application.id, doc.id, kind, bool(doc.superseded_at))
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
    from apps.courses.public import overall_cgpa, results_held
    profile = application.profile
    before = results_held(profile)
    cgpa = overall_cgpa(profile)
    grades = dict(profile.grades or {})
    if not grades and isinstance(profile.spm_prereq_grades, dict) and profile.spm_prereq_grades:
        grades = dict(profile.spm_prereq_grades)
    profile.grades = grades
    profile.stpm_grades, profile.stpm_cgpa, profile.stpm_koko = {}, None, None
    profile.higher_cgpa, profile.higher_koko, profile.higher_institution_type = None, None, ''
    profile.completed_qualifications = ['spm'] if grades else []
    profile.results_exam_type = 'spm' if grades else ''
    profile.exam_type = 'spm'
    profile.save(update_fields=['grades', 'stpm_grades', 'stpm_cgpa', 'stpm_koko', 'higher_cgpa', 'higher_koko',
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
