"""The Requests space — a request and its conversation. Moved verbatim from `views_admin.py`
at code health H11. The analysis, the quote and the delivery are in `requests_delivery.py`.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
import logging

from django.conf import settings
from django.db.models import Count, Q
from rest_framework import status
from rest_framework.response import Response

from ..models import OrgRequest
from ..serializers_admin import OrgRequestOrgSerializer, OrgRequestOwnerSerializer
from .base import _AdminBase

#: THE PACKAGE'S LOGGER NAME, SPELLED OUT. `__name__` here would read
#: `apps.scholarship.views_admin.requests`, and twelve tests assert on
#: `apps.scholarship.views_admin` — an audit line that moves logger is an audit line nobody
#: is watching any more. Every submodule in this package does the same.
logger = logging.getLogger('apps.scholarship.views_admin')


# ── Requests space (Sprint 15) ─────────────────────────────────────────────────────
# The org-section "Requests" area: bug/feature forms → AI reviewer → owner-gated hours
# quotes. Ships DARK behind REQUESTS_ENABLED — every route 404s while the flag is off
# (the FE hub card is hidden by the same 404-probe, so there is no client flag). Service =
# apps.scholarship.org_requests; org-fenced via _org_request_for (cross-org 404), role-gated
# per the endpoint table (org-side vs super-only). All classes classified in
# test_org_fence.py FENCED_OR_EXEMPT and the OrgRequest model is WATCHED (its raw admin
# queries below all carry an # org-fence pragma).

def _org_request_err(e):
    """Map an OrgRequestError code to a 4xx. bad_transition/bug_is_free/... are 4xx; the two
    AI-availability codes are 503 (the model is unconfigured/unavailable, not the caller's fault)."""
    if e.code in ('triage_ai_unconfigured', 'triage_ai_unavailable'):
        return Response({'error': e.code, 'code': e.code},
                        status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'error': e.code, 'code': e.code}, status=status.HTTP_400_BAD_REQUEST)


