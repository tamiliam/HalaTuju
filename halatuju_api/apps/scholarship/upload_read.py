"""The upload's READ, run after the upload is recorded (A2.3, TD-519).

Before A2.3, ``DocumentListCreateView.post`` ran the paid read (Vision OCR, Gemini field extraction)
and the promote decision INSIDE the upload request: p95 about 27 s, so a phone on a weak line often
gave up before the answer came. Now the request only records the document (``queue_plan``, written
in the same insert) and answers at once with ``reading: true``. The read then runs in one of two
places, through the SAME function (``run_read``):

* **at once**, when the web asks for it (``POST documents/<id>/read/``, sent straight after the
  upload) — so the student still sees her result in the time the read takes, as before;
* **within 15 minutes**, from the ``read-documents`` cron (``run_pending_reads``), for any read
  nobody asked for (the phone dropped, the tab closed, an old web build).

``read_and_judge`` is the request's old body, MOVED VERBATIM from ``views.py``: the HEIC fix, the
reads, the tag guard, JUDGE → PROMOTE, the dedupe, the resolution sync, the offer autofill and the
re-ask notes. What a read decides is unchanged, so ``MODEL_VERSION`` is unchanged. The rules here,
each pinned in ``tests/test_upload_read.py``:

* **Claim before the paid call.** A conditional UPDATE claims the row and counts the attempt, so the
  web's call and the cron never read the same document twice. A claim older than ``STALE_CLAIM`` (a
  process killed mid-read) is claimable again; after ``MAX_ATTEMPTS`` the row is 'failed'.
* **A decided newer upload wins.** A read that starts after a NEWER upload in the same slot has
  already been read and judged is dropped unread (no paid call): that newer decision stands, and an
  older read finishing last must never bury it. (A newer one still waiting is simply read after.)
* **Judged against the slot as it is now.** The read compares with the slot's current live copy
  (an earlier upload read in between may now hold it), not the one the upload saw; the plan's copy
  is used only when the slot is empty.
* **No read, no wait.** A document type with no paid read (a photo, a reference letter) is judged
  inside the request exactly as before — there is nothing slow to move.
"""
import logging
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from .document_snapshot import SNAPSHOT_ORDER
from .models import ApplicantDocument

logger = logging.getLogger(__name__)

PENDING = 'pending'
FAILED = 'failed'
MAX_ATTEMPTS = 3
STALE_CLAIM = timedelta(minutes=10)
#: Per cron run. A read takes up to about 30 s and the cron endpoint has 300 s.
BATCH = 6


def needs_read(doc_type):
    """True for the document types the upload sends to a paid read (the three branches of
    ``read_and_judge``). Every other type is judged inside the request, as before."""
    from .views import SUPPORTING_NAME_CHECK_TYPES, TEXT_READ_DOC_TYPES
    return (doc_type in ('ic', 'parent_ic') or doc_type in SUPPORTING_NAME_CHECK_TYPES
            or doc_type in TEXT_READ_DOC_TYPES)


def queue_plan(staged, stale_ids, existing_live):
    """The columns the upload writes with the row so the read can be run later. ``stale_ids`` is
    the SAME list the slot write extends on a clash, so the plan holds what the insert saw."""
    return {'read_state': PENDING, 'read_plan': {
        'staged': bool(staged), 'stale_ids': stale_ids,
        'existing_live': existing_live.id if existing_live is not None else None}}


def pending_payload(doc):
    """The upload's answer while the read is still to run: the row, and 'pending' for the verdict
    (the Action Centre's existing "still checking" state)."""
    from .serializers import ApplicantDocumentSerializer
    data = ApplicantDocumentSerializer(doc).data
    data['match_verdict'] = 'pending'
    data['kept_previous'] = False
    data['reading'] = True
    return data


