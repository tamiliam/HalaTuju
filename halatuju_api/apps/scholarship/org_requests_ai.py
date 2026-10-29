"""The AI reviewer — the ONLY AI seam on an organisation request.

Moves only, split out of `org_requests.py` on 2026-10-29 because that file reached 1,086 lines
against a 1,081-line allowance once `approve()` learned to record WHO accepted a quote (TD-418),
and the 600-line standard asks for a split rather than for prose to be trimmed until the number
passes (`docs/lessons.md`, TD-413).

⚠ **A LEAF, almost.** It reaches back into `org_requests` for exactly two things —
`_check_transition` and `post_comment` — and both are imported INSIDE the functions that use them,
so there is no module-level cycle: `org_requests` imports this module at its top and re-exports
every name, which is what keeps `org_requests.run_ai_review(...)` working for the views, the model
and the tests.

⚠ **The mockable seams live elsewhere and did not move**: `contracts._gemini_generate` and
`vision._fetch_image_bytes`. Tests patch those two by path and call the functions here directly,
which is why re-exporting by name binding is safe.
"""
import json
import logging
import re

from django.conf import settings
from django.utils import timezone

from . import contracts, vision
from .models import OrgRequest
from .org_requests_shared import (AI_RUN_CAP, AUTHOR_AI, AUTHOR_ENGINEER, AUTHOR_ORG,
                                  AUTHOR_OWNER, MAX_ATTACHMENTS, VALID_KINDS,
                                  VALID_LANES, VISIBILITY_INTERNAL, VISIBILITY_SHARED,
                                  OrgRequestError)

logger = logging.getLogger(__name__)

# How each author is introduced to the reviewer in the prompt. The engineer's entry is what lets a
# re-run reason WITH the analysis instead of re-deriving it — which is the point of the steer.
_SPEAKER = {AUTHOR_OWNER: 'the owner', AUTHOR_ORG: 'the requester',
            AUTHOR_AI: 'you, earlier', AUTHOR_ENGINEER: 'the engineer'}


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
    from .org_requests import comments_for, open_questions  # see the docstring
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
    # ⚠ Imported HERE, not at the top: `org_requests` imports this module, so a module-level
    # import back would be a cycle. See this module's docstring.
    from .org_requests import _check_transition

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
    from .org_requests import MAX_OPEN_QUESTIONS, _open_ai_questions, post_comment

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
