"""
Everything that can stop a case: identity, income, offer, red and unreadable docs.

Moved here VERBATIM from `apps/scholarship/services.py` at code health H15 (2026-09-20).
Moves only: not a line of this body was reworded. See `__init__.py`.
"""
from django.utils import timezone

from .. import requirements
from ..document_snapshot import latest_doc, live_docs, present_doc_types
from ..models import ApplicantDocument


# Vision errors that mean the FILE couldn't be decoded/fetched (a PDF/video/corrupt
# upload, or a storage-fetch glitch) — re-uploading a clear photo/scan fixes it.
# Distinct from a genuine OCR-SERVICE outage (quota/network/unconfigured), where
# re-uploading won't help. Drives the ic_unreadable vs ic_service_down split AND is
# excluded from the outage detector's service-failure count. (TD-080)
_IC_DECODE_ERROR_MARKERS = ('empty image', 'bad image data', 'could not fetch')


def is_ic_decode_error(err: str) -> bool:
    e = (err or '').lower()
    return any(m in e for m in _IC_DECODE_ERROR_MARKERS)


def ic_identity_blockers(application):
    """Identity gate on the student's OWN uploaded IC (doc_type='ic').

    The IC is OCR'd once at upload (run_vision_for_document, synchronous), so by
    consent time the vision_* fields are populated or carry an error. Returns the
    relevant blocker code(s):
      - 'ic_service_down'  : the OCR service errored (Vision down / quota / config)
                             → re-uploading won't help; tell the student to retry later.
      - 'ic_unreadable'    : OCR ran but couldn't read the IC (poor image) → re-upload.
      - 'ic_nric_mismatch' : the IC's NRIC doesn't match the profile NRIC.
      - 'ic_name_mismatch' : the IC's name is a different person's (disjoint tokens).
    A 'partial' name (one set a subset of the other — same person, shorter/longer
    form) is NOT blocked: the NRIC is the hard identity key. Empty profile NRIC/name
    are skipped (can't compare). Caller guarantees an 'ic' document exists.
    """
    from ..vision import nric_match, name_match
    ic = latest_doc(application, 'ic')
    if ic is None or not ic.vision_run_at:
        return ['ic_service_down']  # never processed — treat as a system issue
    if ic.vision_error:
        # A decode/fetch error ("Bad image data." from a PDF/video, "empty image",
        # "could not fetch") means the FILE is the problem → re-upload (ic_unreadable).
        # A genuine service error (module/API/network/quota) → retry later
        # (ic_service_down). Pre-TD-080 this lumped "Bad image data." into
        # service_down, stranding PDF-IC students with a false "system down".
        return ['ic_unreadable'] if is_ic_decode_error(ic.vision_error) else ['ic_service_down']
    if not (ic.vision_nric or ic.vision_name):
        return ['ic_unreadable']  # OCR succeeded but read nothing usable (poor image)
    out = []
    pnric = (getattr(application.profile, 'nric', '') or '').strip()
    pname = (getattr(application.profile, 'name', '') or '').strip()
    nric_verified = bool(ic.vision_nric and pnric and nric_match(ic.vision_nric, pnric))
    if ic.vision_nric and pnric and not nric_match(ic.vision_nric, pnric):
        out.append('ic_nric_mismatch')
    # Name is a SOFT cross-check. When the NRIC already verifies identity, a name
    # 'mismatch' is almost always an OCR name-extraction miss (the MyKad name line
    # read imperfectly) — NOT a different person — so it must not block consent;
    # the NRIC is the hard identity key. Only block on a name mismatch when the
    # NRIC did NOT verify (a genuine wrong-IC risk). The admin still sees the soft
    # name-mismatch chip either way.
    if not nric_verified and ic.vision_name and pname and name_match(ic.vision_name, pname) == 'mismatch':
        out.append('ic_name_mismatch')
    return out