def read_and_judge(app, doc, *, staged, stale_ids, existing_live):
    """Read ``doc`` and decide its slot. Returns the upload's response body. MOVED VERBATIM from
    ``DocumentListCreateView.post`` (A2.3); only ``self.`` became the view class and the module
    helpers gained their ``views.`` prefix."""
    from django.conf import settings as _settings
    from . import slot_writes
    from .serializers import ApplicantDocumentSerializer
    from .views import (BILL_DOC_TYPES, SUPPORTING_NAME_CHECK_TYPES, TEXT_READ_DOC_TYPES,
                        _ACADEMIC_SINGLE_TYPES, DocumentListCreateView, _collapse_duplicate_docs,
                        _flag_needs_officer_eye, _note_unresolved_attempts, _reslot_income_doc,
                        _stage_attempts_exhausted)
    # iPhone HEIC → JPEG, in place, BEFORE any Vision/extraction — so OCR can read it and the
    # cockpit viewer / download URL serve a browser-renderable image (soft; no-op otherwise).
    from .imaging import convert_heic_to_jpeg
    convert_heic_to_jpeg(doc)
    # S13 + S17: auto-run Vision OCR on IC uploads (student's IC OR the
    # parent/guardian IC for minor consent). Soft signal — never blocks.
    if doc.doc_type in ('ic', 'parent_ic'):
        from .vision import run_vision_for_document
        run_vision_for_document(doc)
    # Supporting docs: OCR once, then (a) the free name/address presence check
    # and (b) automatic Gemini field-extraction with student feedback. Soft,
    # never blocks. Gemini is guardrailed by the hourly per-application cap.
    elif doc.doc_type in SUPPORTING_NAME_CHECK_TYPES:
        from . import vision as _vision
        profile = app.profile
        names = _vision.reference_names(app)   # student + guardians + roster parents (#126)
        postcode = getattr(profile, 'postal_code', '') or ''
        city = getattr(profile, 'city', '') or ''
        street = getattr(profile, 'address', '') or ''   # #3: street line for the bill fallback
        check_address = doc.doc_type in BILL_DOC_TYPES
        ocr = _vision.ocr_document_full(doc)   # ONE fetch + ONE Vision call, shared by every consumer
        # RE-SLOT an EPF that arrived in the salary-slip slot (owner, 2026-07-14).
        #
        # The income-proof request says "his latest salary slip OR EPF (KWSP) statement", but it
        # has ONE slot — `salary_slip` — and the Action Centre uploads into whatever the item's
        # doc_type says. So an EPF landed in the payslip slot, scored `not_salary` ("no
        # recognisable payslip fields"), failed usable_salary_slip(), never cleared the request,
        # and looped the student into the circuit-breaker. We would have been inviting a document
        # and then refusing it — the #126 trap again, this time written into our own copy.
        #
        # The engine already accepts EITHER doc as income evidence (_parent_has_income_evidence
        # checks salary_slip OR epf). The ONLY broken link was the slot. So: file it where it
        # belongs, keep the member tag, and everything downstream resolves itself.
        _resloted = _reslot_income_doc(doc, ocr)
        if _resloted:
            check_address = doc.doc_type in BILL_DOC_TYPES
        match = _vision.run_vision_match_for_document(
            doc, names=names, postcode=postcode, city=city, street=street,
            check_address=check_address, ocr=ocr)
        if doc.doc_type in _vision.GEMINI_EXTRACT_DOC_TYPES:
            # force=True: this is the ONE document the student just uploaded in
            # response to a request — always read it now, even if the hourly
            # doc-assist cap is hit. A deferred read here is exactly what let an
            # unscanned re-upload greenlight its task (see resolution.doc_match_verdict).
            DocumentListCreateView._maybe_extract_fields(
                app, doc, _vision, ocr, names, postcode, city, street,
                check_address, match, _settings, force=True)
    # P1 (Check 2): the letter of intent — OCR its plain text so the submission
    # review can read motivation. No matching/extraction, just the text. Soft.
    elif doc.doc_type in TEXT_READ_DOC_TYPES:
        from . import vision as _vision
        _vision.read_text_document(doc)
    # ── Tag guard (the airtight last line): attribute an income doc (parent_ic / salary_slip /
    # epf / str) to the household member by the NAME now read off it (Vision/Gemini has run above),
    # in two cases:
    #   (a) FILL a blank tag — a memberless request (income_doc_stale), a reviewer mis-classify,
    #       a direct/legacy client left it untagged (lenient: first roster name-match wins).
    #   (b) CORRECT a tag the NAME contradicts — the #80/#112 class, where a pre-consent STR-route
    #       force-tag stamped the father's payslip onto the mother. Strict: only when the name
    #       matches EXACTLY ONE member who isn't the current tag (see income_engine.name_contradicts_tag).
    # STR is included so a salary-route STR (recipient may differ from the declared income_earner —
    # #45) or a mis-selected STR-route STR files under its actual RECIPIENT (matched on recipient_name),
    # keeping the docs box in step with the verdict's own recipient match.
    # Either way the doc is never PERSISTED under the wrong person where the name is determinable;
    # the verdict then reads it under the right member. A genuinely-unresolvable name leaves the
    # tag untouched (the cockpit catch-all still shows a blank — never hidden).
    if doc.doc_type in ('parent_ic', 'salary_slip', 'epf', 'str'):
        from .income_engine import (resolved_member_for, name_contradicts_tag,
                                    implied_single_member)
        has_tag = bool((doc.household_member or '').strip())
        # (c) LAST RESORT, blank tag only — the name could not be read at all, but the household
        #     admits exactly one candidate (the STR route's declared earner), so the document
        #     cannot belong to anyone else. BrightPath #20: WITHOUT this, an unreadable untagged
        #     income doc keeps its blank tag, and a blank tag is a slot of its own — permanently
        #     empty, so the doc wins it by default and sits in the live documents beside the good
        #     copy it was meant to replace. The worst-read documents were the ones that lingered.
        #     Deliberately last: a readable name always decides first, and the salary route (where
        #     several members may each hold documents) returns '' and leaves the blank alone.
        #     Safe by construction — the re-tagged doc still goes through STAGE → JUDGE → PROMOTE
        #     below, and an unreadable doc is not `usable`, so it can only land in Replaced.
        derived = (name_contradicts_tag(app, doc) if has_tag
                   else (resolved_member_for(app, doc) or implied_single_member(app)))
        if derived and derived != (doc.household_member or '').strip():
            doc.household_member = derived
            doc.save(update_fields=['household_member'])
            # The create-time replace ran with the OLD (blank or wrong) member and couldn't match
            # this person's slot, so now that the correct member is known, supersede any prior live
            # copy in the (doc_type, member, request_code) slot — the re-attributed doc REPLACES
            # that member's existing doc instead of duplicating it. Retained as history (Phase 2),
            # never hard-deleted.
            prior = list(ApplicantDocument.objects.filter(
                application=app, doc_type=doc.doc_type, household_member=derived,
                request_code=doc.request_code, superseded_at__isnull=True,
            ).exclude(id=doc.id).values_list('id', flat=True))
            if staged:
                # The member changed → the promote decision must also supersede the DERIVED
                # member's live slot (e.g. a mother-tagged STR replacing a blank-tagged legacy
                # copy). Fold it into the staged-against set + recompute the doc to protect.
                stale_ids = list(dict.fromkeys(list(stale_ids) + list(prior)))
                existing_live = (ApplicantDocument.objects.filter(
                    id__in=stale_ids, superseded_at__isnull=True).exclude(id=doc.id)
                    .order_by(*SNAPSHOT_ORDER).first())
            elif prior:
                from django.utils import timezone as _tz2
                ApplicantDocument.objects.filter(id__in=prior).update(
                    superseded_at=_tz2.now(), superseded_by=doc)
    # JUDGE → PROMOTE (owner 2026-07-09): the staged doc has now been read. Decide whether it takes
    # the prime slot. USABLE = doc_match_verdict 'ok' (not-fake ∧ right-type ∧ readable ∧ right-
    # person); promote iff it is at least as good as the existing live doc (promotion.should_promote
    # — quality is str_proof_quality for STR, else a readable+genuine+recency proxy). Otherwise it
    # stays staged (Old / Replaced) and the existing proof KEEPS its slot — a worse/wrong re-upload
    # can never bury a good live doc. This generalises the former STR-only keep-better swap-back to
    # EVERY key type; the four TestStrKeepBetterGuard cases are now instances of it:
    #   * #83 junk wrong_type re-upload → not usable → kept out;  * a real Ditolak (quality None)
    #     → news → replaces;  * #30 Lulus dashboard (3,1) vs Lulus Semakan (3,2) → kept;  * #112 a
    #     newer Lulus dashboard over a weaker semakan → currency dominates → replaces.
    kept_previous = False
    if staged:
        from . import promotion, wrong_slip as _ws   # S4: a higher result never displaces an SPM slip
        from .resolution import doc_match_verdict
        # USABLE = the read did not CONFIRM a problem: 'ok' (clean) or 'pending' (not scanned yet —
        # newest still wins, the task stays open, and the quality proxy keeps a pending doc from
        # burying an 'ok' one). Only a CONFIRMED 'mismatch'/'unreadable' is not-usable → stays
        # staged so a wrong/blurry re-upload can't displace a good live proof.
        usable = doc_match_verdict(doc) not in ('mismatch', 'unreadable') and _ws.fills_spm_slot(doc)
        if promotion.should_promote(doc, existing_live, usable=usable):
            # Promote: supersede everything this upload replaces — the staged-against set (the
            # slot sweep, incl. any blank-tagged legacy copy) PLUS any other live copy in this
            # doc's exact slot — then unstage this one into the prime slot.
            # One transaction; a clash with a concurrent live copy keeps that copy (TD-115).
            if not slot_writes.promote_into_slot(app, doc, stale_ids):
                # A clash: another copy went live in this slot first. Only an OLDER live copy
                # means "we kept your previous one"; a NEWER one is usually the student's own
                # double tap, so no kept_previous (the newest upload is live, nothing was refused).
                kept_previous = ApplicantDocument.objects.filter(
                    application=app, doc_type=doc.doc_type, household_member=doc.household_member,
                    request_code=doc.request_code, superseded_at__isnull=True, id__lt=doc.id).exists()
            doc.refresh_from_db()
        else:
            kept_previous = True
            # Circuit-breaker: don't trap a student forever on an unsatisfiable read. After K
            # not-usable attempts, flag the open request for the officer (the existing best doc
            # stays live — a HOLD for human review, never an auto-resolve).
            if _stage_attempts_exhausted(app, doc, _settings):
                _flag_needs_officer_eye(app, doc)
    # copies of THIS doc-type to the single newest (newest pay month / latest-dated STR); the
    # rest drop to Old / Replaced (retained). Runs after the tag guard so the member is final.
    from . import income_engine as _ie
    if doc.doc_type in _ie._DEDUP_DOC_TYPES:
        _ie.dedupe_income_proof(app, (doc.household_member or '').strip(), doc.doc_type)
    # Academic single-per-person docs: an officer can request the same cert/slip twice, each
    # request opening its own slot → two live copies survive the slot-scoped supersede. Collapse
    # to the single best live copy across request codes (owner 2026-07-15, app #66).
    elif doc.doc_type in _ACADEMIC_SINGLE_TYPES:
        _collapse_duplicate_docs(app, doc.doc_type, (doc.household_member or '').strip())
    # S3: a new upload may clear a verdict gap → auto-resolve its ticket
    # (and link the doc), or surface a fresh ticket. Idempotent, never blocks.
    from .resolution import sync_resolution_items, resolve_doc_items_for_upload
    sync_resolution_items(app)
    # A verified offer letter silently settles a pathway the student hadn't locked
    # (undecided→decided) — no query; mirrors the apply form's storage shapes. A
    # genuine clash with a specific declared pick is left for the pathway_confirm
    # query. Soft + best-effort: never let it break the upload response.
    if doc.doc_type == 'offer_letter':
        try:
            from .services import autofill_pathway_from_offer
            autofill_pathway_from_offer(app)
        except Exception:
            logging.getLogger(__name__).warning(
                'autofill_pathway_from_offer failed for app %s', app.id, exc_info=True)
    # Action Centre (post-submit): a clean upload also clears its OFFICER doc task,
    # and the returned verdict tells the frontend whether to surface Cikgu Gopal's
    # advice (mismatch/unreadable) or treat the task as done (ok).
    match_verdict = resolve_doc_items_for_upload(app, doc)
    # Human-aware re-ask (#83, owner 2026-07-08): students routinely re-send the SAME file, or a
    # different-but-still-wrong one, without following the request's instruction. When this
    # upload leaves its doc-request OPEN, stamp the attempt on the item so the Action Centre
    # acknowledges what happened ("you re-sent the same document" / "we received it, but it
    # isn't what we asked for") instead of repeating the original copy as if nothing arrived.
    _note_unresolved_attempts(app, doc, stale_ids, kept_previous)
    data = ApplicantDocumentSerializer(doc).data
    data['match_verdict'] = match_verdict
    # The STR keep-better guard fired: the previous (better) proof stays live; this upload is
    # stored as history. The FE may surface this immediately; the Action Centre note persists.
    data['kept_previous'] = kept_previous
    return data


