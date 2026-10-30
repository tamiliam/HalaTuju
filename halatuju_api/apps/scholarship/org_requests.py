"""Requests space — the org-section "Requests" area (Sprint 15).

Service layer for ``OrgRequest`` (bug reports + feature requests → AI reviewer → owner-gated
hours quotes). Follows the ``payments.py`` shape: pure service functions + an
``OrgRequestError(code)``; ``save(update_fields=...)`` where practical.

Named ``org_requests`` NOT ``requests`` — the latter collides with the HTTP ``requests`` library
in live imports; the model is ``OrgRequest`` NOT ``Request`` for the same grep-safety.

Two decision authorities live here:
  * the TRANSITIONS table — the single source of truth for which status an action moves a request
    FROM and TO (the view re-gates the actor role; the service raises ``bad_transition`` when the
    request isn't in a valid from-status, and ``wrong_role`` as an actor backstop);
  * ``run_ai_review`` — the ONLY AI seam, ``contracts._gemini_generate`` (mocked in tests, never a
    live call in CI). It is best-effort and capped at ``AI_RUN_CAP`` runs; a failure NEVER breaks a
    user action (the caller wraps it via ``auto_run_ai_review``). It classifies and asks; it does
    NOT estimate hours (owner, 2026-07-30 — it cannot see the codebase, so it priced greenfield
    every time). Its RATIONALE reaches the org (TD-202); the clarifying questions always did.

The adjudication rule (published verbatim, owner 2026-07-24) that the AI classifies against and the
owner triages by: *behaviour contradicting the role matrix / manual = bug (free);
working-as-documented-but-wanted-different = feature (priced)*.
"""
import hashlib
import json
import logging
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OrgRequest, REQUEST_COMPONENT_TREE, flatten_component_tree
# The shared vocabulary, so this module and `org_requests_ai` do not import each
# other at module level. All five names are used below, so none is a dead import.
# The AI reviewer lives in its own module since 2026-10-29 (moves only). Imported
# HERE, at the top, so the re-export further down is not an E402 — and an E402
# suppression would raise the suppression budget, which may not rise.
from . import org_requests_ai
from .org_requests_shared import (AI_RUN_CAP, AUTHOR_AI, AUTHOR_ENGINEER, AUTHOR_ORG,
                                  AUTHOR_OWNER, MAX_ATTACHMENTS, VALID_KINDS,
                                  VALID_LANES, VISIBILITY_INTERNAL,
                                  VISIBILITY_SHARED, OrgRequestError)

logger = logging.getLogger(__name__)


# The most UNANSWERED clarifying questions the thread carries at once — the AI is asked for 0-3 and
# we never let the open queue grow past this (a re-run appends only genuinely new questions).
MAX_OPEN_QUESTIONS = 3


# The IMAGE subset of the upload allowlist (jpg/jpeg/png/gif/bmp/webp/tif/tiff/heic/heif) — NO pdf.
# A screenshot is always an image; a PDF is rejected so the inline thumbnail render is always valid.
ATTACHMENT_IMAGE_EXTENSIONS = frozenset({
    '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tif', '.tiff', '.heic', '.heif',
})


def is_allowed_attachment(content_type, filename):
    """True iff the upload is an IMAGE (by MIME type or file extension) — NOT a PDF or anything
    else. Mirrors views._is_allowed_upload's image arm without the ``application/pdf`` branch."""
    import os
    ct = (content_type or '').lower().split(';')[0].strip()
    if ct == 'application/pdf':
        return False
    if ct.startswith('image/'):
        return True
    return os.path.splitext(filename or '')[1].lower() in ATTACHMENT_IMAGE_EXTENSIONS

_ZERO = Decimal('0')
_MAX_HOURS = Decimal('100000')   # sanity ceiling on a parsed AI estimate

# Optional Bugzilla-style scoping — the machine keys DERIVED from the component tree (Sprint 15.1;
# the single source of truth lives on the model). Includes the parent surfaces AND the two-level
# ``applications_<sub>`` values; '' always allowed (the field is optional). ``_clean_choice`` clamps
# anything outside this set to '' (there is no DB CHECK), so every FE-selectable value MUST be here.
VALID_COMPONENTS = flatten_component_tree(REQUEST_COMPONENT_TREE)
VALID_URGENCIES = ('blocking', 'important', 'nice_to_have')

