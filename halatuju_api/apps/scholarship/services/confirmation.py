"""
The student confirming a complete Step-4 profile, and confirming a pathway.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import logging

from django.utils import timezone

from .. import requirements
from ..emails import (
    send_profile_complete_admin_email, send_submission_received_email,
)
from .completeness import application_completeness
from .errors import IncompleteProfileError, RoundFinishedError

#: ⚠ THE PACKAGE NAME, WRITTEN OUT. Never `__name__`: in a submodule that reads
#: `apps.scholarship.services.<module>`, and the one `assertLogs('apps.scholarship.services')`
#: site would still pass (a parent logger records its children) while the name on every line
#: changed underneath it. H11 met exactly this in `views_admin`.
logger = logging.getLogger('apps.scholarship.services')


def confirm_profile(application):
    """Phase C: the student explicitly confirms a complete Step-4 profile.

    Flips status shortlisted → profile_complete, stamps ``profile_completed_at``,
    and notifies the admin. Idempotent: a second call on an already-confirmed (or
    further-along) application is a no-op returning False. Raises
    ``IncompleteProfileError`` (carrying the completeness dict) if the profile
    isn't complete. Completion is NOT a freeze — the student keeps editing rights
    (see POST_SHORTLIST_EDITABLE).
    """
    if application.status != 'shortlisted':
        return False  # already confirmed / further along — idempotent no-op
    # ⚠⚠ A FINISHED ROUND TAKES NO MORE SUBMISSIONS, AND THIS IS THE ONLY PLACE THAT IS TRUE.
    # Closing a round (`is_open=False`) stops NEW applications and nothing else — the intake gate
    # lives on `ApplicationCreateView` and a returning applicant never reaches it again. That grace
    # period is deliberate and production relied on it (thirty students submitted between the 2026
    # round closing on 1 July and the deadline on the 7th). `finished_at` is where the grace period
    # ends, so the refusal belongs on the SUBMIT path, not beside the create gate.
    cohort = application.cohort
    if cohort and cohort.finished_at:
        raise RoundFinishedError(cohort.code)
    completeness = application_completeness(application)
    if not completeness['complete']:
        raise IncompleteProfileError(completeness)
    # Layer 0: freeze what the programme asked for AT THIS MOMENT, before the status flips —
    # the same resolution the gate above just enforced. From here on a configuration change
    # cannot re-gate this student (see `requirements.freeze`). Saved in the same statement as
    # the status so the two can never be observed apart.
    requirements.freeze(application, save=False)
    application.status = 'profile_complete'
    application.profile_completed_at = timezone.now()
    application.save(update_fields=['status', 'profile_completed_at', 'requirements_snapshot'])
    # Best-effort admin notification (never blocks the confirm).
    name = getattr(application.profile, 'name', '') if application.profile else ''
    send_profile_complete_admin_email(application_id=application.id, applicant_name=name,
                                      programme_name=application.cohort.name)
    # Check 2: acknowledge the submission NOW (warm "we've got it, we'll review and
    # revert") and raise the clarify queries SILENTLY. The "we have a few questions"
    # email is deliberately delayed (send_due_query_emails, ~2h later) so it reads as a
    # human review, not an instant bot reply. All best-effort — never blocks the confirm.
    # The richer "your application is in — here's what happens next" email supersedes the
    # basic submission-ack when PROFILE_COMPLETE_EMAIL_ENABLED is on (avoids a double-email).
    from django.conf import settings as _settings
    from .. import usage as _usage
    with _usage.usage_context(application=application):
        if getattr(_settings, 'PROFILE_COMPLETE_EMAIL_ENABLED', False):
            from ..emails import english_only_email, send_profile_complete_student_email
            send_profile_complete_student_email(
                application.notify_email, student_name=name,
                english_only=english_only_email(application))
        else:
            send_submission_received_email(
                to_email=application.notify_email, applicant_name=name,
                programme_name=application.cohort.name, lang=application.locale)
    try:
        from ..check2_queries import sync_check2_queries
        from ..resolution import sync_resolution_items
        sync_check2_queries(application)
        # Also materialise the system gaps NOW (missing-compulsory-doc requests etc.) so the
        # delayed query email can count them — the "review assistant" asks for them too.
        sync_resolution_items(application)
    except Exception:  # noqa: BLE001 — query raising must never fail a submission
        import logging
        logging.getLogger(__name__).warning(
            'Check-2 query raise failed for app %s', application.id, exc_info=True)
    return True


def confirm_pathway(application):
    """Record the student's latest offer letter as their FINAL chosen pathway.

    Driven by the student answering the AI-raised ``pathway_confirm`` Action-Centre
    query Yes (no human officer). Writes the offer's programme + institution into
    ``chosen_programme`` and stamps ``pathway_confirmed_at`` so the Pathway verdict
    reads 'verified'. Idempotent-ish (re-confirming just refreshes the snapshot).
    Returns False when there's no offer letter to confirm."""
    from .. import offer_pathway as op
    from ..models import ApplicantDocument
    from ..pathway_engine import student_offer_check
    offer = (ApplicantDocument.objects.filter(
                application=application, doc_type='offer_letter', superseded_at__isnull=True)
             .order_by('-uploaded_at').first())
    if offer is None:
        return False
    chk = student_offer_check(offer)
    # Write-side guard (defence-in-depth): never store a mis-slotted offer value — a date/'Tarikh'
    # line in the institution slot, or an institution name in the programme slot (the #125 fault).
    # A parsed date fills reporting_date (when null); junk is dropped rather than stored.
    from .. import card_display
    from ..pathway_engine import parse_reporting_date
    prog, inst, rep_raw = card_display.sanitise_offer_slots(chk['programme'], chk['institution'])
    if not prog and (chk['programme'] or '').strip():
        logger.warning('offer-confirm guard dropped an institution-shaped programme (doc %s)', offer.id)
    # Offer letters are often ALL-CAPS; re-case a shouty programme name to Title Case so it
    # never reaches the sponsor pool / profile shouting (catalogue names are already cased — this
    # is the one path that writes raw offer text). Already-cased names pass through untouched.
    cp = dict(application.chosen_programme) if isinstance(application.chosen_programme, dict) else {}
    cp.update({'course_name': op.title_case_programme(prog),
               'institution': inst,
               'source': 'offer_letter_confirmed'})
    application.chosen_programme = cp
    application.pathway_confirmed_at = timezone.now()
    update_fields = ['chosen_programme', 'pathway_confirmed_at']
    if rep_raw and application.reporting_date is None:
        _d = parse_reporting_date(rep_raw)
        if _d:
            application.reporting_date = _d
            update_fields.append('reporting_date')
            logger.warning('offer-confirm guard recovered reporting_date from a mis-slotted '
                           'institution value (doc %s)', offer.id)

    # TD-161: reconcile the pathway TYPE. confirm_pathway writes the programme but never the type;
    # a genuine offer of a DIFFERENT type than declared means the student is switching pathway
    # (#43: STPM → PISMP). Adopt the offer's detected type and drop the now-irrelevant pre-U
    # stream + school, so the record stops contradicting itself — chosen_pathway had stayed on the
    # ORIGINAL declaration, misclassifying funding. Same-type confirms are a no-op here.
    #
    # THIS RUNS FIRST, before the pre-U normalisation below, because that block is GATED on the
    # pathway type and must read the reconciled one (request #7, 2026-08-01). It used to sit after,
    # so a student who never declared a pathway — chosen_pathway '' — had the whole pre-U block
    # skipped on the stale value, and the type was then corrected 40 lines too late to matter:
    # #32 kept her offer's raw "Program Matrikulasi (SAINS)" at "KOLEJ MATRIKULASI SELANGOR" with
    # no track and no school, and read `matric` beside all three. An empty declaration is the
    # NORMAL case for a student who applies uncertain (`pathway_certainty='uncertain'`).
    offer_type = op.detect_pathway_type(prog, chk['institution'])
    ofam = op.pathway_family(offer_type)
    if ofam and ofam != op.pathway_family(application.chosen_pathway or ''):
        application.chosen_pathway = offer_type
        if 'chosen_pathway' not in update_fields:
            update_fields.append('chosen_pathway')
        if not op.is_pre_u(offer_type):
            for _f in ('pre_u_track', 'pre_u_institution'):
                if (getattr(application, _f) or '').strip():
                    setattr(application, _f, '')
                    if _f not in update_fields:
                        update_fields.append(_f)

    # The confirm query promises "we'll update your record to match" — so for an INSTITUTION
    # pathway (matric/STPM), also bring the displayed pre-U fields into line with the confirmed
    # offer. Without this, chosen_programme reflected the offer but `pre_u_institution` /
    # `pre_u_track` stayed on the student's ORIGINAL declaration, so the cockpit kept showing the
    # old school and the offer's Pathway chip kept a stream clash red (#117: confirmed a Sains
    # offer at Kolej Tingkatan Enam Gombak, but the record still read Sains Sosial at SMK P
    # Temenggong Ibrahim). The student confirmed THIS offer, so the offer is now authoritative.
    pw = (application.chosen_pathway or '').strip().lower()
    if op.is_pre_u(pw):
        vf = offer.vision_fields if isinstance(offer.vision_fields, dict) else {}
        f = vf.get('fields', {}) if isinstance(vf.get('fields'), dict) else {}
        if pw == 'stpm':
            stream = op.parse_stpm_stream(f'{f.get("stream", "")} {chk["programme"]}')
            inst = op.clean_school_name(chk['institution'])
        else:  # matric — track from the programme, institution from the state-unique catalogue
            stream = op.parse_matric_track(chk['programme'])
            vc = op.preu_course_id('matric', stream or (application.pre_u_track or ''))
            inst = (op.catalogue_institution(vc, chk['institution']) if vc else '') \
                or op.clean_school_name(chk['institution'])
        if inst and inst != (application.pre_u_institution or ''):
            application.pre_u_institution = inst
            update_fields.append('pre_u_institution')
        if stream and stream != (application.pre_u_track or ''):
            application.pre_u_track = stream
            update_fields.append('pre_u_track')
        # Standardise chosen_programme to match the SILENT auto-settle (canonical course name +
        # the same cleaned institution), so a CONFIRMED pre-U pick reads identically to an
        # auto-settled one — never the raw "Tingkatan Enam Semester 1" / ALL-CAPS school the offer
        # prints (owner 2026-07-17; #119/#120 vs #103). The whole-doc write above kept the raw text.
        # Gate on the OFFER's own detected type (like autofill), NOT the declared pathway: a pre-U
        # pathway confirmed against an offer we could not type (detect returns '' — no keyword we
        # recognise) must keep its real programme name, never be forced to "Tingkatan Enam". A
        # CROSS-family offer (#43: stpm declared, PISMP offer) no longer reaches here at all — the
        # reconciliation above has already moved chosen_pathway off pre-U.
        if op.is_pre_u(offer_type):
            canon = op.canonical_pre_u_course(pw)
            cp_std = dict(application.chosen_programme) if isinstance(application.chosen_programme, dict) else {}
            if canon:
                cp_std['course_name'] = canon
            if inst:
                cp_std['institution'] = inst
            application.chosen_programme = cp_std   # chosen_programme already in update_fields

    # PISMP (owner 2026-07-18): pin the SPECIFIC catalogue course from the offer's stated BIDANG when it
    # resolves to a unique course (a vernacular bidang — Bahasa Tamil → SJKT). Recording the course_id
    # makes the cockpit link the right PISMP course instead of a stale STPM one (the #43 display bug).
    # A multi-aliran bidang is pinned via the profile Aliran picker instead (no unique course here).
    if offer_type == 'pismp':
        resolved = op.resolve_pismp_course((chk.get('bidang') or '').strip())
        if resolved:
            cp = dict(application.chosen_programme) if isinstance(application.chosen_programme, dict) else {}
            cp.update({'course_id': resolved['course_id'], 'course_name': resolved['course_name'],
                       'institution': cp.get('institution') or chk['institution'],
                       'source': 'offer_letter_confirmed'})
            application.chosen_programme = cp
            if 'chosen_programme' not in update_fields:
                update_fields.append('chosen_programme')

    # Align the institution to the recommender CATALOGUE — the single source of truth (owner
    # 2026-07-18). Offer letters often print the institution ALL-CAPS ("INSTITUT PENDIDIKAN GURU
    # KAMPUS TUANKU BAINUN") and confirm_pathway stored that raw text; the catalogue holds the clean
    # title-case name (the course selector reads it). For a catalogue-linked (tertiary) programme,
    # swap in the catalogue's canonical spelling when it UNIQUELY matches the stored value (same
    # place, cleaner — never a different institution). Matric aligns in the pre-U branch above; STPM
    # schools are deliberately NOT catalogue-matched. Mirrors autofill_pathway_from_offer.
    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    _cid = (cp.get('course_id') or '').strip()
    _inst = (cp.get('institution') or '').strip()
    if _cid and _inst and not op.is_pre_u(application.chosen_pathway or ''):
        canon = op.catalogue_institution(_cid, _inst)
        if canon and canon != _inst:
            cp = dict(cp)
            cp['institution'] = canon
            application.chosen_programme = cp
            if 'chosen_programme' not in update_fields:
                update_fields.append('chosen_programme')

    application.save(update_fields=update_fields)
    return True