# ── The queue ────────────────────────────────────────────────────────────────

def _read_claimable(now):
    return Q(read_claimed_at__isnull=True) | Q(read_claimed_at__lt=now - STALE_CLAIM)


def _claim_read(doc_id, now):
    """Atomically claim one pending row and count the attempt. True iff this caller won it."""
    return ApplicantDocument.objects.filter(
        _read_claimable(now), pk=doc_id, read_state=PENDING, read_attempts__lt=MAX_ATTEMPTS,
    ).update(read_claimed_at=now, read_attempts=F('read_attempts') + 1) == 1


def _finish_read(doc_id, token, state=''):
    """Close the claim: '' (done) or FAILED. Only the claim holder's token closes it."""
    ApplicantDocument.objects.filter(pk=doc_id, read_claimed_at=token).update(
        read_state=state, read_claimed_at=None)


def _newer_upload_decided(doc):
    """A NEWER upload in this slot whose read has already finished. Its decision stands: reading
    this older one now could promote it over the newer (``promote_into_slot`` supersedes every other
    live copy in the slot). A newer one still waiting is read AFTER this one, as inline uploads were."""
    return ApplicantDocument.objects.filter(
        application_id=doc.application_id, doc_type=doc.doc_type,
        household_member=doc.household_member, request_code=doc.request_code,
        id__gt=doc.id).exclude(read_state=PENDING).exists()