# action -> (valid_from_statuses, to_status | None). No-transition actions (answer, ai_rerun) map
# to None. The test derives its terminal-refusal matrix from this table, so it stays authoritative.
TRANSITIONS = {
    'triage':   (('submitted',),                                  'triaged'),
    'quote':    (('triaged',),                                    'quoted'),
    'requote':  (('deferred',),                                   'quoted'),
    'approve':  (('quoted', 'deferred'),                          'approved'),
    'defer':    (('quoted',),                                     'deferred'),
    'modify':   (('quoted', 'deferred'),                          'submitted'),
    'schedule': (('triaged', 'approved'),                         'scheduled'),
    'done':     (('scheduled',),                                  'done'),
    'decline':  (('submitted', 'triaged', 'quoted', 'deferred'),  'declined'),
    # ANSWERING stays open until the quote is ACCEPTED (owner, 2026-07-30). Wider than 'ask' on
    # purpose: a question asked before the quote was priced into it, so replying completes the
    # record and cannot re-price anything by itself — whereas a NEW question after quoting could.
    # Closing this at 'triaged' stranded request #3: the quote landed with a question still open,
    # the answer box unmounted, and the thread read "Answer needed" with nowhere to answer it.
    'answer':   (('submitted', 'triaged', 'quoted', 'deferred'),  None),
    'ai_rerun': (('submitted', 'triaged'),                        None),
    # The owner asking the requester something. Same window as the AI's own questions and the
    # answer path — a quoted or terminal request must not grow new questions, because the quote
    # was priced against what was known when it was sent.
    'ask':      (('submitted', 'triaged'),                        None),
}

TERMINAL_STATUSES = ('done', 'declined')

# The longest a discussion comment may be. `OrgRequestComment.body` is a TextField, so this is a
# sanity ceiling on what a person can type, never a storage limit.
#
# ⚠ IT REFUSES; IT DOES NOT TRUNCATE, and that is the whole point of it existing as a named
# constant. `post_comment` used to write `body[:5000]` — an unexplained slice, no validation, no
# error. On 2026-08-01 an engineer's analysis of 7,015 characters was approved and the requesting
# organisation received **5,000 of them**, ending mid-word, missing a correction we had gone out of
# our way to make and the entire effort breakdown. Nothing failed, nothing logged, and the record
# on our side still held the full text — so the two sides of the same conversation disagreed and
# only the requester could see it.
#
# The number is generous because the constraint is human, not technical; what matters is that
# crossing it is an ERROR the author sees while writing, not a silent edit at approval time — two
# steps and one actor away from whoever wrote the words.
COMMENT_MAX_CHARS = 20000

# The statuses in which a request is still BEING SHAPED — evidence and clarification may still
# change what it is and what it should cost. Acceptance is the boundary (owner, 2026-07-30): a
# screenshot added after the quote is accepted would change the evidence behind an agreed number.
# Deliberately the SAME window as TRANSITIONS['answer'], held once so the two cannot drift; the
# frontend mirror is REQUEST_OPEN_FOR_SHAPING in requestStatus.ts, pinned by a test on each side.
OPEN_FOR_SHAPING = ('submitted', 'triaged', 'quoted', 'deferred')


def can_attach(req):
    """Whether screenshots may still be added or removed. See OPEN_FOR_SHAPING.

    Wider than "not terminal", which is what the attachment views enforced until 2026-07-30 —
    that let evidence change under an accepted quote.
    """
    return getattr(req, 'status', None) in OPEN_FOR_SHAPING




def _is_super(admin):
    return bool(getattr(admin, 'is_super', False))


def _check_transition(req, action):
    valid_from, _to = TRANSITIONS[action]
    if req.status not in valid_from:
        raise OrgRequestError('bad_transition')


def _effective_kind(req):
    """The owner's triaged kind wins over the submitter's declared kind (the adjudication rule is
    the owner's to apply); falls back to the declared kind before triage."""
    return req.triaged_kind or req.kind


# ── create ──────────────────────────────────────────────────────────────────────

def _clean_choice(value, valid):
    """Clamp an optional choice to the valid set; anything unknown (incl. None) → '' (the field is
    optional, so a bad value is dropped rather than raising)."""
    v = (value or '').strip()
    return v if v in valid else ''


@transaction.atomic
def create_request(organisation, submitted_by, *, kind, title, description,
                   component='', urgency='', steps_to_reproduce=''):
    """Create a SUBMITTED request for ``organisation`` by ``submitted_by`` (a PartnerAdmin).
    Validates kind/title; the three Bugzilla-style scoping fields (component/urgency/steps) are
    OPTIONAL — component/urgency clamp to their choice sets ('' allowed), steps is free text. The
    caller (view) has already fenced the organisation to the actor. AI auto-run + the owner-notify
    email are the caller's best-effort post-commit steps."""
    if kind not in VALID_KINDS:
        raise OrgRequestError('bad_kind')
    title = (title or '').strip()
    description = (description or '').strip()
    if not title:
        raise OrgRequestError('title_required')
    if not description:
        raise OrgRequestError('description_required')
    return OrgRequest.objects.create(
        organisation=organisation, submitted_by=submitted_by,
        kind=kind, title=title[:200], description=description,
        component=_clean_choice(component, VALID_COMPONENTS),
        urgency=_clean_choice(urgency, VALID_URGENCIES),
        steps_to_reproduce=(steps_to_reproduce or '').strip(),
    )


