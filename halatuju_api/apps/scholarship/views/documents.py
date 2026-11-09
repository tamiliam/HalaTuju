"""The student's documents: sign an upload, record it, read it, remove it."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from halatuju.throttling import UploadRateThrottle
from .. import results_route
from ..document_snapshot import SNAPSHOT_ORDER
from ..models import ApplicantDocument
from ..results_review import slip_locked, SLIP_REQUEST_CODE
from ..serializers import (
    ApplicantDocumentSerializer,
    DocumentCreateSerializer,
    SignUploadSerializer,
)
from ..services import revert_if_profile_incomplete
from .common import _current_application
from .document_rules import _BYPASS_JUDGE_TYPES, _is_allowed_upload, RELATIONSHIP_DOC_TYPES


class DocumentSignUploadView(APIView):
    """POST /api/v1/scholarship/documents/sign-upload/ -> signed URL to PUT a file."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request):
        import uuid
        from ..storage import create_signed_upload_url, build_doc_key
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = SignUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc_type = serializer.validated_data['doc_type']
        # Org-prefixed key (Sprint 4): <org_id>/<app_id>/<doc_type>/<uuid>.
        path = build_doc_key(app, app.id, doc_type, uuid.uuid4().hex)
        # Audit A1.7 (SEC-18): signed no-overwrite — a URL can never replace the file at its key.
        url = create_signed_upload_url(path, upsert=False)
        if not url:
            return Response(
                {'error': 'Document storage is temporarily unavailable.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )
        return Response({'upload_url': url, 'storage_path': path, 'doc_type': doc_type})


class DocumentListCreateView(APIView):
    """GET list / POST record the caller's documents."""
    permission_classes = [SupabaseIsAuthenticated]
    throttle_classes = [UploadRateThrottle]

    def get(self, request):
        app = _current_application(request.user_id)
        # Student-facing listing: LIVE docs only — a superseded (replaced) copy is
        # version history for the officer view, never shown back to the student.
        # S4a review H1: an in-programme results slip is EVIDENCE, shown with its result, never here.
        docs = (ApplicantDocument.objects.filter(application=app, superseded_at__isnull=True)
                .exclude(request_code=SLIP_REQUEST_CODE) if app else ApplicantDocument.objects.none())
        # ⚠ THE LIMITS ARE SERVED, NEVER MIRRORED (Org Config Sprint E). The uploader used to
        # hold its own `8 * 1024 * 1024` so it could warn before a doomed upload; that number is
        # the ORGANISATION's now, so it rides here — the same read the POST below refuses on.
        # `app` is None before shortlisting, and `org_config.value(None, …)` is the platform
        # default, so an uploader with no application still draws a sane limit.
        from apps.courses import org_config
        org = app.owning_organisation if app else None
        return Response({
            'documents': ApplicantDocumentSerializer(docs, many=True).data,
            # A2.3: uploads still being read (staged ones too, which the list above does not show),
            # so the page can say "we are still reading N" instead of looking finished.
            'reading': (ApplicantDocument.objects.filter(application=app, read_state='pending').count()
                        if app else 0),
            'limits': {
                'max_doc_size_mb': org_config.value(org, 'max_doc_size_mb'),
                'max_docs_per_application': org_config.value(org, 'max_docs_per_application'),
                'max_other_docs': org_config.value(org, 'max_other_docs'),
            },
        })

    # EVERY document is single-instance: a re-upload REPLACES the existing copy in the
    # same slot (DB row + Supabase blob), keeping things simple — one IC, one salary slip,
    # one EPF, … per person. The sweep is scoped to the (doc_type, household_member) pair,
    # so re-uploading Mother's salary slip replaces Mother's, never Father's, and a
    # blank-member upload (student IC, STR-route doc) never touches the member-tagged ones.
    # (Retired the former str/salary_slip/epf multi-instance exception — user's call,
    # 2026-06-05; supersedes the S15 "several monthly slips" decision. See TD/decisions.)
    def _is_single_instance(self, doc_type, member):
        return True

    # The POST is a short run of named steps, in the order the checks have always run. Each
    # `_refuse_*` helper returns the Response to send, or None to carry on.
    @staticmethod
    def _refuse_bad_file(app, data):
        """Guardrails 0 and 1 and the slip lock: format, size, and a results slip's slot."""
        # Guardrail 0 (TD-080): accept images + PDF only — reject video/other junk.
        if not _is_allowed_upload(data.get('content_type'), data.get('original_filename')):
            return Response({'error': 'unsupported_format', 'code': 'unsupported_format'},
                            status=status.HTTP_400_BAD_REQUEST)
        from apps.courses import org_config
        # Guardrail 1: per-file size cap (the bytes go client→Storage via signed
        # URL, so this validates the reported size). Org Config Sprint E: the cap is the
        # ORGANISATION's, and `max_doc_size_bytes` is the only MB→bytes conversion — the
        # refusal reports the same number the uploader was served.
        _org = app.owning_organisation
        if (data.get('size') or 0) > org_config.max_doc_size_bytes(_org):
            return Response({'error': 'file_too_large',
                             'max_mb': org_config.value(_org, 'max_doc_size_mb')},
                            status=status.HTTP_400_BAD_REQUEST)
        if (data.get('request_code', '') or '') == SLIP_REQUEST_CODE:   # S4a H1: a results slip's slot is never replaced here
            return Response({'error': 'slip_locked', 'code': 'slip_locked'}, status=status.HTTP_409_CONFLICT)
        return None

    @staticmethod
    def _earner_tag(app, new_doc_type, new_member, new_request_code):
        """Slot model (TD-115): returns (str_income, member) — who an STR-route income doc belongs to."""
        # The STR route has a single earner, so PRE-CONSENT the backend AUTHORITATIVELY tags the
        # earner's income docs (str/parent_ic/salary_slip/epf) to that earner — by design, the STR
        # route clears on ONE parent's STR + IC (+ BC), so a blank-request income doc IS the earner's.
        #
        # AFTER consent (profile_completed_at set) that assumption is WRONG: we now collect EVERY
        # working member's details, and tagging is driven by the Check-2 doc request (which carries
        # the member). A father's payslip on a mother-STR household must NOT be force-tagged to the
        # mother (#80: exactly this happened — a force-tag mis-attributed the father's slip). So the
        # force-tag is GATED on pre-consent; post-consent a blank tag is left for the request member
        # or the name-on-doc guard below to resolve. (A request-keyed upload was never force-tagged.)
        # TD-309: an IC the student EXPLICITLY tagged to someone else (the card the Documents page
        # offers for the member who would settle whose STR it is) keeps that tag — an IC only
        # (review F2): a non-earner STR / slip / EPF is still force-tagged to the earner.
        _INCOME_EARNER_DOCS = {'str', 'parent_ic', 'salary_slip', 'epf'}
        str_income = (new_doc_type in _INCOME_EARNER_DOCS and not new_request_code
                      and (getattr(app, 'income_route', '') or '').strip() == 'str'
                      and (new_doc_type != 'parent_ic'
                           or new_member in ('', (getattr(app, 'income_earner', '') or '').strip()))
                      and app.profile_completed_at is None)   # pre-consent only
        if str_income:
            new_member = (getattr(app, 'income_earner', '') or '').strip()
        return str_income, new_member

    @staticmethod
    def _refuse_over_cap(app, new_doc_type, replaces):
        """Guardrail 2: the per-application caps. A replacement never grows the count."""
        from apps.courses import org_config
        _org = app.owning_organisation
        # 'other' (reviewer-requested extra) cap — a NEW 'other' slot beyond the cap is rejected.
        _max_other = org_config.value(_org, 'max_other_docs')
        if new_doc_type == 'other' and not replaces and ApplicantDocument.objects.filter(
                application=app, doc_type='other', superseded_at__isnull=True).count() >= _max_other:
            return Response({'error': 'other_doc_limit_reached', 'max': _max_other},
                            status=status.HTTP_400_BAD_REQUEST)
        _max_docs = org_config.value(_org, 'max_docs_per_application')
        if not replaces and ApplicantDocument.objects.filter(
                application=app, superseded_at__isnull=True).count() >= _max_docs:
            return Response({'error': 'doc_limit_reached', 'max': _max_docs},
                            status=status.HTTP_400_BAD_REQUEST)
        return None

    @staticmethod
    def _stale_ids(app, new_doc_type, new_request_code, slot_filter, sweep_members):
        """The live rows this upload supersedes, snapshotted BEFORE the create."""
        stale_ids = list(
            ApplicantDocument.objects.filter(**slot_filter).values_list('id', flat=True))
        # An OFFICER-REQUESTED re-upload (request_code set) also SUPERSEDES the student's
        # apply-form copy of the SAME (doc_type, member): the officer asked for a fresh/better
        # copy, so the old one is replaced (→ OTHER "Old / Replaced"), not kept as a parallel
        # slot. Scoped to the same member, so a cross-person request (e.g. the father's IC on a
        # mother-STR route) never clobbers another member's doc (TD-115).
        if new_request_code:
            apply_form_ids = ApplicantDocument.objects.filter(
                application=app, doc_type=new_doc_type, household_member__in=sweep_members,
                request_code='', superseded_at__isnull=True).values_list('id', flat=True)
            stale_ids += [i for i in apply_form_ids if i not in stale_ids]
        return stale_ids

    def post(self, request):
        app = _current_application(request.user_id)
        if app is None:
            return Response({'error': 'No shortlisted application.'}, status=status.HTTP_403_FORBIDDEN)
        serializer = DocumentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        new_doc_type = serializer.validated_data['doc_type']
        refusal = self._refuse_bad_file(app, serializer.validated_data)
        if refusal:
            return refusal
        new_member = serializer.validated_data.get('household_member', '') or ''
        # A reviewer-requested upload carries the officer ResolutionItem code — it makes this
        # document its OWN single-instance slot, so it can't overwrite the student's route doc
        # or another request. '' = the student's own apply-form/route doc (shared slot).
        new_request_code = serializer.validated_data.get('request_code', '') or ''
        str_income, new_member = self._earner_tag(app, new_doc_type, new_member, new_request_code)
        if str_income:
            serializer.validated_data['household_member'] = new_member
        single = self._is_single_instance(new_doc_type, new_member)
        # Slots this upload supersedes — the target (type, member, request_code), plus (STR income
        # docs) the legacy UNTAGGED copy. The request_code in the key is what lets multiple 'other'
        # docs (and cross-person income requests) coexist instead of overwriting each other.
        # `superseded_at__isnull=True` keeps this scoped to the LIVE row in the slot — an already-
        # superseded copy (version history) is never re-superseded and never counts toward a cap.
        sweep_members = [new_member, ''] if str_income else [new_member]
        slot_filter = dict(application=app, doc_type=new_doc_type,
                           household_member__in=sweep_members, request_code=new_request_code,
                           superseded_at__isnull=True)
        # A single-instance re-upload replaces an existing doc, so it doesn't count toward growth.
        # All caps count LIVE docs only — superseded history rows are retained but must not fill the quota.
        replaces = single and ApplicantDocument.objects.filter(**slot_filter).exists()
        refusal = self._refuse_over_cap(app, new_doc_type, replaces)
        if refusal:
            return refusal
        # Guardrail 3 (orphan-row prevention, app #80 EPF 2026-06-27): the bytes are PUT
        # client→Storage via the signed URL BEFORE this POST. If that PUT silently failed, we'd
        # record a row pointing at a blob that isn't there — a dead "view" link + an unreadable
        # doc that never resolves. Verify the object actually landed before recording it. Reject
        # ONLY on a CONFIRMED-missing blob (False); a storage hiccup during the check (None) must
        # not block a legitimate upload. Runs BEFORE the stale-sweep (a rejection never touches the
        # good copy). SEC-01: first, the key must be the one the upload step issued for THIS app + type.
        from ..storage import recorded_doc_key_refusal
        _refusal = recorded_doc_key_refusal(app, new_doc_type, serializer.validated_data.get('storage_path'))
        if _refusal:
            return Response({'error': _refusal, 'code': _refusal}, status=status.HTTP_400_BAD_REQUEST)
        # Single-instance re-upload REPLACES the live copy in the slot. Phase 2 (version history):
        # the old row is no longer HARD-deleted — it is stamped `superseded_at` and pointed at the
        # replacement (`superseded_by`), retaining an audit trail shown under the officer "Old /
        # Replaced" list; its Storage blob is deliberately KEPT (no sweep). Order matters (TD-115):
        # supersede FIRST, then create, in ONE transaction (`slot_writes`) — the slot's unique index
        # admits one live row, and a failed create rolls back, leaving the old live doc untouched.
        # Snapshot the stale ids BEFORE the create so the new row (same slot) is never superseded.
        stale_ids = []
        if single:
            stale_ids = self._stale_ids(app, new_doc_type, new_request_code, slot_filter, sweep_members)
        # STAGE → JUDGE → PROMOTE (owner 2026-07-09): a KEY NAMED doc is created STAGED (not-live) so
        # the existing proof keeps the prime slot until it is read + judged below; only a usable doc
        # that is at least as good is promoted. BYPASS/reviewer docs (bank_statement / income_support
        # _doc / other — the reviewer eyeballs them) keep the replace-first path.
        staged = single and (new_doc_type not in _BYPASS_JUDGE_TYPES)
        existing_live = (ApplicantDocument.objects.filter(id__in=stale_ids)
                         .order_by(*SNAPSHOT_ORDER).first() if staged else None)
        if new_doc_type == 'higher_results':   # S3a (D13) the results held; S4 a request's own kind
            serializer.validated_data['results_kind'] = results_route.upload_kind(app, new_request_code)
        # A staged doc is created not-live; the promote decision (upload_read) owns ALL slot mutation.
        # A concurrent upload into the same slot is retried once, then answered 409 (TD-115, never a 500).
        # A2.3 (TD-519): a type with a PAID read is recorded QUEUED (`read_plan` in the same insert)
        # and answered at once; the web asks for the read straight after, and the read-documents cron
        # catches any it never asks for. A type with no paid read is judged here, as before.
        from .. import slot_writes, upload_read
        queued = upload_read.needs_read(new_doc_type)
        if queued:
            serializer.validated_data.update(upload_read.queue_plan(staged, stale_ids, existing_live))
        doc = slot_writes.create_in_slot(app, serializer.validated_data, staged=staged,
                                         existing_live=existing_live, stale_ids=stale_ids, slot_filter=slot_filter)
        if doc is None:
            return Response({'error': 'upload_conflict', 'code': 'upload_conflict'}, status=status.HTTP_409_CONFLICT)
        if queued:
            return Response(upload_read.pending_payload(doc), status=status.HTTP_201_CREATED)
        data = upload_read.read_and_judge(app, doc, staged=staged, stale_ids=stale_ids,
                                          existing_live=existing_live)
        return Response(data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _maybe_extract_fields(app, doc, _vision, ocr, names, postcode, city, street, check_address, match, _settings, force=False):
        """Run Gemini doc-assist if the cost knob + hourly throttle allow; otherwise
        mark 'review_manually'. Never blocks the upload.

        ``force=True`` (the interactive upload) bypasses BOTH the cost knob and the
        hourly cap and always reads the document — so the file the student just
        submitted is scanned before its accept/keep-open verdict is computed, never
        deferred to a 'review_manually' state that would greenlight an unread doc.
        Abuse is still bounded by the per-request UploadRateThrottle + MAX_DOCS_PER_APPLICATION."""
        from datetime import timedelta
        from django.utils import timezone
        uncertain = (match.get('name_match') in ('not_found', 'unreadable')
                     or match.get('address_match') in ('not_found', 'unreadable'))
        # Relationship docs (birth cert) MUST extract — their verdict reads the structured
        # fields (child/mother names), which a name-presence "found" wouldn't surface. Never
        # let the cost knob skip them.
        always = doc.doc_type in RELATIONSHIP_DOC_TYPES
        if not force and getattr(_settings, 'DOC_ASSIST_ONLY_WHEN_UNCERTAIN', False) and not uncertain and not always:
            return  # clean upload + knob on → skip the billable call
        recent = ApplicantDocument.objects.filter(
            application=app, vision_fields_run_at__gte=timezone.now() - timedelta(hours=1)).count()
        if not force and recent >= getattr(_settings, 'DOC_ASSIST_RATE_LIMIT_PER_HOUR', 15):
            doc.vision_fields = {'fields': {}, 'warnings': [],
                                 'student_verdict': 'review_manually', 'error': 'rate_limited'}
            doc.vision_fields_run_at = timezone.now()
            doc.save(update_fields=['vision_fields', 'vision_fields_run_at'])
            return
        _vision.run_field_extraction_for_document(
            doc, names=names, postcode=postcode, city=city, street=street,
            check_address=check_address, ocr=ocr)


class DocumentReadView(APIView):
    """POST documents/<pk>/read/ — run a queued upload's read now (A2.3, TD-519).

    The web sends it straight after an upload answered ``reading: true``, so the student sees her
    result in the time the read takes. Safe to repeat: the queue's claim lets one caller read, and
    every other call (or a document already read) gets the row and its verdict as they stand. No
    throttle: the claim means a document is read at most ``MAX_ATTEMPTS`` times, whoever asks."""
    permission_classes = [SupabaseIsAuthenticated]

    def post(self, request, pk):
        from .. import upload_read
        doc = ApplicantDocument.objects.filter(pk=pk, application__profile_id=request.user_id).first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if doc.read_state == upload_read.PENDING:
            outcome, data = upload_read.run_read(doc.id)
            if outcome == 'done':
                return Response(data)
            doc.refresh_from_db()
        return Response(upload_read.answer_for(doc))


class DocumentDetailView(APIView):
    """DELETE the caller's document."""
    permission_classes = [SupabaseIsAuthenticated]

    def delete(self, request, pk):
        doc = ApplicantDocument.objects.filter(
            pk=pk, application__profile_id=request.user_id, superseded_at__isnull=True,
        ).first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
        if slip_locked(doc):   # S4a review H1: a results slip is evidence, whatever its review says
            return Response({'error': 'slip_locked', 'code': 'slip_locked'}, status=status.HTTP_409_CONFLICT)
        # An explicit "Remove" fully clears the slot INCLUDING its version history — this is a
        # deliberate student action, not a replace. Hard-delete the live row AND every superseded
        # ancestor it replaced (walk the `supersedes` chain transitively — a slot can have several
        # generations A←B←C), sweeping every Storage blob. (A re-upload soft-supersedes and keeps
        # the old blob; a Remove is the one path that truly deletes.)
        chain, frontier = [doc], [doc]
        while frontier:
            parents = list(ApplicantDocument.objects.filter(
                superseded_by__in=[d.id for d in frontier]))
            chain.extend(parents)
            frontier = parents
        from ..storage import delete_own_doc_objects   # SEC-01: a blob outside this app's prefix is kept
        paths = [d.storage_path for d in chain if d.storage_path]
        if paths:
            delete_own_doc_objects(doc.application, paths)
        application = doc.application
        # Self-referential FK is SET_NULL, so delete order is safe; one query clears the chain.
        ApplicantDocument.objects.filter(id__in=[d.id for d in chain]).delete()
        # Removing a compulsory document can drop a confirmed profile below
        # complete — un-confirm it so the status reflects reality.
        revert_if_profile_incomplete(application)
        # TD-079: re-open the resolved ticket whose gap this deletion brought back, then sync.
        from ..resolution import after_document_deleted
        after_document_deleted(application, doc.doc_type)
        return Response({'status': 'deleted'})
