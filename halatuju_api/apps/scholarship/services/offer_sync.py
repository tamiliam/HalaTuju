"""
Reading an offer letter back onto the application: dates, institution, pathway.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
import logging

from django.utils.dateparse import parse_date

from .completeness import application_completeness

#: ⚠ THE PACKAGE NAME, WRITTEN OUT. Never `__name__`: in a submodule that reads
#: `apps.scholarship.services.<module>`, and the one `assertLogs('apps.scholarship.services')`
#: site would still pass (a parent logger records its children) while the name on every line
#: changed underneath it. H11 met exactly this in `views_admin`.
logger = logging.getLogger('apps.scholarship.services')


def sync_reporting_date_from_offer(application, offer=None):
    """Copy the offer letter's reporting date into ``ScholarshipApplication.reporting_date``.

    THE single owner of that copy (owner 2026-07-23). It exists as its own function because the
    date is an independent fact — when the student starts — that has nothing to do with settling
    which PATHWAY they are on, yet it used to be written at the bottom of
    ``autofill_pathway_from_offer``, below four guards that abandon on a pathway disagreement.
    Result: the students whose offer disagreed with their declaration (exactly the ones sent a
    "please confirm" query) silently lost their date, and with it the correct bursary size and
    their semester-result request.

    A later re-extraction that yields a date DOES overwrite an officer-entered one, deliberately:
    the officer only typed a value because the letter had none, so a letter we can now read is
    better evidence than a human's inference. Returns True when it wrote.
    """
    from ..models import ApplicantDocument
    from ..pathway_engine import student_offer_check, parse_reporting_date
    if offer is None:
        offer = (ApplicantDocument.objects.filter(
                    application=application, doc_type='offer_letter', superseded_at__isnull=True)
                 .order_by('-uploaded_at').first())
    if offer is None:
        return False
    rd = parse_reporting_date(student_offer_check(offer).get('reporting_date'))
    if rd is None or application.reporting_date == rd:
        return False
    application.reporting_date = rd
    application.save(update_fields=['reporting_date'])
    return True


def sync_institution_from_catalogue(application, offer=None, offer_check=None):
    """Fill a BLANK ``chosen_programme.institution`` — WHERE the student will study.

    THE single owner of that copy, and its own function for the same reason
    ``sync_reporting_date_from_offer`` is: the institution is an independent fact that has nothing
    to do with settling which PATHWAY a student is on, yet it used to be written at the bottom of
    ``autofill_pathway_from_offer``, below four guards that abandon on a name/IC/junk/pathway
    disagreement (lessons #11 — "a fact riding as a passenger in a function whose real job is
    something else inherits every one of that function's exits"). #48 is the proof: one letter, one
    function, the date hoisted in 2026-07-23 and the institution left behind, so the cockpit showed
    a ticked reporting date beside an empty Institution.

    It matters because the field is sponsor-facing and its blank is INVISIBLE, not ugly:
    ``card_display.resolve_institution`` returns '' and the sponsor FE renders the line only when
    truthy, so an unfilled institution doesn't read as "—" to a sponsor — the line vanishes from the
    card. Owner 2026-07-25: it is a must-fill.

    Resolution order, most authoritative first — each already-sanctioned machinery, nothing new:
      1. the course is offered at exactly ONE campus → the catalogue IS the answer
         (``sole_catalogue_institution``; needs no offer at all, so it fixes a student who has
         uploaded nothing yet);
      2. multi-campus → the OFFER letter's institution, validated against the catalogue's campus
         list (``catalogue_institution``) — used ONLY when the letter is the applicant's own
         (name/IC not mismatched), so a wrong-person letter can never name a campus;
      3. MATRIC with no course_id → the catalogue college for the declared state, via the
         ``matric-<track>`` virtual course (12 state-unique colleges → a safe unique match).

    Deliberately NOT resolved: **STPM**. Its ~250 near-identical school names make a catalogue match
    unsafe (lessons #378), and laundering the student's own declared school into ``chosen_programme``
    would attribute their answer to the offer letter — the #117(d) guard. A blank STPM institution is
    a human's to fill, not this function's to guess.

    Never overwrites a non-blank value (a stored institution is the caller's to protect; junk is
    fixed at source, per ``card_display``). Only the ``institution`` sub-key is touched —
    ``course_id``/``course_name``/``source`` are preserved, so nothing is re-attributed to the offer.
    Idempotent. Returns True when it wrote.
    """
    from ..models import ApplicantDocument
    from ..pathway_engine import student_offer_check
    from .. import offer_pathway as op

    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    if (cp.get('institution') or '').strip():
        return False                      # already recorded — never overwrite

    cid = (cp.get('course_id') or '').strip()

    # Read the letter once (the caller usually already has). Needed even for the sole-campus case,
    # because a letter that CONTRADICTS the declared course is a stop — see below.
    if offer_check is None:
        if offer is None:
            offer = (ApplicantDocument.objects.filter(
                        application=application, doc_type='offer_letter',
                        superseded_at__isnull=True)
                     .order_by('-uploaded_at').first())
        offer_check = student_offer_check(offer) if offer is not None else {}
    wrong_person = (offer_check.get('name') == 'mismatch'
                    or offer_check.get('ic') == 'mismatch')
    offer_inst = '' if wrong_person else (offer_check.get('institution') or '').strip()
    # Junk in the institution slot (a leaked clause number "2.5." / a 'Tarikh' line — #47/#125) is
    # not an institution and must not be read as disagreeing with anything.
    from .. import card_display
    if offer_inst and (card_display.looks_like_clause_number(offer_inst)
                       or card_display.looks_like_date(offer_inst)):
        offer_inst = ''

    resolved = op.sole_catalogue_institution(cid) if cid else ''
    if resolved and op.offer_contradicts_course_institution(cid, offer_inst):
        # The student's own letter names an institution that is NOT a campus of the course they
        # declared (#11 Politeknik Ungku Omar vs a UPNM asasi, #64 i-CATS vs UPM, #86 Cyberjaya vs
        # UMK, #113 UTAR vs UMK, #93 UniMAIWP vs UMK — every one a private/other place against a
        # declared public course). The catalogue's answer would be *consistent with the declaration*
        # and *wrong about the student*, on a SPONSOR-FACING field. Abstain: the pathway verdict
        # already raises this as a clash for a human to settle, and `backfill_institution` lists it.
        resolved = ''
    elif not resolved:
        if cid and offer_inst:
            # Multi-campus: the letter names the campus, the catalogue validates it is a campus OF
            # THIS course (unique match) and supplies the canonical casing.
            resolved = op.catalogue_institution(cid, offer_inst)
        elif not cid and (application.chosen_pathway or '').strip().lower() == 'matric':
            track = (application.pre_u_track or '').strip().lower()
            vc = op.preu_course_id('matric', track)
            hint = offer_inst or (application.pre_u_institution or '').strip()
            resolved = op.catalogue_institution(vc, hint) if (vc and hint) else ''

    if not resolved:
        return False
    application.chosen_programme = {**cp, 'institution': resolved}
    application.save(update_fields=['chosen_programme'])
    return True


def set_reporting_date_by_officer(application, admin, value):
    """Record a reporting date an officer established by hand — the fallback for a letter that
    carries no readable date (owner 2026-07-23).

    No provenance columns by owner decision: this is a rare one-off, and the cockpit already
    distinguishes a typed date from a documented one for free (its verified tick reads DOCUMENT
    corroboration, so a hand-typed date renders without one). WHO typed it is captured by the
    AUDIT log line below — the same treatment other one-off admin corrections get.

    Raises ValueError('date_required') on a blank/unparseable value."""
    if value is None or str(value).strip() == '':
        raise ValueError('date_required')
    if isinstance(value, str):
        value = parse_date(value.strip())
        if value is None:
            raise ValueError('date_required')
    application.reporting_date = value
    application.save(update_fields=['reporting_date'])
    logger.info('AUDIT reporting_date_set app_id=%s by=%s value=%s',
                application.id, (getattr(admin, 'email', '') or '?'), value)
    return True


def autofill_pathway_from_offer(application):
    """Silently settle a pathway the student had NOT yet locked, from a verified offer
    letter — no student query (the undecided→decided case the ``pathway_confirm`` query
    is *not* for). Mirrors the apply form's own storage shapes (see ``offer_pathway``):
    pre-U → ``chosen_pathway`` + ``pre_u_track`` + ``pre_u_institution`` (school as text);
    tertiary → ``chosen_programme`` with a canonical ``course_id`` on a confident catalogue
    match, else plain labels. Also clears the "still deciding" framing (``pathway_certainty
    = 'sure'``) so the cockpit stops showing the student as exploring.

    Deliberately does NOT stamp ``pathway_confirmed_at`` — that short-circuits the verdict
    BEFORE the clash check, so stamping here would mask a future genuinely-different offer.
    The verdict reaches 'verified' on its own (readable, non-clashing offer); writing
    ``chosen_programme`` also means a later clashing offer is now compared against it and
    correctly raises ``pathway_confirm``.

    Fires only when the offer is the applicant's (identity not mismatched), readable, and
    NOT a genuine clash with an already-specific declared programme (that stays the
    ``pathway_confirm`` query's job). No-op (returns False) otherwise. Idempotent."""
    from ..models import ApplicantDocument
    from ..pathway_engine import student_offer_check
    from .. import offer_pathway as op

    offer = (ApplicantDocument.objects.filter(
                application=application, doc_type='offer_letter', superseded_at__isnull=True)
             .order_by('-uploaded_at').first())
    if offer is None:
        return False
    # FIRST, unconditionally: the reporting date is an independent fact about WHEN the student
    # starts. It used to be written at the BOTTOM of this function, below four `return False`
    # guards about the PATHWAY — so a letter whose programme disagreed with the declaration (the
    # very case that raises the confirm query) lost its date as collateral damage. 45% of
    # applications that needed a pathway confirm had a NULL date against 3.8% of the rest.
    # Its result is folded into this function's return value, which means "did I write
    # anything" (backfill_offer_pathways counts on it) — so moving the write out must not
    # silently turn a real update into a reported no-op.
    date_written = sync_reporting_date_from_offer(application, offer=offer)
    chk = student_offer_check(offer)
    # SECOND, also unconditionally: WHERE the student studies is likewise independent of settling
    # the pathway, and used to be written below these same guards — which is how #48 ended up with
    # a ticked reporting date and an empty Institution. sync_institution_from_catalogue owns the
    # copy now (it does its own wrong-person check before using the letter as a campus hint), so it
    # runs above every `return` below. Folded into this function's return value for the same
    # reason the date is: the value means "did I write anything".
    inst_written = sync_institution_from_catalogue(application, offer=offer, offer_check=chk)
    wrote_early = date_written or inst_written
    # Wrong-person letter (name OR IC clash) → never adopt.
    if chk['ic'] == 'mismatch' or chk['name'] == 'mismatch':
        return wrote_early
    prog = (chk['programme'] or '').strip()
    inst = (chk['institution'] or '').strip()
    # A bare numbered-clause header ("2.4."/"2.5.") leaked from an offer's section numbering (#47)
    # is never a programme/institution — drop it before it reaches ANY stored field
    # (pre_u_institution as well as chosen_programme), defence-in-depth over the read-side guard.
    from .. import card_display
    if prog and card_display.looks_like_clause_number(prog):
        prog = ''
    if inst and card_display.looks_like_clause_number(inst):
        inst = ''
    if not prog and not inst:
        return wrote_early  # nothing readable to SETTLE — but date/institution may have landed
    # A genuine clash with a SPECIFIC declared programme is the confirm query's job, not a
    # silent overwrite.
    if chk['pathway'] == 'mismatch':
        return wrote_early

    cp = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    locked = bool(cp.get('course_id')) and application.pathway_certainty == 'sure'

    fields = []

    # Pathway ADOPTION only runs when the student hasn't already locked a precise pick —
    # we never silently overwrite a deliberate, confirmed choice. (The reporting date below
    # is settled regardless: it's a fact off the offer, independent of the chosen pathway,
    # so a locked student must still get it persisted — this was the gap that left
    # reporting_date NULL for confirmed applicants.)
    ptype = op.detect_pathway_type(prog, inst)
    pw = (application.chosen_pathway or '').strip().lower() or ptype

    # Standardise the pre-U TRACK first (it's needed below to reach the matric catalogue
    # college). Canonical vocabulary (Matrikulasi: sains/kejuruteraan/sains_komputer/
    # perakaunan; STPM: sains/sains_sosial); fill a blank/'not_sure' only — never clobber a
    # deliberate pick — regardless of lock state.
    track = ''
    if pw == 'matric':
        track = op.parse_matric_track(prog)
    elif pw == 'stpm':
        track = op.parse_stpm_stream(prog)
        if not track:
            profile = getattr(application, 'profile', None)
            track = op.infer_stpm_bidang(getattr(profile, 'grades', None),
                                         getattr(profile, 'stream_subjects', None))
    if track and (application.pre_u_track or '').strip().lower() in ('', 'not_sure'):
        application.pre_u_track = track
        fields.append('pre_u_track')
    effective_track = (application.pre_u_track or track or '').strip().lower()

    def _canonical_preu_institution():
        # Matric → the catalogue college for the student's STATE (via the matric-<track> virtual
        # course; 12 state-unique colleges → safe). STPM → casing-only clean of the recorded
        # school (NO catalogue match: ~250 near-identical names, SMK vs SMJK indistinguishable —
        # would change which school the student attends). '' when nothing resolves.
        if pw == 'matric':
            vc = op.preu_course_id('matric', effective_track)
            hint = (inst or '').strip() or (application.pre_u_institution or '').strip()
            return op.catalogue_institution(vc, hint) if vc else ''
        if pw == 'stpm':
            # #117 (d): standardise ONLY what the offer letter actually read. Passing
            # application.pre_u_institution as a fallback laundered the student's OWN declared
            # school into chosen_programme stamped source='offer_letter_auto' whenever the offer's
            # institution failed to extract — so the cockpit showed the SMK as if the offer said so.
            # If the offer institution is blank, leave it blank rather than attribute the student's
            # own answer to the letter.
            return op.clean_school_name(inst)
        return ''

    if not locked:
        if op.is_pre_u(ptype):
            # Pre-U: structured pathway + school (apply-form parity). Fill blanks only —
            # never clobber something the student deliberately typed.
            if not (application.chosen_pathway or '').strip():
                application.chosen_pathway = ptype
                fields.append('chosen_pathway')
            if not (application.pre_u_institution or '').strip():
                application.pre_u_institution = inst
                fields.append('pre_u_institution')

        # Display programme: a canonical course_id for a confident tertiary match, else labels.
        # Pre-U course names are STANDARDISED ("Program Matrikulasi" / "Tingkatan Enam"; the
        # stream/jurusan lives in pre_u_track) AND the institution is canonicalised here too
        # (matric → catalogue college; STPM → casing-only), so a re-run is idempotent and never
        # reintroduces raw offer wording (e.g. "TINGKATAN ENAM SEMESTER 1 TAHUN 2025").
        # Write-side guard (defence-in-depth): a mis-slotted offer (institution in the
        # programme slot / a 'Tarikh' line in the institution slot — the #125 fault) is
        # sanitised before it can be stored.
        from .. import card_display
        g_prog, g_inst, _rep = card_display.sanitise_offer_slots(prog, inst)
        new_cp = {'course_name': g_prog, 'institution': g_inst, 'source': 'offer_letter_auto'}
        if op.is_pre_u(ptype):
            canon = op.canonical_pre_u_course(ptype)
            if canon:
                new_cp['course_name'] = canon
            canon_inst = _canonical_preu_institution()
            if canon_inst:
                new_cp['institution'] = canon_inst
        else:
            match = op.resolve_catalogue_course(g_prog, g_inst)
            if match:
                new_cp = {**match, 'source': 'offer_letter_auto'}
        # Only overwrite when there's no precise existing pick to protect, and only when the
        # value actually changes (keeps re-runs idempotent).
        if not cp.get('course_id') and cp != new_cp:
            application.chosen_programme = new_cp
            fields.append('chosen_programme')

        # The place is confirmed — drop the "still deciding" framing.
        if application.pathway_certainty != 'sure':
            application.pathway_certainty = 'sure'
            fields.append('pathway_certainty')

    # Single-source-of-truth for a catalogue-linked programme's institution NAME: the recommender
    # CATALOGUE (course_id → Institution), not the offer letter — so OCR variants ("POLITEKNIK
    # SEBERANG PERAI (POLITEKNIK PREMIER)") are ironed out and the bursary can't disagree with the
    # recommender. Runs regardless of lock state; only the institution sub-key is touched.
    #
    # Two DIFFERENT jobs, deliberately split (they used to be one block, which is how the must-fill
    # ended up below the guards):
    #   • NORMALISING an institution already on file — display tidying, stays here;
    #   • FILLING a blank one — the must-fill, owned by sync_institution_from_catalogue() and called
    #     at the TOP of this function, above every guard.
    # The fill is attempted once more here because the `not locked` branch above may just have
    # written a fresh course_id, and a course's institution can only be resolved once it exists.
    cp_now = application.chosen_programme if isinstance(application.chosen_programme, dict) else {}
    cid_now = (cp_now.get('course_id') or '').strip()
    inst_now = (cp_now.get('institution') or '').strip()
    if cid_now and inst_now:
        canon_inst = op.catalogue_institution(cid_now, inst_now)
        if canon_inst and canon_inst != inst_now:
            application.chosen_programme = {**cp_now, 'institution': canon_inst}
            if 'chosen_programme' not in fields:
                fields.append('chosen_programme')
    elif cid_now:
        if sync_institution_from_catalogue(application, offer=offer, offer_check=chk):
            wrote_early = True    # it saved itself; don't re-add chosen_programme to `fields`

    # Neither the reporting date nor the must-fill institution is synced at the BOTTOM of this
    # function any more — sync_reporting_date_from_offer() and sync_institution_from_catalogue()
    # both run at the top, above the guards that used to skip them. See their docstrings.

    if not fields:
        return wrote_early
    application.save(update_fields=fields)
    return True


def revert_if_profile_incomplete(application):
    """Honest-funnel guard: if a ``profile_complete`` application is edited back
    into an incomplete state (e.g. the student deletes a compulsory document, or
    clears a required story field), roll the status back to ``shortlisted`` and
    clear ``profile_completed_at`` so the funnel never shows "complete" on an
    incomplete profile. Only touches ``profile_complete`` — interviewing /
    interviewed / accepted are the admin's to own. Returns True if it reverted.
    """
    if application.status != 'profile_complete':
        return False
    if application_completeness(application)['complete']:
        return False
    application.status = 'shortlisted'
    application.profile_completed_at = None
    # Back in the wizard: the frozen requirement set goes with the submission it belonged to.
    # The student now sees and is gated on the CURRENT configuration, and is re-frozen at
    # their next Submit. (A student can only reach here through their OWN edit — deleting a
    # compulsory document, blanking a required answer — never through a configuration change,
    # because the completeness check above read the frozen copy.)
    application.requirements_snapshot = None
    try:
        del application._requirements_memo
    except AttributeError:
        pass
    application.save(update_fields=['status', 'profile_completed_at', 'requirements_snapshot'])
    return True
