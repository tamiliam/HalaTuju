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
import json
import logging
import re
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from .models import OrgRequest, REQUEST_COMPONENT_TREE, flatten_component_tree

logger = logging.getLogger(__name__)

# Auto-run cap (owner 2026-07-24) — the AI reviewer runs at most this many times per request
# (on create + on each clarification answer). A super may still trigger a manual re-run, which is
# also bounded by this cap. Guards against Gemini cost runaway.
AI_RUN_CAP = 3

# The most UNANSWERED clarifying questions the thread carries at once — the AI is asked for 0-3 and
# we never let the open queue grow past this (a re-run appends only genuinely new questions).
MAX_OPEN_QUESTIONS = 3

# Screenshot attachments (Sprint 15.1, TD-172): images ONLY, at most this many per request. The cap
# is enforced at BOTH the sign-upload (before we mint a URL) and the record (after the PUT) seams.
MAX_ATTACHMENTS = 5

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

VALID_KINDS = ('bug', 'feature')
VALID_LANES = ('small_change', 'sprint')
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


class OrgRequestError(Exception):
    """Raised by the service with a machine code for the view (e.g. 'bad_transition',
    'bug_is_free', 'bad_hours', 'reason_required', 'wrong_role')."""
    def __init__(self, code, message=''):
        self.code = code
        super().__init__(message or code)


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
AUTHOR_AI = 'ai'
AUTHOR_OWNER = 'owner'
AUTHOR_ORG = 'org'

# How each author is introduced to the reviewer in the prompt.
_SPEAKER = {AUTHOR_OWNER: 'the owner', AUTHOR_ORG: 'the requester',
            AUTHOR_AI: 'you, earlier'}

VISIBILITY_SHARED = 'shared'
VISIBILITY_INTERNAL = 'internal'


def comments_for(req, *, viewer_is_org):
    """The thread as the viewer may see it, oldest first.

    ⚠ The visibility filter lives HERE, once. The org-facing serializer is an allowlist and cannot
    leak a field it does not name, but it CAN leak a row — a serializer that names `body` will
    happily render an internal comment. Filtering at the query is the only place that distinguishes
    rows rather than columns.
    """
    qs = req.comments.all().select_related('author_admin')
    if viewer_is_org:
        qs = qs.filter(visibility=VISIBILITY_SHARED)
    return list(qs)


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
    """
    body = (body or '').strip()
    if not body:
        raise OrgRequestError('body_required')
    if author_kind not in {AUTHOR_AI, AUTHOR_OWNER, AUTHOR_ORG}:
        raise OrgRequestError('bad_author')
    if visibility not in {VISIBILITY_SHARED, VISIBILITY_INTERNAL}:
        raise OrgRequestError('bad_visibility')
    if author_kind == AUTHOR_ORG and visibility == VISIBILITY_INTERNAL:
        raise OrgRequestError('bad_visibility')
    if not can_comment(req):
        raise OrgRequestError('bad_transition')
    from .models import OrgRequestComment
    return OrgRequestComment.objects.create(
        org_request=req,
        author_kind=author_kind,
        author_admin=admin if getattr(admin, 'pk', None) else None,
        body=body[:5000],
        visibility=visibility,
        awaiting_reply=awaiting_reply,
    )


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

    if comment_id is not None:
        target = req.comments.filter(pk=comment_id, awaiting_reply=True).first()
    else:
        target = next(iter(open_questions(req)), None)
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
    caller's post-commit step."""
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'quote')
    if _effective_kind(req) != 'feature':
        raise OrgRequestError('bug_is_free')
    _apply_quote(req, hours, margin_pct, note)
    req.save(update_fields=[
        'quote_hours', 'quote_margin_pct', 'quote_note', 'quoted_at', 'status', 'updated_at'])
    return req


def requote(req, admin, *, hours, margin_pct=None, note=''):
    """deferred → quoted (super). Re-quote a parked request (feature only, same rules as quote)."""
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'requote')
    if _effective_kind(req) != 'feature':
        raise OrgRequestError('bug_is_free')
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
    """scheduled → done (super). Terminal."""
    if not _is_super(admin):
        raise OrgRequestError('wrong_role')
    _check_transition(req, 'done')
    req.status = 'done'
    req.save(update_fields=['status', 'updated_at'])
    return req


# ── requestee responses to a quote ────────────────────────────────────────────────