def run_read(doc_id):
    """Claim, read, judge. Returns ``(outcome, data)``: outcome 'done', 'retry', 'failed',
    'superseded' or 'not_claimed'; ``data`` is the upload's response body on 'done', else None."""
    now = timezone.now()
    if not _claim_read(doc_id, now):
        return 'not_claimed', None
    doc = ApplicantDocument.objects.select_related('application').get(pk=doc_id)
    if _newer_upload_decided(doc):
        _finish_read(doc_id, now)
        logger.info('AUDIT upload_read_superseded doc=%s app=%s', doc_id, doc.application_id)
        return 'superseded', None
    plan = doc.read_plan or {}
    stale_ids = list(plan.get('stale_ids') or [])
    existing_live = None
    if plan.get('staged'):
        # Judge against the slot AS IT IS NOW, not as the upload saw it: an earlier upload read
        # since (or a copy that replaced the plan's) may hold the slot, and should_promote(.., None)
        # always promotes, so a stale "nothing" would let a mismatch bury a good live copy. The
        # slot's live copies join the staged-against set; the pick is the tag guard's own
        # (SNAPSHOT_ORDER over that set).
        # An empty slot is judged against nothing: the plan's copy was moved out or deleted.
        live_now = ApplicantDocument.objects.filter(
            application_id=doc.application_id, doc_type=doc.doc_type,
            household_member=doc.household_member, request_code=doc.request_code,
            superseded_at__isnull=True).exclude(id=doc.id).values_list('id', flat=True)
        stale_ids = list(dict.fromkeys(stale_ids + list(live_now)))
        existing_live = (ApplicantDocument.objects.filter(
            id__in=stale_ids, superseded_at__isnull=True).exclude(id=doc.id)
            .order_by(*SNAPSHOT_ORDER).first())
    try:
        data = read_and_judge(doc.application, doc, staged=bool(plan.get('staged')),
                              stale_ids=stale_ids, existing_live=existing_live)
    except Exception:  # never raise into the cron or the student's call: one failed attempt
        logger.warning('upload read failed doc=%s attempt=%s', doc_id, doc.read_attempts,
                       exc_info=True)
        if doc.read_attempts >= MAX_ATTEMPTS:
            _finish_read(doc_id, now, FAILED)
            return 'failed', None
        ApplicantDocument.objects.filter(pk=doc_id, read_claimed_at=now).update(read_claimed_at=None)
        return 'retry', None
    _finish_read(doc_id, now)
    data['reading'] = False
    return 'done', data