def detect_vision_outage(window_hours=24):
    """Passive Google-Vision health signal from recent IC / parent_ic OCR outcomes.

    Returns ``(is_down, stats)``. ``is_down`` is True when there were OCR attempts
    in the window and EVERY one carried a service-level error with NOT ONE success
    — i.e. the OCR *service* (not a single blurry image) has been failing for
    everyone who tried. A poor image ('empty image' / read-nothing) is NOT counted
    as a service failure, so a run of bad uploads alone never trips the alert.

    Read-only; no Vision API calls (so the check itself costs nothing). Pair with a
    daily scheduled run so the admin is alerted once a day while an outage persists.
    """
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(hours=window_hours)
    docs = ApplicantDocument.objects.filter(
        doc_type__in=['ic', 'parent_ic'], vision_run_at__gte=cutoff,
    ).only('vision_error', 'vision_nric', 'vision_name')
    attempts = successes = service_failures = 0
    for d in docs:
        attempts += 1
        if not d.vision_error and (d.vision_nric or d.vision_name):
            successes += 1
        elif d.vision_error and not is_ic_decode_error(d.vision_error):
            service_failures += 1
    is_down = attempts >= 1 and successes == 0 and service_failures >= 1
    return is_down, {
        'window_hours': window_hours, 'attempts': attempts,
        'successes': successes, 'service_failures': service_failures,
    }


#: TD-151 (3), 2026-10-02 — the READ documents the submission gates and the verdict depend on, swept
#: like the IC when an upload's read never ran: the slip and offer (identity / academic / pathway
#: blockers), the income-cluster proofs (`member_income_evidenced`, `usable_salary_slip`) and the two
#: relationship documents. Stuck = BOTH run stamps NULL (`run_vision_match_for_document` always stamps
#: `vision_run_at`, field extraction `vision_fields_run_at`) AND `vision_fields` EMPTY — a document
#: that carries any stored read (one made before either stamp existed included) is never re-read by
#: the sweep, so nothing it holds can be overwritten (review F1) — and never a superseded one.
_SELF_HEAL_READ_TYPES = ('results_slip', 'offer_letter', 'salary_slip', 'epf', 'str',
                         'birth_certificate', 'guardianship_letter', 'income_support_doc')
#: Written on a row BEFORE the sweep reads it; a completed read overwrites it. Left on a row, it
#: means the process died mid-read — the sweep will not try again; an officer's Re-run can.
REPROCESS_ATTEMPTED = 'reprocess_attempted'


def _stuck_unread_documents(limit):
    from django.db.models import Q
    return list(ApplicantDocument.objects
                .filter(Q(doc_type__in=('ic', 'parent_ic'), vision_run_at__isnull=True)
                        | Q(doc_type__in=_SELF_HEAL_READ_TYPES, vision_run_at__isnull=True,
                            vision_fields_run_at__isnull=True, superseded_at__isnull=True,
                            vision_fields={}))
                .order_by('uploaded_at')[:limit])