# ── clarification thread ──────────────────────────────────────────────────────────

# ── the discussion (TD-201, owner 2026-07-31) ───────────────────────────────────
#
# Replaces the `clarifications` JSONField of {question, answer} PAIRS. A QUESTION IS A COMMENT
# AWAITING A REPLY — that is what makes this one stream rather than a comment table beside a
# question table. See models.OrgRequestComment for why `visibility` exists from the first migration.




def comments_for(req, *, viewer_is_org):
    """The thread as the viewer may see it, oldest first.

    ⚠ The visibility filter lives HERE, once. The org-facing serializer is an allowlist and cannot
    leak a field it does not name, but it CAN leak a row — a serializer that names `body` will
    happily render an internal comment. Filtering at the query is the only place that distinguishes
    rows rather than columns.
    """
    rows = prefetched_rows(req, 'comments')
    if rows is not None:                     # the Requests LIST prefetched them (TD-291)
        return [c for c in rows if not viewer_is_org or c.visibility == VISIBILITY_SHARED]
    qs = req.comments.all().select_related('author_admin')
    if viewer_is_org:
        qs = qs.filter(visibility=VISIBILITY_SHARED)
    return list(qs)


def prefetched_rows(req, name):
    """`req.<name>` as already loaded by a list view's prefetch, else None (TD-291). A `.filter`
    on a related manager IGNORES a prefetch, so each reader filters the loaded rows itself."""
    cache = getattr(req, '_prefetched_objects_cache', None) or {}
    return list(cache[name]) if name in cache else None


def can_comment(req):
    """Commenting stays open until the request is TERMINAL — deliberately WIDER than
    ``OPEN_FOR_SHAPING`` (owner, 2026-07-31).

    Answering and attaching close when the quote is accepted because both change what was priced.
    A remark does not, and the owner's model is explicit: *"open discussion/debate, even after it
    has been assigned to someone."* Two windows, each with its own reason — do not "tidy" them into
    one. Asking a NEW question is the narrow one (``TRANSITIONS['ask']``): a question can re-price,
    which is why it still stops when the quote goes out.
    """
    return req.status not in TERMINAL_STATUSES


def open_questions(req):
    """Comments still awaiting a reply, in order."""
    return [c for c in req.comments.all() if c.awaiting_reply]


def _open_ai_questions(req):
    """The AI's own unanswered questions — what ``MAX_OPEN_QUESTIONS`` actually caps.

    The cap exists so an eager reviewer cannot bury the requester. It was never meant to stop the
    OWNER asking something, so an owner question must not consume the AI's room; otherwise asking
    one thing by hand silently costs the reviewer a slot.
    """
    return [c for c in open_questions(req) if c.author_kind == AUTHOR_AI]


def post_comment(req, admin, body, *, author_kind, visibility=VISIBILITY_SHARED,
                 awaiting_reply=False):
    """Append one entry to the discussion. The single write path — ``ask_question``, the AI's
    questions and the requester's replies all land here so authorship, visibility and the window
    are enforced in one place.

    ⚠ An INTERNAL comment is platform-side only; a caller must never mark an org author internal
    (there is no org-internal tier — if one is ever wanted it is a third value, not a reuse of
    this one).

    ⚠ AN ORG COMMENT SETTLES THE QUESTIONS BEFORE IT — see ``_settle_open_questions``.
    """
    body = (body or '').strip()
    if not body:
        raise OrgRequestError('body_required')
    if len(body) > COMMENT_MAX_CHARS:
        raise OrgRequestError('body_too_long')
    if author_kind not in {AUTHOR_AI, AUTHOR_OWNER, AUTHOR_ORG, AUTHOR_ENGINEER}:
        raise OrgRequestError('bad_author')
    if visibility not in {VISIBILITY_SHARED, VISIBILITY_INTERNAL}:
        raise OrgRequestError('bad_visibility')
    if author_kind == AUTHOR_ORG and visibility == VISIBILITY_INTERNAL:
        raise OrgRequestError('bad_visibility')
    if not can_comment(req):
        raise OrgRequestError('bad_transition')
    from .models import OrgRequestComment
    posted = OrgRequestComment.objects.create(
        org_request=req,
        author_kind=author_kind,
        author_admin=admin if getattr(admin, 'pk', None) else None,
        body=body,
        visibility=visibility,
        awaiting_reply=awaiting_reply,
    )
    if author_kind == AUTHOR_ORG:
        _settle_open_questions(req, before=posted)
    return posted