def approve(req, admin, *, by_role):
    """quoted/deferred → approved (the submitting org's org_admin, or super). Owner-notify is the
    caller's post-commit step."""
    _check_transition(req, 'approve')
    req.approved_at = timezone.now()
    req.status = 'approved'
    req.save(update_fields=['approved_at', 'status', 'updated_at'])
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


# ── AI reviewer (the ONLY AI seam) ────────────────────────────────────────────────

_ADJUDICATION_RULE = (
    'Adjudication rule: behaviour that CONTRADICTS the documented role matrix / manual is a BUG '
    '(free). Behaviour that works AS DOCUMENTED but the org wants it DIFFERENT is a FEATURE '
    '(priced).'
)
_LANE_DEFINITIONS = (
    'Lane definitions: "small_change" = a one-off fix or tweak (a handful of files, no new model / '
    'page / feature); "sprint" = a new feature, page, model, or anything touching money / consent / '
    'auth / PII.'
)


def _review_images(req):
    """The submitter's screenshots as ``[(bytes, mime), …]`` for the multimodal review.

    Until 2026-07-30 the reviewer was told only HOW MANY images were attached, never shown them —
    so on a request that is entirely about a screen ("add a link here", with two screenshots
    showing exactly where) it was estimating blind. Owner decision: send them.

    Best-effort per image: a blob that will not fetch is skipped rather than failing the review,
    because a broken attachment must not cost the owner their triage. Bounded by the same ≤5
    attachment cap the upload path enforces.
    """
    from .vision import _fetch_image_bytes
    out = []
    try:
        attachments = list(req.attachments.all()) if req.pk else []
    except Exception:
        return out
    for att in attachments[:MAX_ATTACHMENTS]:
        data = _fetch_image_bytes(att.storage_path)
        if data:
            out.append((data, att.content_type or 'image/png'))
    return out


def _build_review_prompt(req):
    """The strict-JSON triage prompt: kind/title/description + the clarification thread + the
    OWNER'S STEER + the adjudication rule + lane definitions → the reviewer JSON contract.

    The steer is the point of the 2026-07-30 change. Before it, a re-run rebuilt its prompt from
    the same description and the same answered questions, so it could only re-derive the same
    answer — the owner's actual judgement (``triage_note``) was never an input. Now a re-run
    reasons WITH the owner.

    ⚠ ``triage_note`` is owner-private and must never reach the org. That is safe here because the
    whole AI draft is owner-only too (``OrgRequestOrgSerializer`` is an explicit allowlist with no
    model passthrough) — and a test pins it, because "safe by construction" is worth asserting.
    """
    # The whole discussion, attributed — an answer to the OWNER's question carries different
    # weight from an answer to the reviewer's own, and a STATEMENT from the owner is a steer in
    # itself. INTERNAL comments are included deliberately: the reviewer is platform-side, and
    # the owner's judgement is exactly what a re-run should reason WITH rather than re-derive.
    # The org-facing serializer is what keeps any of this from reaching the requester.
    thread = [c for c in req.comments.all() if c.body.strip()]
    qa = '\n'.join(
        f'{_SPEAKER.get(c.author_kind, c.author_kind)}'
        f'{" (internal)" if c.visibility == VISIBILITY_INTERNAL else ""}: {c.body}'
        for c in thread)
    # Questions the owner has asked that are still UNANSWERED say what the owner is worried
    # about, even before a reply lands.
    pending_owner = [c.body for c in open_questions(req) if c.author_kind == AUTHOR_OWNER]
    steer = (req.triage_note or '').strip()
    return (
        'You are the AI reviewer triaging an organisation request for a software team. '
        'Return STRICT JSON ONLY, no prose, shaped as '
        '{"classification": "bug"|"feature", "lane": "small_change"|"sprint", '
        '"clarifying_questions": [up to 3 short strings], "rationale": short string}. '
        # ⚠ DO NOT ASK IT FOR HOURS (owner, 2026-07-30). It cannot see the codebase, so it
        # prices every request as greenfield: 24h for a sponsor invite largely already built
        # (referrals.py), 8h for a notification whose mailer already existed. Classification
        # and lane it gets right; the NUMBER was the one output with nothing behind it, and
        # once shown it became the figure the real quote had to argue against. The estimate
        # is now the engineer's, made from the code, and cited.
        'Do NOT estimate hours or duration, and do not state a number of hours in your '
        'rationale — you cannot see the codebase, so you cannot know what already exists. '
        'Classify it, choose the lane, and say what you would need to know. '
        'Ask a clarifying question ONLY when you genuinely cannot classify without '
        'it; ask none when the request is clear.\n\n'
        + _ADJUDICATION_RULE + '\n' + _LANE_DEFINITIONS + '\n\n'
        f'KIND (as declared): {req.kind}\n'
        f'TITLE: {req.title}\n'
        + (f'COMPONENT (area of the app): {req.component}\n' if req.component else '')
        + (f'URGENCY (the org\'s own signal): {req.urgency}\n' if req.urgency else '')
        + f'DESCRIPTION:\n{req.description}\n'
        + (f'\nSTEPS TO REPRODUCE:\n{req.steps_to_reproduce}\n' if req.steps_to_reproduce else '')
        + (f'\nCLARIFICATION THREAD:\n{qa}\n' if qa else '')
        + (f'\nTHE OWNER HAS ASKED, STILL UNANSWERED:\n'
           + '\n'.join(f'- {q}' for q in pending_owner) + '\n' if pending_owner else '')
        + (f"\nTHE OWNER'S OWN ASSESSMENT — treat this as authoritative and reason WITH it. If it "
           f"points at a different shape of solution from the one requested, say so and estimate "
           f"THAT shape:\n{steer}\n" if steer else '')
        + ('\nThe images supplied with this prompt are the submitter\'s screenshots. Read them: '
           'they usually show exactly where in the app the request applies.\n'
           if _has_attachments(req) else '')
    )