def reprocess_unread_ic_documents(limit=200, dry_run=False):
    """Self-heal IC / parent_ic documents stuck UN-PROCESSED (``vision_run_at`` is NULL).

    ``run_vision_for_document`` never raises and ALWAYS stamps ``vision_run_at``, so a NULL
    means Vision was never run on the doc — a silent upload-time pipeline failure with no
    retry. That strands the student behind a false ``ic_service_down`` ("document-check
    service unavailable") consent block (``ic_identity_blockers`` line ~1170) and a "couldn't
    read the IC" cockpit verdict, even though the service is up. This re-runs Vision on every
    such doc — once each: after a run, ``vision_run_at`` is set, so it's never re-picked (cost
    is one Vision read per stuck doc). Defensive: if a run ever does raise, we stamp an outcome
    so it can't loop. Returns ``{scanned, processed, errored}``.

    TD-151 (3): the same sweep now covers the other read documents a submission gate depends on
    (``_SELF_HEAL_READ_TYPES``), re-read through ``reextract.reextract_document`` — the one
    dispatcher the cockpit's Re-run uses. ``dry_run`` counts what WOULD be re-read, per type, and
    reads nothing (``{scanned, by_type}``) — run it before the first deploy to size the backlog.
    """
    from ..vision import run_vision_for_document
    from ..reextract import reextract_document
    stuck = _stuck_unread_documents(limit)
    if dry_run:
        by_type = {}
        for doc in stuck:
            by_type[doc.doc_type] = by_type.get(doc.doc_type, 0) + 1
        return {'scanned': len(stuck), 'by_type': by_type}
    scanned = processed = errored = 0
    for doc in stuck:
        scanned += 1
        # STAMP BEFORE READING (2026-10-02). A memory kill is not an exception: one 2 MB PDF took
        # the instance past 2 GiB mid-read, nothing below ran, and the same row was re-picked every
        # hour. Only the two stamp/error columns — never `vision_fields` (F1 above).
        prior_error = doc.vision_error or ''
        doc.vision_error, doc.vision_run_at = REPROCESS_ATTEMPTED, timezone.now()
        doc.save(update_fields=['vision_error', 'vision_run_at'])
        try:
            if doc.doc_type in ('ic', 'parent_ic'):
                err = run_vision_for_document(doc).get('error')
            else:
                reextract_document(doc)
                err = None
            if doc.vision_error == REPROCESS_ATTEMPTED:   # a read that wrote no outcome of its own
                doc.vision_error = prior_error
                doc.save(update_fields=['vision_error'])
            err = err if err is not None else doc.vision_error
            errored += 1 if err else 0
            processed += 0 if err else 1
        except Exception:
            errored += 1
            if doc.vision_error in ('', REPROCESS_ATTEMPTED):
                doc.vision_error = 'reprocess_failed'
            doc.vision_run_at = timezone.now()
            doc.save(update_fields=['vision_error', 'vision_run_at'])
    return {'scanned': scanned, 'processed': processed, 'errored': errored}