def _settle_open_questions(req, *, before):
    """The requester has spoken, so we are no longer waiting on them (owner, 2026-07-31).

    ``awaiting_reply`` means exactly one thing: **the ball is in the requester's court**. It drives
    the owner's Requests badge, the reviewer's question budget and the "Answer needed" prompt. So
    the moment the requester says anything, every question standing before it is settled — whether
    they used the reply box or the comment box.

    ⚠ THIS IS THE FIX FOR A DEAD END THE TWO-BOX DESIGN CREATED. Answering closes at acceptance
    while commenting runs to the end, so on an approved request the reply box is gone and the
    comment box is all that is left. Clearing the flag ONLY in ``answer_clarification`` therefore
    meant a question answered after acceptance read "Unanswered" for ever, directly above its own
    answer, and the owner's badge stayed lit on a request nobody was waiting on. Request #3 did
    exactly that. Two boxes are a detail of WHEN you may speak; they must never decide WHETHER
    speaking counts as an answer.

    Settles ALL preceding open questions, not just the oldest: the flag is a claim about who owes
    whom, and once the requester has replied that claim is false for every one of them. If a remark
    turns out not to answer something the owner reads the thread and asks again — an early clear is
    visible and recoverable, a permanent one is neither.
    """
    req.comments.filter(awaiting_reply=True, id__lt=before.id).update(
        awaiting_reply=False, replied_at=timezone.now())


def comment(req, admin, body, *, visibility=VISIBILITY_SHARED):
    """The OWNER posts a STATEMENT — the verb the module never had (super-only).

    Until now exactly one verb reached the requester: ``ask`` a question. So a conclusion — *"here
    is what we would build, and why"* — had to travel as a quote note or not at all, and the owner's
    judgement about the SHAPE of a request left the system. A statement expects no reply, so it does
    not set ``awaiting_reply`` and does not touch the question cap.
    """
    if not _is_super(admin):
        raise OrgRequestError('forbidden')
    return post_comment(req, admin, body, author_kind=AUTHOR_OWNER, visibility=visibility)


def ask_question(req, admin, question):
    """The OWNER asks the requester something (super-only) — a comment that AWAITS A REPLY.

    Kept on the NARROW window (``TRANSITIONS['ask']``, submitted/triaged) while plain comments run
    until terminal: a quoted request must not grow new questions, because the quote was priced
    against what was known when it was sent. A remark carries no such risk.

    Deliberately NOT counted against ``MAX_OPEN_QUESTIONS`` — see ``_open_ai_questions``.
    The caller emails the requester, matching how the AI's questions are delivered.
    """
    if not _is_super(admin):
        raise OrgRequestError('forbidden')
    _check_transition(req, 'ask')
    question = (question or '').strip()
    if not question:
        raise OrgRequestError('question_required')
    # Same dedup as the AI's, on text: asking the identical thing twice is a slip, not an intent.
    if any(c.body.strip().casefold() == question.casefold() for c in req.comments.all()):
        raise OrgRequestError('duplicate_question')
    post_comment(req, admin, question[:1000], author_kind=AUTHOR_OWNER,
                 visibility=VISIBILITY_SHARED, awaiting_reply=True)
    return question[:1000]


def answer_clarification(req, answer, *, comment_id=None, admin=None):
    """The requesting org replies (no status transition — allowed until the quote is ACCEPTED,
    i.e. submitted/triaged/quoted/deferred).

    The reply is itself a comment, authored by the org; the question it answers is stamped replied.
    ``comment_id`` selects which open question; omitted, it answers the OLDEST one. Raises
    ``not_answerable`` when there is nothing awaiting a reply.
    """
    _check_transition(req, 'answer')
    answer = (answer or '').strip()
    if not answer:
        raise OrgRequestError('answer_required')

    if comment_id in (None, ''):
        target = next(iter(open_questions(req)), None)
    else:
        # Coerced HERE rather than at the view, so a shell caller gets the same answer as an HTTP
        # one. A value that is not an id cannot name a question, so it is `not_answerable` — never
        # a 500, and never a silent fall-through to the oldest, which would answer the wrong
        # question while reporting success.
        try:
            comment_id = int(comment_id)
        except (TypeError, ValueError):
            raise OrgRequestError('not_answerable')
        target = req.comments.filter(pk=comment_id, awaiting_reply=True).first()
    if target is None:
        raise OrgRequestError('not_answerable')

    post_comment(req, admin, answer[:2000], author_kind=AUTHOR_ORG,
                 visibility=VISIBILITY_SHARED)
    target.awaiting_reply = False
    target.replied_at = timezone.now()
    target.save(update_fields=['awaiting_reply', 'replied_at'])
    return req


# ── owner triage / quote / schedule / done ────────────────────────────────────────

def triage(req, admin, *, triaged_kind, lane, note=''):
    """submitted → triaged (super). Sets the authoritative kind + lane (may override the AI /
    the submitter's declared kind, per the adjudication rule)."""
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'triage')
    if triaged_kind not in VALID_KINDS:
        raise OrgRequestError('bad_kind')
    if lane not in VALID_LANES:
        raise OrgRequestError('bad_lane')
    req.triaged_kind = triaged_kind
    req.lane = lane
    req.triage_note = (note or '').strip()
    req.triaged_at = timezone.now()
    req.status = 'triaged'
    req.save(update_fields=[
        'triaged_kind', 'lane', 'triage_note', 'triaged_at', 'status', 'updated_at'])
    return req