def _has_attachments(req):
    try:
        return bool(req.pk) and req.attachments.exists()
    except Exception:
        return False


def _parse_draft(raw):
    """Defensive parse of the AI reviewer's reply. Returns a dict:
      {ok, kind, lane, hours, questions, rationale, raw}
    ``ok`` is False for un-parseable output (the caller stores the raw text in ai_draft_note and
    NEVER 500s). Enums are clamped to the valid sets (unknown → ''); hours → Decimal or None."""
    text = (raw or '').strip()
    out = {'ok': False, 'kind': '', 'lane': '', 'hours': None,
           'questions': [], 'rationale': '', 'raw': text}
    if not text:
        return out
    # Strip a ```json fence if present.
    fenced = text
    if fenced.startswith('```'):
        fenced = re.sub(r'^```[a-zA-Z]*\n?', '', fenced)
        fenced = re.sub(r'\n?```$', '', fenced).strip()
    # Fall back to the first {...} block if there is leading/trailing prose.
    candidate = fenced
    if not candidate.startswith('{'):
        m = re.search(r'\{.*\}', candidate, re.DOTALL)
        if m:
            candidate = m.group(0)
    try:
        data = json.loads(candidate)
    except (ValueError, TypeError):
        return out
    if not isinstance(data, dict):
        return out

    kind = str(data.get('classification', '')).strip().lower()
    out['kind'] = kind if kind in VALID_KINDS else ''
    lane = str(data.get('lane', '')).strip().lower()
    out['lane'] = lane if lane in VALID_LANES else ''

    # `estimated_hours` is NO LONGER REQUESTED (see _build_review_prompt). A model that volunteers
    # one anyway is IGNORED rather than stored — so the field cannot quietly come back through a
    # chatty response. The column stays on the model, so historical drafts keep their values and
    # nothing needs a migration.

    questions = data.get('clarifying_questions') or []
    if isinstance(questions, list):
        out['questions'] = [str(q).strip()[:500] for q in questions[:3] if str(q).strip()]

    out['rationale'] = str(data.get('rationale', '')).strip()[:2000]
    out['ok'] = True
    return out