def income_doc_blockers(application):
    """The route + selection aware COMPULSORY income documents still missing, as blocker
    codes (gate v2, 2026-06-05). Sourced from ``income_engine`` so the consent gate and
    the student's wizard checklist can never disagree (one source of truth).
      - blank route / no earner-or-member chosen → ``income_incomplete`` (walk the wizard);
      - STR route → STR doc + the earner IC + relationship doc (mother→BC, guardian→letter);
      - salary route → for EVERY selected member: their IC + income shown any one way
        (payslip / EPF / declared+letter / STR — ``member_income_evidenced``) + the relationship doc.
    The per-PERSON codes are member-qualified — ``parent_ic_missing:<member>`` and
    ``income_evidence_missing:<member>`` (member = father/mother/guardian/brother/sister) — so
    the consent checklist names each person ("Upload Father's IC"). The frontend splits on
    ``:`` and renders the member name; the household relationship docs (BC / guardianship
    letter) stay un-suffixed. The POST gate only cares that the list is non-empty.
    """
    from ..income_engine import (working_members, relationship_doc_for,
                                _member_ic_doc, _cluster_docs, str_not_breached,
                                salary_income_satisfied, usable_salary_slip,
                                member_income_evidenced, household_str_status)
    # ⚠ LAYER 0 TOUCHES THIS FUNCTION IN EXACTLY ONE PLACE: whether it runs at all.
    #
    # Everything below is the income ROUTE ENGINE — STR versus salary, per-member evidence,
    # relationship documents, the either-route-satisfies rules. None of it is configurable and
    # none of it may become configurable: letting an organisation switch off "the father's IC"
    # while leaving "his payslip" on would produce an assessment nobody designed. So the catalogue
    # offers ONE item, `income_proof`, and it means "run this engine, or don't".
    if not requirements.asks_for(application, 'document', 'income_proof'):
        return []
    route = (getattr(application, 'income_route', '') or '').strip()
    if not route:
        return ['income_incomplete']
    # ⚠ F8 — ONLY THE FAMILY'S OWN STR COUNTS (owner 2026-09-19, `docs/decisions.md`). Every STR
    # arm below runs through `str_not_breached`, which asks whether the household's STR has FAILED
    # and never WHOSE it is, so a stranger's letter used to clear this gate. The ownership test is
    # applied here rather than inside that predicate because it also feeds the verdict — see
    # `income_str_ownership`, which also documents why an UNREAD STR is not a stranger's one.
    # TD-285 F1 (2026-09-29): only a TRUE stranger blocks; an STR we cannot judge counts here and
    # its missing IC is asked after submission (see `stranger_str_blocks_submission`).
    from ..income_str_ownership import STR_NOT_HOUSEHOLD, stranger_str_blocks_submission
    strangers_str = stranger_str_blocks_submission(application)
    present = present_doc_types(application)
    out = []
    if route == 'str':
        # EITHER route satisfies (owner 2026-07-22): a fully documented earner settles income on
        # its own, so don't go on to demand the STR triplet from a student whose STR is missing or
        # failed the format gate. Mirrors the salary branch's identical early-return below.
        # (`salary_income_satisfied` reads the un-tightened STR arm, so a stranger's STR could
        # satisfy it — hence the F8 guard on both of its call sites in this function.)
        if not strangers_str and salary_income_satisfied(application):
            return []
        earner = (getattr(application, 'income_earner', '') or '').strip()
        if not earner:
            return ['income_incomplete']
        # Order: STR doc first (the primary income proof), then the earner IC, then the
        # relationship doc — matches the Documents-UI DISPLAY_ORDER (str before parent_ic).
        if 'str' not in present:
            out.append('str_missing')
        elif strangers_str:
            out.append(STR_NOT_HOUSEHOLD)      # present, but it belongs to somebody else
        if _member_ic_doc(application, earner) is None:
            out.append(f'parent_ic_missing:{earner}')   # names the single STR earner
        rel = relationship_doc_for(earner)          # birth_certificate / guardianship_letter / ''
        if rel and rel not in present:
            out.append(f'{rel}_missing')            # birth_certificate_missing / guardianship_letter_missing
        return out
    # Salary route. A dispositive STR settles income on EITHER route (household_str_status is the
    # government means-test, matched to a household member), so honour it here exactly as the STR
    # branch above honours a complete salary cluster. Without this, a genuinely-STR student who
    # picked 'salary' was trapped behind salary-route demands (a ticked worker + that member's IC)
    # their STR should have cleared — and the consent-time route reconcile could never rescue them,
    # because they'd never reach consent. Route-symmetry: either evidence clears either route.
    if household_str_status(application)[0] is not None:
        return []
    # ONE complete, clean earner cluster is enough to submit (owner 2026-07-08).
    members = working_members(application)
    if not members:
        return ['income_incomplete']
    # If any selected member's cluster is complete + coherent, the income requirement is met and
    # every OTHER member's gaps become soft Check-2 follow-ups — so a family that has fully
    # documented one earner is never trapped over a second earner's missing/partial docs.
    if not strangers_str and salary_income_satisfied(application):
        return []
    if strangers_str:
        # F8. Nothing else in this household shows what it earns (`stranger_str_blocks_submission`
        # checked), so the STR is carrying the gate and it is not this family's.
        out.append(STR_NOT_HOUSEHOLD)
    # No cluster complete yet — list what's still needed so the student can finish at least one.
    # Income is shown ANY ONE way (owner 2026-07-25): a payslip, an EPF statement, a declared amount
    # backed by a supporting letter, OR a non-breached household STR (means-test, P3). So a cash /
    # informal earner (an e-hailing father, or Janani's mother with a ketua-kampung letter) is never
    # trapped behind a salary slip they can't produce. `member_income_evidenced` is the single source,
    # shared with `member_cluster_complete`, so the gate and the wizard agree. IC + relationship docs
    # stay required (identity/link).
    need_bc = need_guard = False
    for m in members:
        # Member-qualified codes so the checklist names each person — IC then income evidence,
        # grouped per member to match the Documents-UI member blocks.
        if _member_ic_doc(application, m) is None:
            out.append(f'parent_ic_missing:{m}')
        if not member_income_evidenced(application, m):
            out.append(f'income_evidence_missing:{m}')
        rel = relationship_doc_for(m)
        if rel == 'birth_certificate' and 'birth_certificate' not in present:
            need_bc = True
        elif rel == 'guardianship_letter' and 'guardianship_letter' not in present:
            need_guard = True
    if need_bc:
        out.append('birth_certificate_missing')
    if need_guard:
        out.append('guardianship_letter_missing')
    return out