class _OrgRequestsBase(_AdminBase):
    """Shared flag/role/org gate for the Requests-space endpoints.

    404-FIRST dark ship: with ``REQUESTS_ENABLED`` off, ``_flag`` short-circuits every handler to
    404 BEFORE any auth/role work — the same shape as the sponsor-pool flag gate — so the feature
    leaks no existence signal while dark. When the flag is on, role denials are REAL 403s and a
    cross-org id is 404 (no existence leak)."""

    def _flag(self):
        """Returns an error Response (404) when the feature is dark, else None."""
        if not getattr(settings, 'REQUESTS_ENABLED', False):
            return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)
        return None

    def _not_found(self):
        return Response({'error': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

    def _org_request_for(self, admin, pk):
        # org-fence: fetch then re-gate to the caller's organisation (super global); a cross-org
        # id returns None -> 404 (no existence leak). This is the ONLY OrgRequest.objects read.
        req = (OrgRequest.objects
               .select_related('organisation', 'submitted_by').filter(pk=pk).first())
        if req is None:
            return None
        if self.has_role(admin, 'super'):
            return req
        if req.organisation_id != admin.owning_organisation_id:
            return None
        return req

    # ── role prologues (flag already assumed checked by the caller) ──────────────
    def _org_side(self, request):
        """Caller must be an org_admin or super (the roles that OPEN the Requests area)."""
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (admin.is_super or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None

    def _requestee(self, request, pk, *, allow_super=False):
        """A requestee WRITE (answer/defer/modify → org_admin only; approve/decline → +super).
        Returns (admin, req, None) or (None, None, err)."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not ((admin.role == 'org_admin') or (allow_super and admin.is_super)):
            return None, None, self._deny_role()
        req = self._org_request_for(admin, pk)
        if req is None:
            return None, None, self._not_found()
        return admin, req, None

    def _super_side(self, request, pk):
        """A super-only WRITE (triage/quote/requote/schedule/done/ai-rerun)."""
        admin = self.get_admin(request)
        if not admin:
            return None, None, self._deny()
        if not admin.is_super:
            return None, None, self._deny_role()
        req = self._org_request_for(admin, pk)
        if req is None:
            return None, None, self._not_found()
        return admin, req, None

    def _serialize(self, admin, req):
        """Super sees the OWNER payload (incl. the AI draft + triage); everyone else the
        allowlist ORG payload (no ai_* / triage ever)."""
        if self.has_role(admin, 'super'):
            return OrgRequestOwnerSerializer(req).data
        return OrgRequestOrgSerializer(req).data


class AdminOrgRequestListView(_OrgRequestsBase):
    """GET list (org-fenced) . POST create a request. org_admin + super."""

    def get(self, request):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        # org-fence: list scoped to the caller's organisation (super global) via _org_scoped.
        qs = self._org_scoped(
            OrgRequest.objects.select_related('organisation', 'submitted_by'),
            admin, field='organisation_id')
        return Response({'requests': [self._serialize(admin, r) for r in qs]})

    def post(self, request):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        from .. import org_requests
        # Whose org the request belongs to: the org_admin's own; a super must name organisation_id.
        if admin.is_super:
            org_id = request.data.get('organisation_id')
            from apps.courses.models import PartnerOrganisation
            org = PartnerOrganisation.objects.filter(pk=org_id).first() if org_id else None
            if org is None:
                return Response({'error': 'org_required', 'code': 'org_required'},
                                status=status.HTTP_400_BAD_REQUEST)
        else:
            org = admin.owning_organisation
            if org is None:
                return Response({'error': 'no_org', 'code': 'no_org'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            req = org_requests.create_request(
                org, admin, kind=(request.data.get('kind') or '').strip(),
                title=request.data.get('title') or '',
                description=request.data.get('description') or '',
                component=request.data.get('component') or '',
                urgency=request.data.get('urgency') or '',
                steps_to_reproduce=request.data.get('steps_to_reproduce') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        # Best-effort post-commit: notify the owner + auto-run the AI reviewer (never fails create).
        try:
            from .. import emails
            emails.send_org_request_submitted_email(req)
        except Exception:
            logger.warning('Requests: submit-notify failed for OrgRequest %s', req.pk, exc_info=True)
        org_requests.auto_run_ai_review(req)
        req.refresh_from_db()
        return Response(self._serialize(admin, req), status=status.HTTP_201_CREATED)


class AdminOrgRequestCountView(_OrgRequestsBase):
    """GET {count} for the nav badge. Super: requests waiting on US — SUBMITTED (awaiting triage)
    OR a triaged FEATURE with no approved analysis (TD-205). org_admin: own org's requests that
    need THEIR attention — quoted (awaiting accept) OR carrying an unanswered clarifying question.
    org_admin + super."""

    def get(self, request):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        from django.db.models import Count, Q
        if self.has_role(admin, 'super'):
            # TD-205: "waiting on us" is BOTH ends of the engineer's involvement. Untriaged is the
            # obvious half. The other is a triaged FEATURE with no approved analysis — it cannot be
            # quoted at all (`analysis_required` refuses), so it is stuck BY CONSTRUCTION and
            # nothing else says so. A triaged BUG is deliberately NOT counted: a bug is free and
            # schedulable straight from triage, so it waits on a decision, not on an analysis.
            #
            # A filtered Count, and one annotate only (two multi-valued annotates multiply each
            # other — this project has been bitten by that).
            #
            # A single `.exclude(analyses__approved_at__isnull=False, analyses__superseded_at__
            # isnull=True)` is EQUIVALENT here and was measured to be, not assumed: Django compiles
            # one multi-condition exclude into a single NOT EXISTS with both conditions on the same
            # joined row, which is exactly "has no approved, live analysis". The multi-valued
            # negation trap is real but belongs to CHAINED `.exclude(a).exclude(b)`, which asks two
            # independent questions of two different rows. Count is kept for being explicit about
            # the zero and for not needing `.distinct()`, NOT because exclude is broken — an
            # earlier version of this comment claimed it was, and a bite-check disproved it.
            #
            # An approved analysis always carries ≥1 cited file because `approve_analysis` refuses
            # otherwise, so this agrees with `org_requests.approved_analysis` without re-testing it.
            # org-fence: super is global by design for the triage badge.
            waiting = OrgRequest.objects.annotate(
                live_analyses=Count('analyses', filter=Q(analyses__approved_at__isnull=False,
                                                         analyses__superseded_at__isnull=True)),
            ).filter(
                Q(status='submitted')
                | Q(status='triaged', triaged_kind='feature', live_analyses=0)
            )
            return Response({'count': waiting.count()})
        # TD-201: "needs you" is a quote awaiting a decision, or a question awaiting a reply —
        # the latter is now a comment row, so it is one subquery instead of walking a JSON list
        # per request.
        # org-fence: own org only (org_admin). Kept ADJACENT to the query — the static guard reads
        # a 200-char window, so an explanation wedged in between silently un-fences it.
        qs = OrgRequest.objects.filter(
            organisation_id=admin.owning_organisation_id,
        ).exclude(status__in=('done', 'declined'))
        return Response({'count': qs.filter(
            Q(status='quoted') | Q(comments__awaiting_reply=True)
        ).distinct().count()})


class AdminOrgRequestDetailView(_OrgRequestsBase):
    """GET one request (org_admin own else 404; super). org_admin + super."""

    def get(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, err = self._org_side(request)
        if err:
            return err
        req = self._org_request_for(admin, pk)
        if req is None:
            return self._not_found()
        return Response(self._serialize(admin, req))


class AdminOrgRequestAnswerView(_OrgRequestsBase):
    """POST answer a clarifying question (org_admin own org). No status transition."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            # ⚠ `comment_id` AND `admin`, and both were missing. This call still passed `index=`
            # — the parameter the service dropped on 2026-07-31 when clarifications became
            # comments — so EVERY answer raised TypeError before the service was reached, and the
            # `except OrgRequestError` below could not see it. Answering was 500-ing for every
            # organisation on every request for eighteen days (BrightPath request #15).
            req = org_requests.answer_clarification(
                req, request.data.get('answer') or '',
                comment_id=request.data.get('comment_id'),
                admin=admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        # Best-effort: notify the owner + re-run the AI reviewer on the new answer.
        try:
            from .. import emails
            emails.send_org_request_answered_email(req)
        except Exception:
            logger.warning('Requests: answer-notify failed for OrgRequest %s', req.pk, exc_info=True)
        org_requests.auto_run_ai_review(req)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestApproveView(_OrgRequestsBase):
    """POST accept a quote (quoted/deferred → approved). org_admin own org, or super."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from .. import org_requests
        by_role = 'super' if admin.is_super else 'org_admin'
        try:
            req = org_requests.approve(req, admin, by_role=by_role)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from .. import emails
            emails.send_org_request_accepted_email(req)
        except Exception:
            logger.warning('Requests: accept-notify failed for OrgRequest %s', req.pk, exc_info=True)
        return Response(self._serialize(admin, req))


class AdminOrgRequestDeferView(_OrgRequestsBase):
    """POST defer a quote (quoted → deferred). org_admin own org."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            req = org_requests.defer(req, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestModifyView(_OrgRequestsBase):
    """POST modify (amend the description; quoted/deferred → submitted). org_admin own org."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            req = org_requests.modify(req, admin, description=request.data.get('description') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        org_requests.auto_run_ai_review(req)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestDeclineView(_OrgRequestsBase):
    """POST decline/withdraw (→ declined, terminal). org_admin own org (withdraw, reason
    optional), or super (decline, reason required)."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from .. import org_requests
        by_role = 'super' if admin.is_super else 'org_admin'
        try:
            req = org_requests.decline(req, admin, by_role=by_role,
                                       reason=request.data.get('reason') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestAskView(_OrgRequestsBase):
    """POST <pk>/ask/ {question} — the OWNER asks the requester something. Super only.

    Until now the clarification thread ran one way: the AI asked, the requester answered, and the
    owner watched by email. So a judgement about the SHAPE of a request — "adding a sponsor
    directly would bypass the terms and consent; would an invite do?" — had nowhere to go, because
    `triage_note` is private to the owner and the org never sees it.

    Same window as `/answer/` and the AI's own questions (submitted/triaged): a quoted request
    must not grow new questions, because the quote was priced against what was known when it
    was sent.

    Emails the requester through the SAME helper the AI's questions use, so a question reads the
    same to them however it was authored — only the on-screen attribution differs.
    """

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            question = org_requests.ask_question(req, admin, request.data.get('question') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from .. import emails
            emails.send_org_request_questions_email(req, [question])
        except Exception:
            logger.warning('Requests: owner-question notify failed for OrgRequest %s',
                           req.pk, exc_info=True)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestCommentView(_OrgRequestsBase):
    """POST <pk>/comments/ {body, visibility?} — post to the DISCUSSION (TD-201).

    The verb the module never had. Until now exactly ONE action reached the requester: `ask` a
    question. So a conclusion — "here is what we would build, and why" — had to travel as a quote
    note or not at all, and the owner's judgement about the shape of a request left the system.

    ACTOR: super OR any org_admin of the owning organisation (owner ruling, 2026-07-31). They can
    already READ the request — requests are org-fenced, and a cross-org pk is a 404 — so this adds
    no visibility, it lets the people already in the room speak. `_requestee(allow_super=True)` is
    exactly that rule; the org fence is the request lookup, not a check here.

    ⚠ `visibility='internal'` is SUPER-ONLY and the service refuses it for an org author. Two
    layers on purpose: a serializer allowlist cannot save you here, because the leak would be a
    ROW the org may not read rather than a field — see `org_requests.comments_for`.

    WINDOW: until the request is TERMINAL, wider than `OPEN_FOR_SHAPING`. Discussion continues
    after assignment (the owner's Bugzilla framing); it is asking a NEW QUESTION that still stops
    at the quote, because a question can re-price and a remark cannot.
    """

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from .. import org_requests
        visibility = (request.data.get('visibility') or org_requests.VISIBILITY_SHARED).strip()
        # An org_admin may not post an internal note. Refused HERE as well as in the service so
        # the endpoint's contract is readable without following the call.
        if visibility == org_requests.VISIBILITY_INTERNAL and not admin.is_super:
            return Response({'error': 'forbidden', 'code': 'forbidden'},
                            status=status.HTTP_403_FORBIDDEN)
        author_kind = (org_requests.AUTHOR_OWNER if admin.is_super
                       else org_requests.AUTHOR_ORG)

        # ⚠ THE ENGINEER MAY SPEAK DIRECTLY, BUT ONLY WHERE THE ORGANISATION CANNOT HEAR IT
        # (2026-08-01). Authorship is otherwise derived from the caller, which meant a note the
        # ENGINEER wrote — a triage recommendation, say — arrived stamped as the OWNER, because it
        # is the owner's token making the call. TD-204 already refused that trade for approved
        # analyses ("attributing it to the approver is a lie about who wrote it"); the same
        # objection applies to a note the owner did not write.
        #
        # ⚠ INTERNAL ONLY, and the pairing is the whole control. Engineer prose that REACHES the
        # requester still has exactly one route — stage an analysis, the owner approves — so this
        # cannot become a side door around that gate. An internal note is owner-visible by
        # construction (`org_requests.comments_for` filters the ROW), so there is nothing for an
        # approval step to protect.
        #
        # ⚠ THE RULE LIVES HERE, NOT IN `post_comment`, and that is deliberate rather than lazy:
        # `approve_analysis` legitimately posts engineer + SHARED through the same service, so a
        # service-level "engineer implies internal" would break the one path this exists to
        # protect. What is enforced here is the HTTP contract — who may claim to be whom — while
        # the domain rule (engineer + shared happens only on approval) stays in the service.
        claimed = (request.data.get('author') or '').strip()
        if claimed:
            if not admin.is_super or claimed != org_requests.AUTHOR_ENGINEER:
                return Response({'error': 'forbidden', 'code': 'forbidden'},
                                status=status.HTTP_403_FORBIDDEN)
            if visibility != org_requests.VISIBILITY_INTERNAL:
                return Response({'error': 'engineer_must_be_internal',
                                 'code': 'engineer_must_be_internal'},
                                status=status.HTTP_400_BAD_REQUEST)
            author_kind = org_requests.AUTHOR_ENGINEER
        try:
            org_requests.post_comment(
                # ⚠ `author_admin=None` for the engineer, exactly as `approve_analysis` does.
                # `_comment_dicts` exposes `author_name`, so passing the calling admin would print
                # the OWNER'S NAME beside an "Engineer" badge — the same lie in a second field,
                # and the one a reader would actually see.
                req, None if author_kind == org_requests.AUTHOR_ENGINEER else admin,
                request.data.get('body') or '',
                author_kind=author_kind, visibility=visibility)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))