def _clean_hours(value):
    try:
        h = Decimal(str(value)).quantize(Decimal('0.1'))
    except (InvalidOperation, ValueError, TypeError):
        raise OrgRequestError('bad_hours')
    if h <= 0 or h > _MAX_HOURS:
        raise OrgRequestError('bad_hours')
    return h


# ── the engineer's analysis (TD-204, owner 2026-07-31) ──────────────────────────
#
# Owner: "Gemini's role is only initial analysis. It has no access to the codebase and cannot
# reliably do much. You have to do the proper analysis and estimate the workload, and I want you to
# post as well, with my approval."
#
# Two actors, deliberately: the engineer STAGES a draft, the owner APPROVES it, and only approval
# posts anything to the requester. Same split as `pool.publish_profile_to_pool` — preparing is free,
# publishing is the control.

MAX_CITED_FILES = 40
_MAX_CITED_PATH = 255


def _clean_cited_files(values):
    """Normalise the citation list: strip, drop blanks, dedupe PRESERVING ORDER, cap.

    Order is preserved because the first file named is usually the one that decides the estimate,
    and a reader scanning the list is reading the engineer's reasoning order.
    """
    if values is None:
        return []
    if isinstance(values, (str, bytes)) or not hasattr(values, '__iter__'):
        raise OrgRequestError('bad_cited_files')
    out = []
    for value in values:
        if not isinstance(value, str):
            raise OrgRequestError('bad_cited_files')
        path = value.strip()
        if not path:
            continue
        if len(path) > _MAX_CITED_PATH:
            raise OrgRequestError('bad_cited_files')
        if path not in out:
            out.append(path)
    if len(out) > MAX_CITED_FILES:
        raise OrgRequestError('bad_cited_files')
    return out


def _description_sha(req):
    """sha256 of the description the analysis was written against — the audit trail behind
    supersession. Stored, never compared automatically; `modify()` supersedes explicitly."""
    return hashlib.sha256((req.description or '').encode('utf-8')).hexdigest()


def _clean_proposal(kind, lane):
    """The engineer's proposed triage, or ('', '') — validated against the SAME vocabularies the
    triage action uses, so a proposal can never prefill the form with a value the form would then
    refuse. A blank or unrecognised value is dropped silently: a proposal is advice, and advice
    that cannot be spelled correctly is simply absent.
    """
    from .models import OrgRequest
    kinds = {k for k, _ in OrgRequest.KIND_CHOICES}
    lanes = {l for l, _ in OrgRequest.LANE_CHOICES}
    kind = (kind or '').strip().lower()
    lane = (lane or '').strip().lower()
    return (kind if kind in kinds else ''), (lane if lane in lanes else '')


def record_analysis(req, admin, *, body, estimated_hours=None, cited_files=(),
                    authored_by='', repo_sha='', proposed_kind='', proposed_lane=''):
    """Stage a DRAFT analysis. Posts NOTHING — approval is the act that reaches the requester.

    ⚠ Deliberately NOT super-gated in the service, while `approve_analysis` is. A draft is invisible
    to the requesting organisation BY CONSTRUCTION — no org-facing serializer names this table — and
    has no effect on anything until approved, so staging one is not a privileged act. The ENDPOINT
    is still `_super_side`; this mirrors `pool.publish_profile_to_pool`, where preparing the profile
    is ungated and publishing it is the control.

    ⚠ AT LEAST ONE CITED FILE IS REQUIRED, here and again at approval. The standing rule is that the
    estimate must cite its files — that is the only thing separating the engineer's number from the
    model's. An analysis citing nothing is the thing this record exists to prevent.
    """
    body = (body or '').strip()
    if not body:
        raise OrgRequestError('body_required')
    # ⚠ Checked HERE as well as in `post_comment`, deliberately. A draft is written now and posted
    # later by somebody else; discovering at approval that the prose will not fit is discovering it
    # in front of the owner, with the author gone. An analysis that cannot post INTACT is refused
    # while it is still being written.
    if len(body) > COMMENT_MAX_CHARS:
        raise OrgRequestError('body_too_long')
    if not can_comment(req):
        # Terminal: there is nothing left to analyse, and approval could never post it.
        raise OrgRequestError('bad_transition')
    files = _clean_cited_files(cited_files)
    if not files:
        raise OrgRequestError('files_required')
    hours = _clean_hours(estimated_hours) if estimated_hours not in (None, '') else None

    p_kind, p_lane = _clean_proposal(proposed_kind, proposed_lane)

    from .models import OrgRequestAnalysis
    return OrgRequestAnalysis.objects.create(
        org_request=req,
        body=body,
        estimated_hours=hours,
        cited_files=files,
        authored_by=(authored_by or '').strip()[:50],
        repo_sha=(repo_sha or '').strip()[:40],
        description_sha=_description_sha(req),
        # A RECOMMENDATION. Stored here, applied nowhere — `triage()` is still the only thing that
        # writes the request's own kind and lane, and only an owner may call it.
        proposed_kind=p_kind,
        proposed_lane=p_lane,
    )