def _offer_blocks(application):
    """Whether the offer should BLOCK submission. Blocks only when the offer is judged NOT-official
    (``offer_official_status == 'not_genuine'``) AND the four-fact PATHWAY VERDICT is NOT "blue and
    above". Owner 2026-07-08: we accept Probable/Certain — so a cropped-official offer the
    reporting-date bonus / genuineness ladder legitimately lifts to Certain is allowed even though
    ``offer_official_status`` still reads not_genuine (#56 tiled Certain yet was blocked). An offer
    that is missing / official / UNKNOWN (not yet genuineness-scored) still never blocks — we don't
    gate on our own gap (unchanged).

    STPM route (owner 2026-07-20): a Form-Six student has no university-style offer letter — their
    pathway proof is school enrolment (a *Surat Pengesahan Pelajar*), which the offer-genuineness
    model isn't trained to recognise, so it reads not_genuine and the pathway sits red. We never bar
    an STPM student at the submission door on that gap: the reviewer audits the pathway by hand (the
    verdict may legitimately stay red). Presence is still required (`offer_letter_missing` — they must
    upload *something*); only the genuineness block is lifted, and only for STPM. Other routes —
    incl. Matriculation, which DOES get a recognisable official offer — are unaffected."""
    # Layer 0: a programme that does not ask for an offer letter cannot be blocked by one.
    # This is the ORGANISATION's setting; the STPM exemption immediately below is a per-STUDENT
    # rule and is untouched — the two are different questions and stay separate.
    if not requirements.asks_for(application, 'document', 'offer_letter'):
        return False
    if (getattr(application, 'chosen_pathway', '') or '').strip().lower() == 'stpm':
        return False
    from ..pathway_engine import offer_official_status
    offer = latest_doc(application, 'offer_letter')
    if offer is None or offer_official_status(offer) != 'not_genuine':
        return False                       # missing / official / unknown → not a block
    # A not-official offer blocks UNLESS the pathway verdict the officer sees is Probable+.
    from ..verdict_engine import build_verdict
    from ..verdict_narrative import _fact_band
    for fact in build_verdict(application):
        if fact.get('fact') == 'pathway':
            return _fact_band(fact) not in ('Certain', 'Probable')
    return True


# The income-CLUSTER document types — the ones the "one clean cluster is enough" rule can turn
# into soft Check-2 items once a different earner is fully documented. The student's own IC and the
# identity/academic/pathway docs (ic / results_slip / offer_letter) are NOT here — they always gate.
#
# ⚠ THE RELATIONSHIP DOCUMENTS ARE DELIBERATELY NOT IN THIS LIST (BrightPath #23, owner 2026-09-08).
# `birth_certificate` and `guardianship_letter` sat here until today, so proving the household's
# income switched OFF the question "is this really her mother?" — a DIFFERENT question, answered by
# a different document, that only happens to travel in the same cluster. That is how application 144
# submitted with a certificate nobody had checked. "One clean cluster is enough" is a rule about
# income EVIDENCE: an extraneous or misread income proof must not trap a family whose income is
# already established (#19, #28). It was never a rule about who somebody's parent is.
#
# Measured on production before it shipped: of the seven live applications, exactly ONE was newly
# stopped, and it was the owner's own test account (16), whose certificate names a different child.
# Zero real students moved. Across all 62 certificates on file there are three red rows — one
# genuinely wrong document, one the IC-number chain already rescues, and that test account.
_INCOME_CLUSTER_DOC_TYPES = ('parent_ic', 'salary_slip', 'epf', 'str')


