"""The Requests space — the engineer's analysis, the quote, the schedule, and a request's
attachments. Moved verbatim from `views_admin.py` at code health H11; the request record and
its conversation are in `requests.py`.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
import logging

from rest_framework import status
from rest_framework.response import Response

from .requests import _OrgRequestsBase, _org_request_err

#: The package's logger name, spelled out — see the note in `requests.py`.
logger = logging.getLogger('apps.scholarship.views_admin')


class AdminOrgRequestAnalysisView(_OrgRequestsBase):
    """POST <pk>/analysis/ {body, estimated_hours?, cited_files[], authored_by?, repo_sha?} —
    stage the ENGINEER'S ANALYSIS as a DRAFT (TD-204). Super only.

    Posts NOTHING. The draft is invisible to the requesting organisation by construction — no
    org-facing serializer names `org_request_analyses` — and reaches them only when the owner
    approves it below. Owner ruling, 2026-07-31: *"you have to do the proper analysis and estimate
    the workload, and I want you to post as well, with my approval."*

    ⚠ `cited_files` is REQUIRED and non-empty. The estimate must cite its files; that is the only
    thing separating the engineer's number from the model's, and an analysis citing nothing is
    exactly what this record exists to prevent.
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
            org_requests.record_analysis(
                req, admin,
                body=request.data.get('body') or '',
                estimated_hours=request.data.get('estimated_hours'),
                cited_files=request.data.get('cited_files') or [],
                authored_by=request.data.get('authored_by') or '',
                repo_sha=request.data.get('repo_sha') or '',
                # A PROPOSED triage — prefills the owner's form and applies nothing. The request's
                # own kind/lane still change only when the owner presses Run.
                proposed_kind=request.data.get('proposed_kind') or '',
                proposed_lane=request.data.get('proposed_lane') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestAnalysisApproveView(_OrgRequestsBase):
    """POST <pk>/analysis/<aid>/approve/ — the owner approves; it enters the thread (TD-204).

    This is the control the whole record hangs on: the engineer stages, the owner approves, and
    only approval reaches the requester. Same split as `pool.publish_profile_to_pool` — preparing
    is free, publishing is gated. Super only.

    ⚠ The analysis is reached through `req.analyses`, never the model's top-level manager — the org
    fence IS the request lookup, so a cross-org id must 404 rather than resolve. (Naming that
    manager even in prose trips the static fence guard, which scans source text: see
    test_org_fence.TestOrgFenceStaticGuard.)

    Only the PROSE crosses to the requester. The cited files and the hours stay owner-side; see the
    model docstring for why neither is secrecy.
    """

    def post(self, request, pk, aid):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        analysis = req.analyses.filter(pk=aid).first()   # org-fence: scoped to this request
        if analysis is None:
            return self._not_found()
        from .. import org_requests
        try:
            org_requests.approve_analysis(analysis, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestWithdrawAnalysisView(_OrgRequestsBase):
    """POST <pk>/analysis/<aid>/withdraw/ — retire a DRAFT the engineer got wrong. Super only.

    Staging is POST-only and a draft could not be corrected or retracted, so fixing one meant
    staging a second and leaving the first in the approve list. Two near-identical drafts render
    with the same badge, the same hours and the same cited files, and `approve_analysis` does not
    refuse a second approval — so the stale one could reach the requester as a duplicate comment.

    ⚠ Same org fence as approve: reached through `req.analyses`, never the model's top-level
    manager, so a cross-org id 404s rather than resolving.
    """

    def post(self, request, pk, aid):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        analysis = req.analyses.filter(pk=aid).first()   # org-fence: scoped to this request
        if analysis is None:
            return self._not_found()
        from .. import org_requests
        try:
            org_requests.withdraw_analysis(analysis, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


class AdminOrgRequestTriageView(_OrgRequestsBase):
    """POST triage (submitted → triaged). Super only."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            req = org_requests.triage(
                req, admin, triaged_kind=(request.data.get('triaged_kind') or '').strip(),
                lane=(request.data.get('lane') or '').strip(),
                note=request.data.get('note') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestQuoteView(_OrgRequestsBase):
    """POST send a quote (triaged → quoted; feature only). Super only. Emails the submitter."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            req = org_requests.quote(
                req, admin, hours=request.data.get('hours'),
                margin_pct=request.data.get('margin_pct'),
                note=request.data.get('note') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from .. import emails
            emails.send_org_request_quote_email(req)
        except Exception:
            logger.warning('Requests: quote email failed for OrgRequest %s', req.pk, exc_info=True)
        return Response(self._serialize(admin, req))


class AdminOrgRequestRequoteView(_OrgRequestsBase):
    """POST re-quote a deferred request (deferred → quoted). Super only. Emails the submitter."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            req = org_requests.requote(
                req, admin, hours=request.data.get('hours'),
                margin_pct=request.data.get('margin_pct'),
                note=request.data.get('note') or '')
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        try:
            from .. import emails
            emails.send_org_request_quote_email(req)
        except Exception:
            logger.warning('Requests: re-quote email failed for OrgRequest %s', req.pk, exc_info=True)
        return Response(self._serialize(admin, req))


class AdminOrgRequestScheduleView(_OrgRequestsBase):
    """POST schedule (triaged-bug or approved → scheduled). Super only. Optional date."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from django.utils.dateparse import parse_date
        from .. import org_requests
        raw = (request.data.get('scheduled_for') or '').strip()
        sched = parse_date(raw) if raw else None
        try:
            req = org_requests.schedule(req, admin, scheduled_for=sched)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestDoneView(_OrgRequestsBase):
    """POST mark done (scheduled → done, terminal). Super only."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            req = org_requests.done(req, admin)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        return Response(self._serialize(admin, req))


class AdminOrgRequestAiRerunView(_OrgRequestsBase):
    """POST re-run the AI reviewer manually (no transition; submitted/triaged). Super only.
    Unlike the auto-run this surfaces the ContractsError as a 503 so the owner sees WHY."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._super_side(request, pk)
        if err:
            return err
        from .. import org_requests
        try:
            result = org_requests.run_ai_review(req)
        except org_requests.OrgRequestError as e:
            return _org_request_err(e)
        if result['new_questions']:
            try:
                from .. import emails
                emails.send_org_request_questions_email(req, result['new_questions'])
            except Exception:
                logger.warning('Requests: questions email failed for OrgRequest %s', req.pk,
                               exc_info=True)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))


# ── Screenshot attachments (Sprint 15.1, TD-172) ────────────────────────────────────
# Images ONLY, ≤5 per request, org-fenced. Every read/write reaches an attachment ONLY through the
# org-fenced request lookup (_requestee → _org_request_for → cross-org 404), and the storage key is
# requests/<org_id>/<request_id>/<uuid> so the download-URL org assertion (serializers_admin +
# storage.resolve_org_for_path) refuses a foreign blob. Attachments are queried via the request's
# related manager (req.attachments) — never a raw OrgRequestAttachment.objects query — so the fence
# rides on the already-fenced request (no separate pragma needed).


class AdminOrgRequestAttachmentSignUploadView(_OrgRequestsBase):
    """POST <pk>/attachments/sign-upload/ — a signed URL to PUT a screenshot. org_admin (own org) +
    super. The request must be non-terminal, and the count cap is enforced BEFORE we mint a URL."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from .. import org_requests
        # Evidence closes when the quote is ACCEPTED, not merely at a terminal status — changing
        # a screenshot under an accepted quote changes what was priced. See org_requests.can_attach.
        if not org_requests.can_attach(req):
            return Response({'error': 'request_closed', 'code': 'request_closed'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Count cap BEFORE signing (≤5 recorded attachments).
        if req.attachments.count() >= org_requests.MAX_ATTACHMENTS:
            return Response({'error': 'attachment_limit', 'code': 'attachment_limit',
                             'max': org_requests.MAX_ATTACHMENTS},
                            status=status.HTTP_400_BAD_REQUEST)
        import uuid
        from ..storage import create_signed_upload_url, build_request_attachment_key
        path = build_request_attachment_key(req.organisation_id, req.id, uuid.uuid4().hex)
        url = create_signed_upload_url(path)
        if not url:
            return Response({'error': 'storage_unavailable', 'code': 'storage_unavailable'},
                            status=status.HTTP_503_SERVICE_UNAVAILABLE)
        return Response({'upload_url': url, 'storage_path': path})


class AdminOrgRequestAttachmentCreateView(_OrgRequestsBase):
    """POST <pk>/attachments/ — record an attachment row after the PUT. org_admin (own org) + super.
    Validates: non-terminal request, IMAGE allowlist (no pdf), size ≤ the organisation's
    `max_doc_size_mb` (Org Config Sprint E — same cap its students answer to), count cap,
    and the storage_path prefix must match THIS request (a foreign path is rejected)."""

    def post(self, request, pk):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from .. import org_requests
        # Evidence closes when the quote is ACCEPTED, not merely at a terminal status — changing
        # a screenshot under an accepted quote changes what was priced. See org_requests.can_attach.
        if not org_requests.can_attach(req):
            return Response({'error': 'request_closed', 'code': 'request_closed'},
                            status=status.HTTP_400_BAD_REQUEST)
        storage_path = (request.data.get('storage_path') or '').strip()
        content_type = (request.data.get('content_type') or '').strip()
        original_filename = (request.data.get('original_filename') or '').strip()
        try:
            size = int(request.data.get('size') or 0)
        except (TypeError, ValueError):
            size = 0
        # Path prefix must belong to THIS request (foreign-path rejection).
        from ..storage import build_request_attachment_key
        expected_prefix = build_request_attachment_key(req.organisation_id, req.id, '')
        if not storage_path.startswith(expected_prefix) or storage_path == expected_prefix:
            return Response({'error': 'bad_path', 'code': 'bad_path'},
                            status=status.HTTP_400_BAD_REQUEST)
        # IMAGE allowlist only (no pdf).
        if not org_requests.is_allowed_attachment(content_type, original_filename):
            return Response({'error': 'unsupported_format', 'code': 'unsupported_format'},
                            status=status.HTTP_400_BAD_REQUEST)
        # The size cap is the ORGANISATION's here too (Org Config Sprint E) — this attachment
        # belongs to that organisation's own support request, so it answers to the same number
        # its students' uploads do.
        from apps.courses import org_config
        if size > org_config.max_doc_size_bytes(req.organisation):
            return Response({'error': 'file_too_large', 'code': 'file_too_large',
                             'max_mb': org_config.value(req.organisation, 'max_doc_size_mb')},
                            status=status.HTTP_400_BAD_REQUEST)
        # Count cap at record too (another attachment may have landed since sign).
        if req.attachments.count() >= org_requests.MAX_ATTACHMENTS:
            return Response({'error': 'attachment_limit', 'code': 'attachment_limit',
                             'max': org_requests.MAX_ATTACHMENTS},
                            status=status.HTTP_400_BAD_REQUEST)
        req.attachments.create(
            storage_path=storage_path, original_filename=original_filename[:255],
            content_type=content_type[:100], size=size, uploaded_by=admin)
        req.refresh_from_db()
        return Response(self._serialize(admin, req), status=status.HTTP_201_CREATED)


class AdminOrgRequestAttachmentDeleteView(_OrgRequestsBase):
    """DELETE <pk>/attachments/<att_id>/ — remove an attachment while the request is non-terminal.
    org_admin (own org) + super; the attachment is reached through the org-fenced request, so
    another org's attachment is 404. Deletes the row + best-effort blob sweep."""

    def delete(self, request, pk, att_id):
        gate = self._flag()
        if gate:
            return gate
        admin, req, err = self._requestee(request, pk, allow_super=True)
        if err:
            return err
        from .. import org_requests
        # Evidence closes when the quote is ACCEPTED, not merely at a terminal status — changing
        # a screenshot under an accepted quote changes what was priced. See org_requests.can_attach.
        if not org_requests.can_attach(req):
            return Response({'error': 'request_closed', 'code': 'request_closed'},
                            status=status.HTTP_400_BAD_REQUEST)
        # Scoped to THIS (already org-fenced) request — a foreign attachment id is 404.
        att = req.attachments.filter(pk=att_id).first()
        if att is None:
            return self._not_found()
        path = att.storage_path
        att.delete()
        try:
            from ..storage import delete_objects
            delete_objects([path])
        except Exception:
            logger.warning('Requests: attachment blob sweep failed for %s', path, exc_info=True)
        req.refresh_from_db()
        return Response(self._serialize(admin, req))