@transaction.atomic
def approve_analysis(analysis, admin):
    """The OWNER approves an analysis, and it enters the thread as an `engineer` comment (super).

    Atomic on purpose: a failed post must leave NO approved-but-unposted row, or the quote gate
    would pass on an analysis the requester never received.

    IDEMPOTENT — an already-approved analysis returns unchanged and posts nothing a second time,
    mirroring `pool.publish_profile_to_pool`.

    ⚠ The posted comment carries `author_admin=None`, exactly as the AI's questions do. Attributing
    it to the approving owner would print their name beside an "Engineer" badge, which is a lie
    about who wrote it. Provenance lives on THIS row (`authored_by`, `approved_by`).

    ⚠ Only `body` crosses to the requester. `cited_files` and `estimated_hours` stay here — see the
    model docstring.
    """
    if not _is_super(admin):
        raise OrgRequestError('forbidden')
    if analysis.approved_at:
        return analysis
    if analysis.superseded_at:
        raise OrgRequestError('analysis_superseded')
    if not analysis.cited_files:
        raise OrgRequestError('files_required')

    req = analysis.org_request
    posted = post_comment(req, None, analysis.body, author_kind=AUTHOR_ENGINEER,
                          visibility=VISIBILITY_SHARED)
    analysis.approved_at = timezone.now()
    analysis.approved_by = admin if getattr(admin, 'pk', None) else None
    analysis.posted_comment = posted
    analysis.save(update_fields=['approved_at', 'approved_by', 'posted_comment', 'updated_at'])
    return analysis


def withdraw_analysis(analysis, admin):
    """Retire a DRAFT the engineer got wrong, so it can never be approved by mistake (super).

    ⚠ The reason this exists: staging is POST-only and there was no way to correct or retract a
    draft, so fixing one meant staging a second and leaving the first sitting in the approve list.
    On 2026-08-01 that produced two near-identical drafts on request #10 — same "Draft" badge, same
    hours, same cited files, and NO timestamp on screen — and `approve_analysis` has no guard
    against approving both, so the stale one was one mis-click from reaching the requester as a
    second engineer comment. The remedy is a retraction, not a sharper pair of eyes.

    It stamps `superseded_at` rather than deleting the row, for two reasons. The guard already
    exists — `approve_analysis` refuses a superseded analysis — so this is a setter for an
    enforcement that was written and unreachable. And a withdrawn draft is part of how the estimate
    was arrived at; the record is a working paper, and destroying the wrong turn would make the
    thinking less legible, not more.

    ⚠ APPROVED analyses are refused. Once the prose is in the thread the requester has read it, and
    unsaying it here would leave the comment standing with no record behind it — that is
    `modify()`'s job (it supersedes approved analyses when the description itself changes).
    """
    if not _is_super(admin):
        raise OrgRequestError('forbidden')
    if analysis.approved_at:
        raise OrgRequestError('analysis_approved')
    if analysis.superseded_at:
        return analysis                      # idempotent, mirroring approve_analysis
    analysis.superseded_at = timezone.now()
    analysis.save(update_fields=['superseded_at', 'updated_at'])
    return analysis


def approved_analysis(req):
    """The analysis standing behind this request, or None. The ONE home for that question — the
    quote gate and the owner payload both read it, so they cannot disagree.

    Approved, not superseded, and carrying at least one cited file.
    """
    rows = prefetched_rows(req, 'analyses')
    if rows is not None:                     # same rule, over the prefetched rows (TD-291)
        live = [a for a in rows if a.approved_at and not a.superseded_at and a.cited_files != []]
        return max(live, key=lambda a: (a.approved_at, a.id), default=None)
    return (req.analyses
            .filter(approved_at__isnull=False, superseded_at__isnull=True)
            .exclude(cited_files=[])
            .order_by('-approved_at', '-id')
            .first())


def _supersede_analyses(req):
    """The request changed underneath them, so no approved analysis describes it any more.

    Called from `modify()` ONLY. Deliberately not derived by comparing `created_at` to
    `updated_at`: `updated_at` is `auto_now`, so our own sweeps bump it — this project has already
    been bitten by exactly that on partner "last activity". Superseding at the one seam that
    rewrites the description is legible; a timestamp heuristic is not.

    An ANSWER can also change scope, and deliberately does NOT supersede — answers are frequent and
    that would be a treadmill. The cockpit shows an amber "predates the last comment" note instead.
    """
    req.analyses.filter(approved_at__isnull=False, superseded_at__isnull=True).update(
        superseded_at=timezone.now())