def document_red_blockers(application):
    """Every RED ('Doesn't match' / rejected / stale) per-document check that must
    clear before consent. Reads the SAME stored verification the student sees in the
    Documents tab (the student_*_check engines — no new OCR). Only a CONFIRMED
    `mismatch` (or STR rejected/stale) blocks; 'pending' / 'unreadable' / 'no_ref' do
    not. IC identity reds are covered separately by ic_identity_blockers. Utility
    bills (soft hardship signal) are deliberately NOT gated. Returns blocker codes."""
    from .. import income_engine
    from ..academic_engine import student_slip_check
    from ..pathway_engine import student_offer_check
    from ..doc_red_keys import person_red     # the person-red keys' one home (TD-110)
    codes = set()
    # #4 (2026-06-11): a person-mismatch on an income PROOF only hard-blocks when that proof is
    # COMPULSORY for the chosen route — i.e. a salary-route salary slip tagged to a SELECTED
    # working member. An optional/extraneous proof must NOT trap the student at submission: the
    # STR route (where the STR itself is the income proof), EPF (which never substitutes the
    # slip), or a non-selected member — e.g. the father's payslip dropped onto a mother-STR
    # cluster. The cluster coach nudges its removal instead. (Was: ANY mismatched salary_slip /
    # epf blocked, trapping a student over a document they did not even need.)
    route = (getattr(application, 'income_route', '') or '').strip()
    selected_members = set(income_engine.working_members(application)) if route == 'salary' else set()
    # "Income already established -> other income-doc errors are soft" (owner 2026-07-08), on BOTH
    # routes: a complete salary cluster OR a valid dispositive household STR. Once income is
    # established, every OTHER income-document error -- an extraneous misread second-parent IC on a
    # clean salary cluster (#19), or the OTHER parent's IC cross-checked against a single-recipient
    # STR and 'mismatching' meaninglessly (#28) -- becomes a soft Check-2 follow-up, not a
    # submission blocker. The student's OWN identity/academic/pathway reds (results_slip /
    # offer_letter) still always block -- they're not income-cluster docs.
    income_ok = income_engine.income_established(application)

    for doc in live_docs(application):
        dt = doc.doc_type
        if income_ok and dt in _INCOME_CLUSTER_DOC_TYPES:
            continue
        if dt == 'results_slip':
            chk = student_slip_check(doc)
            if chk.get('name') == 'mismatch':
                codes.add('results_slip_name_mismatch')      # identity red -> still hard-blocks
            # A GRADE / subject mismatch is NO LONGER a hard submission block (owner 2026-07-08):
            # the slip is the authoritative record and the officer sees the exact discrepancy in
            # the cockpit (the slip-check chip), so it is reconciled at review / interview rather
            # than walling the student out of submitting -- a student who simply under-typed a
            # grade (#48: typed G, slip E) must not be trapped. The student's coach still names
            # the diff and links to the grades page so they can correct it if they wish.
        elif dt == 'offer_letter':
            # Name / IC are hard identity reds; the pathway-clash is a SOFT "is this
            # where you're going?" signal and is deliberately not gated here.
            if person_red(dt, student_offer_check(doc)):
                codes.add('offer_letter_mismatch')
        elif dt == 'parent_ic':
            chk = income_engine.student_income_ic_check(doc)
            if person_red(dt, chk):
                codes.add('parent_ic_person_mismatch')
        elif dt == 'salary_slip':
            # Only a COMPULSORY salary slip (salary route + a SELECTED working member) blocks on a
            # person-mismatch — an optional/extraneous slip must not (see the note above).
            compulsory = route == 'salary' and (doc.household_member or '') in selected_members
            if compulsory and person_red(dt, income_engine.student_income_proof_check(doc)):
                codes.add('salary_slip_person_mismatch')
        elif dt == 'epf':
            pass  # EPF is supplementary on BOTH routes (never substitutes the salary slip), so a
                  # person-mismatch on it never blocks submission — the cluster coach handles it.
        elif dt == 'str':
            chk = income_engine.student_str_check(doc)
            if person_red(dt, chk) or chk.get('current_status') in income_engine.STR_RED_STATES:
                codes.add('str_person_mismatch')
        elif dt == 'birth_certificate':
            # ⚠ THE FATHER ROW IS DELIBERATELY NOT A BLOCKER (BrightPath #23, owner 2026-09-08).
            # It compares the certificate's father against the patronymic in the STUDENT'S own
            # name — a father may legitimately have no Malaysian IC (Lina's has none), and a
            # foreign or absent father must never be what stops a student submitting. The row is
            # still READ and still shown to the officer; it just does not hold the door.
            if person_red(dt, income_engine.student_bc_check(doc)):
                codes.add('birth_cert_person_mismatch')
        elif dt == 'guardianship_letter':
            if person_red(dt, income_engine.student_guardianship_check(doc)):
                codes.add('guardianship_person_mismatch')
    return list(codes)