def answer_for(doc):
    """The read endpoint's answer for a document this call did not read (already read, being read
    by the cron, or superseded): the row as it stands, the verdict as it stands."""
    from .resolution import doc_match_verdict
    from .serializers import ApplicantDocumentSerializer
    reading = doc.read_state == PENDING
    data = ApplicantDocumentSerializer(doc).data
    data['match_verdict'] = 'pending' if reading else doc_match_verdict(doc)
    # Staged and never promoted: the copy it was judged against (an OLDER one) kept the slot.
    data['kept_previous'] = (not reading and doc.superseded_at is not None
                             and (doc.superseded_by_id is None or doc.superseded_by_id < doc.id))
    data['reading'] = reading
    return data


def run_pending(limit=BATCH):
    """The cron body: read up to ``limit`` queued uploads, oldest first. Never raises."""
    counts = {'done': 0, 'retry': 0, 'failed': 0, 'superseded': 0, 'not_claimed': 0, 'error': 0}
    now = timezone.now()
    # A read killed mid-call on its LAST attempt can never be claimed again: close it as failed.
    counts['failed'] += ApplicantDocument.objects.filter(
        read_state=PENDING, read_attempts__gte=MAX_ATTEMPTS, read_claimed_at__lt=now - STALE_CLAIM,
    ).update(read_state=FAILED, read_claimed_at=None)
    ids = list(ApplicantDocument.objects.filter(_read_claimable(now), read_state=PENDING,
                                                read_attempts__lt=MAX_ATTEMPTS)
               .order_by('uploaded_at', 'id').values_list('pk', flat=True)[:limit])
    for doc_id in ids:
        try:
            counts[run_read(doc_id)[0]] += 1
        except Exception:  # one bad row never stops the batch
            logger.warning('upload read run failed doc=%s', doc_id, exc_info=True)
            counts['error'] += 1
    return counts