def _require_analysis(req):
    """Refuse to price work nobody has read the code for (owner, 2026-07-31).

    ⚠ Called EXPLICITLY from both `quote()` and `requote()`, in the same position, rather than from
    the shared `_apply_quote`. `_apply_quote` is a field writer; an evidence policy at that altitude
    would make the error ORDERING accidental (whether the owner sees `analysis_required` or
    `bad_hours` would depend on which line it sat above). The duplication is honest — those two
    functions are already deliberate byte-identical twins — and a test asserting BOTH refuse is the
    anti-drift device.
    """
    if approved_analysis(req) is None:
        raise OrgRequestError('analysis_required')


def _clean_margin(value):
    if value is None or value == '':
        return int(getattr(settings, 'REQUESTS_QUOTE_MARGIN_PCT', 50))
    try:
        m = int(value)
    except (ValueError, TypeError):
        raise OrgRequestError('bad_margin')
    if m < 0 or m > 1000:
        raise OrgRequestError('bad_margin')
    return m


def _apply_quote(req, hours, margin_pct, note):
    req.quote_hours = _clean_hours(hours)
    req.quote_margin_pct = _clean_margin(margin_pct)
    req.quote_note = (note or '').strip()
    req.quoted_at = timezone.now()
    req.status = 'quoted'


def quote(req, admin, *, hours, margin_pct=None, note=''):
    """triaged → quoted (super). FEATURE only — a bug is free (`bug_is_free`) and skips straight
    to scheduling. Hours > 0; margin defaults from settings. The email to the submitter is the
    caller's post-commit step.

    ⚠ Requires an approved analysis citing files (`analysis_required`, TD-204). `bug_is_free` stays
    ABOVE it: a bug is never quoted at all, so demanding an analysis before saying "schedule it
    instead" gives a worse message AND implies the rule covers bugs, which it does not.
    """
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'quote')
    if _effective_kind(req) != 'feature':
        raise OrgRequestError('bug_is_free')
    _require_analysis(req)
    _apply_quote(req, hours, margin_pct, note)
    req.save(update_fields=[
        'quote_hours', 'quote_margin_pct', 'quote_note', 'quoted_at', 'status', 'updated_at'])
    return req


def requote(req, admin, *, hours, margin_pct=None, note=''):
    """deferred → quoted (super). Re-quote a parked request (feature only, same rules as quote).

    ⚠ Carries `_require_analysis` in the SAME position as `quote()`. These two are deliberate
    byte-identical twins; a test asserts both refuse, because a gate on one of two twins is the
    exact shape of the `award_amount` defect (a rule kept at one caller out of three).
    """
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'requote')
    if _effective_kind(req) != 'feature':
        raise OrgRequestError('bug_is_free')
    _require_analysis(req)
    _apply_quote(req, hours, margin_pct, note)
    req.save(update_fields=[
        'quote_hours', 'quote_margin_pct', 'quote_note', 'quoted_at', 'status', 'updated_at'])
    return req


def schedule(req, admin, *, scheduled_for=None):
    """triaged → scheduled (a free BUG lane skips the quote) OR approved → scheduled (super,
    optional date). A feature at triaged must be quoted first — scheduling it here is a
    bad_transition (a bug is the only thing schedulable straight from triage)."""
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'schedule')
    if req.status == 'triaged' and _effective_kind(req) != 'bug':
        raise OrgRequestError('bad_transition')
    req.scheduled_for = scheduled_for
    req.status = 'scheduled'
    req.save(update_fields=['scheduled_for', 'status', 'updated_at'])
    return req


def done(req, admin):
    """scheduled → done (super). Terminal.

    ⚠⚠ **IT CANNOT CLOSE WITHOUT ITS CLOSING REPORT** (owner, 2026-10-30: *"agent that complete a
    request MUST ... They shouldn't need reminder from me"*). This is the ONE door into the
    terminal state, so it is the only place that rule can be made true rather than hoped for. A
    forgotten figure used to surface a month later: five of the first sixteen billed requests were
    billed on their PLAN. `invoicing.actual_hours_missing` refuses that month ABSOLUTELY — correct,
    and four weeks too late. The full story is in `TestClosingAReport`.

    ⚠ ONE check suffices because `record_hours` requires `actual_hours`, so a row carrying
    `charged_hours` carries the actual too — and `closing_report` reads what the organisation was
    SENT, the only honest source for a bill.
    ⚠ **A BUG IS NOT EXEMPT**: its charge is `0.0`, which is what `bug_reports_fixed` counts as
    free work given away — an answer, where a blank is not.

    ⚠ ORDER: `_check_transition` runs FIRST, so a never-closable status stays `bad_transition`.
    `request_hours` is imported inside the function — at module scope the pair would cycle.
    """
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'done')
    from . import request_hours
    if request_hours.closing_report(req) is None:
        raise OrgRequestError('closing_report_required')
    req.status = 'done'
    req.save(update_fields=['status', 'updated_at'])
    return req