def document_unreadable_blockers(application):
    """Compulsory documents that were uploaded but are UNREADABLE — a bad/blurry/skewed
    photo the student can simply re-take (Gopal already says exactly this). Owner policy:
    don't accept what we can't verify. EXCLUDES our own OCR-service outages: the Gemini
    docs (slip/offer/relationship) surface an outage as 'pending' (not processed), not
    'unreadable'; the Vision IC path is guarded with is_ic_decode_error (a service error
    is not the student's fault). Returns blocker codes."""
    from ..academic_engine import student_slip_check
    from ..pathway_engine import student_offer_check
    from ..income_engine import (income_cluster_advice, effective_working_members,
                                _member_ic_doc, student_income_ic_check)
    codes = set()
    slip = latest_doc(application, 'results_slip')
    if slip and student_slip_check(slip).get('name') == 'unreadable':
        codes.add('results_slip_unreadable')
    offer = latest_doc(application, 'offer_letter')
    if offer and student_offer_check(offer).get('name') == 'unreadable':
        codes.add('offer_letter_unreadable')
    # Income cluster — per earner.
    route = (getattr(application, 'income_route', '') or '').strip()
    if route == 'str':
        earner = (getattr(application, 'income_earner', '') or '').strip()
        members = [earner] if earner else []
    elif route == 'salary':
        # NB: pass the application (effective_working_members reads it) — an earlier version
        # passed the income_working_members LIST, which always resolved to [] (the loop never
        # ran → an unreadable salary-route earner IC/relationship doc was never gated). Using
        # effective_working_members also picks up the #90 tagged-docs/roster fallback.
        members = effective_working_members(application)
    else:
        members = []
    for member in members:
        ic = _member_ic_doc(application, member)
        if ic is not None:
            ran = bool(getattr(ic, 'vision_run_at', None))
            err = getattr(ic, 'vision_error', '') or ''
            service_down = bool(err) and not is_ic_decode_error(err)   # OUR outage → don't block
            if ran and not service_down and not student_income_ic_check(ic).get('readable'):
                codes.add('income_document_unreadable')
        # The relationship doc (BC / guardianship letter) is a Gemini field-extraction doc,
        # so an outage shows as 'pending' — only a genuine bad scan returns this code.
        if income_cluster_advice(application, member) == 'income_rel_doc_unreadable':
            codes.add('income_document_unreadable')
    return list(codes)