def run_ai_review(req):
    """Run the AI reviewer ONCE against ``req`` through ``contracts._gemini_generate`` (the ONLY
    seam; mocked in tests). Increments ``ai_run_count``, writes the ``ai_draft_*`` fields, and
    appends any GENUINELY NEW clarifying questions to the thread (owner-gated hours stay in the
    draft; questions flow to the requestee — the caller emails them).

    Returns ``{draft, new_questions}``. Raises:
      * ``ai_limit_reached`` when ``ai_run_count`` is already at ``AI_RUN_CAP``;
      * ``triage_ai_unconfigured`` / ``triage_ai_unavailable`` mapped from ``ContractsError``.

    Un-parseable output is NOT an error — the raw text is stored in ``ai_draft_note`` and no
    structured draft/question is written (manual triage always works)."""
    from . import contracts
    # The reviewer only runs while the request is open for triage (submitted/triaged); a quoted or
    # terminal request is a bad_transition, matching the manual re-run endpoint's gate.
    _check_transition(req, 'ai_rerun')
    if req.ai_run_count >= AI_RUN_CAP:
        raise OrgRequestError('ai_limit_reached')

    model = getattr(settings, 'REQUESTS_TRIAGE_MODEL', 'gemini-2.5-pro')
    from . import usage
    try:
        with usage.usage_context(organisation_id=getattr(req, 'organisation_id', None),
                                 source='requests_triage'):
            # Multimodal from 2026-07-30: the submitter's screenshots go WITH the prompt. Cost is
            # bounded by the two existing caps — ≤5 attachments × AI_RUN_CAP runs — and the
            # usage_context above already meters it as `requests_triage`.
            raw = contracts._gemini_generate(_build_review_prompt(req), model,
                                             images=_review_images(req))
    except contracts.ContractsError as e:
        # Map the seam's codes to the requests-space vocabulary. 'quiz_ai_unconfigured' (no key)
        # and 'quiz_ai_unavailable' (SDK missing) are the two the seam raises; anything else is
        # an availability failure from the model call.
        if e.code == 'quiz_ai_unconfigured':
            raise OrgRequestError('triage_ai_unconfigured')
        raise OrgRequestError('triage_ai_unavailable')
    except Exception:
        # A live call error (network / model) is an availability failure, never a 500 upstream.
        raise OrgRequestError('triage_ai_unavailable')

    draft = _parse_draft(raw)
    now = timezone.now()
    req.ai_run_count = req.ai_run_count + 1
    req.ai_draft_model = model[:50]
    req.ai_draft_at = now
    fields = ['ai_run_count', 'ai_draft_model', 'ai_draft_at', 'updated_at']

    if draft['ok']:
        req.ai_draft_kind = draft['kind']
        req.ai_draft_lane = draft['lane']
        req.ai_draft_hours = draft['hours']
        req.ai_draft_note = draft['rationale']
        fields += ['ai_draft_kind', 'ai_draft_lane', 'ai_draft_hours', 'ai_draft_note']
    else:
        # Garbage → keep the raw text for the owner's eye; leave the structured fields untouched.
        req.ai_draft_note = draft['raw'][:4000]
        fields += ['ai_draft_note']

    req.save(update_fields=list(dict.fromkeys(fields)))
    # AFTER the save: questions are now rows of their own, so they no longer ride along in
    # `update_fields`. A failure here cannot lose the draft that was just written.
    new_questions = _append_questions(req, draft['questions'])
    return {'draft': draft, 'new_questions': new_questions}


def _append_questions(req, questions):
    """Post the reviewer's clarifying questions as comments awaiting a reply, skipping any already
    in the thread (dedup on text) and keeping the open queue within ``MAX_OPEN_QUESTIONS``.

    Returns the newly-posted question strings — the caller emails them to the requester.
    """
    existing = {c.body.strip().casefold() for c in req.comments.all()}
    # Room is measured against the AI's OWN open questions, not the whole thread: an owner
    # question must not cost the reviewer a slot (see _open_ai_questions).
    room = MAX_OPEN_QUESTIONS - len(_open_ai_questions(req))
    added = []
    for q in questions:
        if room <= 0:
            break
        key = q.strip().casefold()
        if not key or key in existing:
            continue
        post_comment(req, None, q, author_kind=AUTHOR_AI,
                     visibility=VISIBILITY_SHARED, awaiting_reply=True)
        existing.add(key)
        added.append(q)
        room -= 1
    return added


def auto_run_ai_review(req):
    """Best-effort wrapper for the post-commit auto-run (create / answer / modify). Capped at
    ``AI_RUN_CAP``, swallows EVERYTHING (a Gemini failure never fails the user action), emails the
    requestee any new clarifying questions. Returns True iff a review actually ran."""
    try:
        result = run_ai_review(req)
    except OrgRequestError:
        return False
    except Exception:
        logger.warning('Requests: auto AI review failed for OrgRequest %s', req.pk, exc_info=True)
        return False
    if result['new_questions']:
        try:
            from . import emails
            emails.send_org_request_questions_email(req, result['new_questions'])
        except Exception:
            logger.warning('Requests: questions email failed for OrgRequest %s', req.pk,
                           exc_info=True)
    return True