# ── requestee responses to a quote ────────────────────────────────────────────────

def approve(req, admin, *, by_role):
    """quoted/deferred → approved (the submitting org's org_admin, or super). Owner-notify is the
    caller's post-commit step.

    ⚠ **WHO accepted is recorded, not just when** (TD-418, owner 2026-10-29). Both arguments were
    already being handed in and discarded. A feature cannot be billed without an acceptance
    (`request_hours.consent_gaps`), so this is the provenance of a charge: `by_role` distinguishes
    the customer accepting their own quote from a super accepting on their behalf, and both are
    legitimate. `admin` may have no primary key in a test double, so it is stored defensively the
    same way `approve_analysis` does it.
    """
    _check_transition(req, 'approve')
    req.approved_at = timezone.now()
    req.approved_by = admin if getattr(admin, 'pk', None) else None
    req.approved_by_role = (by_role or '').strip()
    req.status = 'approved'
    req.save(update_fields=['approved_at', 'approved_by', 'approved_by_role', 'status',
                            'updated_at'])
    return req


def defer(req, admin):
    """quoted → deferred (org_admin own org). Parks the quote — acceptable later, re-quotable."""
    _check_transition(req, 'defer')
    req.status = 'deferred'
    req.save(update_fields=['status', 'updated_at'])
    return req


@transaction.atomic
def modify(req, admin, *, description):
    """quoted/deferred → submitted (org_admin own org). Amends the description, records the OLD
    text in the thread as history, then returns to triage. The AI re-runs (caller's post-commit
    step)."""
    _check_transition(req, 'modify')
    description = (description or '').strip()
    if not description:
        raise OrgRequestError('description_required')
    previous = req.description
    req.description = description
    req.status = 'submitted'
    req.save(update_fields=['description', 'status', 'updated_at'])
    # ⚠ The description this was written against no longer exists, so no approved analysis
    # describes this request any more (TD-204). Without this, the quote gate would pass on an
    # analysis of text nobody can read — silent mispricing, the same class as the `award_amount`
    # bug. Immediately after the save, so the two facts move together.
    _supersede_analyses(req)
    # After the save, so a failure recording history cannot leave the amendment half-applied.
    # SHARED, and authored by the org: `modify` is an org_admin action (`_requestee`), and the
    # history is a record of what the REQUESTER themselves changed — there is nothing private in
    # it, and they can already see the new text. (An earlier draft marked this internal, which the
    # service correctly refused: an org author may not write a platform-internal note.)
    post_comment(req, admin,
                 'Description amended. Previous text:\n\n' + previous,
                 author_kind=AUTHOR_ORG, visibility=VISIBILITY_SHARED)
    return req


def decline(req, admin, *, by_role, reason=''):
    """submitted/triaged/quoted/deferred → declined. Terminal. A super DECLINE requires a reason
    (``reason_required``); an org_admin WITHDRAW may omit it. ``declined_by_role`` is recorded."""
    _check_transition(req, 'decline')
    reason = (reason or '').strip()
    if by_role == 'super' and not reason:
        raise OrgRequestError('reason_required')
    req.decline_reason = reason
    req.declined_by_role = by_role
    req.status = 'declined'
    req.save(update_fields=['decline_reason', 'declined_by_role', 'status', 'updated_at'])
    return req


# ── AI reviewer (the ONLY AI seam) ───────────────────────────────
#
# The reviewer moved to `org_requests_ai.py` on 2026-10-29 (moves only: this file reached
# 1,086 lines against a 1,081-line allowance). Re-exported below so every existing caller —
# the views, `models.OrgRequest`, and the tests that call these by name — keeps working.
#
# ⚠ BOUND AS NAMES, not `from .org_requests_ai import ...`: a re-export import reads as unused
# to the linter and needs an F401 suppression, and the count of those suppressions is itself a
# budget that may not rise. Binding through the module uses the import, so nothing is
# suppressed. (Same reason as the re-export at the top of `platform_cost`.)
_ADJUDICATION_RULE = org_requests_ai._ADJUDICATION_RULE
_LANE_DEFINITIONS = org_requests_ai._LANE_DEFINITIONS
_review_images = org_requests_ai._review_images
_build_review_prompt = org_requests_ai._build_review_prompt
_has_attachments = org_requests_ai._has_attachments
_parse_draft = org_requests_ai._parse_draft
run_ai_review = org_requests_ai.run_ai_review
_append_questions = org_requests_ai._append_questions
auto_run_ai_review = org_requests_ai.auto_run_ai_review
