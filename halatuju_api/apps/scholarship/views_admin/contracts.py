"""Contract templates — the admin endpoints, moved verbatim from `views_admin.py` at H11.

⚠ `from .. import contracts` below and inside this module means `apps.scholarship.contracts`,
the SERVICE. This file is `views_admin.contracts`, the views. They are different modules and
the one extra dot is what keeps them apart.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
from rest_framework import status
from rest_framework.response import Response

from .base import _AdminBase


# ── Contract module (org-owned versioned bursary templates) — S3 admin API ────────
# Access: super or org_admin ONLY, org-fenced (a cross-org template is 404, never
# 403). Deploy is SUPER-only (org_admin -> 403). The service (apps.scholarship.
# contracts) owns the lifecycle + validation; these views are thin. generate-quiz
# is draft-only and calls the mockable Gemini seam (never live in tests).

_CONTRACT_RULE_LABELS = {
    'T1': 'Version + counterparty complete',
    'T2': 'Lawyer vetting recorded',
    'C1': 'Clauses numbered 1..N (contiguous)',
    'C2': 'English complete on every clause',
    'Q1': 'At least one quiz question',
    'Q2': 'Each quiz question is structurally valid',
    'Q3': 'No quiz on a non-candidate clause',
    'Q4': 'Quiz languages agree (same correct answer)',
    'S1': 'A default schedule row exists',
    'S2': 'Schedule row shapes are valid',
    'S3': 'Each schedule total is an allowed amount',
    'S4': 'Schedule totals match the award amounts',
    'P1': 'Uses only v1-supported options',
    'W1': 'Guarantor wording vs co-signer config',
    'W2': 'Some translations are incomplete',
    'W3': 'A clause body contains an RM figure',
}


def _contract_clause_dict(c):
    return {
        'order': c.order,
        'level': c.level,
        'heading_en': c.heading_en, 'heading_ms': c.heading_ms, 'heading_ta': c.heading_ta,
        'body_en': c.body_en, 'body_ms': c.body_ms, 'body_ta': c.body_ta,
        'is_quiz_candidate': c.is_quiz_candidate,
        'quiz_en': c.quiz_en, 'quiz_ms': c.quiz_ms, 'quiz_ta': c.quiz_ta,
        'quiz_generated_model': c.quiz_generated_model,
    }


def _contract_schedule_dict(r):
    return {
        'pathway': r.pathway, 'variant': r.variant,
        'label_en': r.label_en, 'label_ms': r.label_ms, 'label_ta': r.label_ta,
        'monthly_amount': str(r.monthly_amount), 'start_month': r.start_month,
        'paid_offsets': list(r.paid_offsets or []), 'sort_order': r.sort_order,
        'months': len(r.paid_offsets or []), 'total': str(r.total),
    }


def _contract_template_summary(t):
    return {
        'id': t.id, 'organisation': t.organisation.code, 'version': t.version,
        'status': t.status, 'languages_available': t.languages_available,
        'vetted_by_name': t.vetted_by_name, 'vetted_on': t.vetted_on,
        'deployed_by_at': t.deployed_by_at, 'created_at': t.created_at,
        'updated_at': t.updated_at,
    }


def _contract_template_detail(t):
    d = _contract_template_summary(t)
    d.update({
        'title_en': t.title_en, 'title_ms': t.title_ms, 'title_ta': t.title_ta,
        'preamble_en': t.preamble_en, 'preamble_ms': t.preamble_ms, 'preamble_ta': t.preamble_ta,
        'progress_standard_en': t.progress_standard_en, 'progress_standard_ms': t.progress_standard_ms,
        'progress_standard_ta': t.progress_standard_ta,
        'counterparty_name': t.counterparty_name, 'counterparty_title': t.counterparty_title,
        'counterparty_nric': t.counterparty_nric, 'counterparty_address': t.counterparty_address,
        'counterparty_notify_emails': t.counterparty_notify_emails or [],
        'parent_role': t.parent_role, 'parent_pin_required': t.parent_pin_required,
        'witness_policy': t.witness_policy,
        'vetting_attested_by_email': t.vetting_attested_by_email,
        'vetting_attested_at': t.vetting_attested_at,
        'created_by_email': t.created_by_email, 'submitted_by_email': t.submitted_by_email,
        'submitted_by_at': t.submitted_by_at, 'deployed_by_email': t.deployed_by_email,
        'archived_at': t.archived_at,
        'clauses': [_contract_clause_dict(c) for c in t.clauses.all().order_by('order')],
        'schedule': [_contract_schedule_dict(r) for r in t.schedule_rows.all()],
    })
    return d


def _contract_validation_dict(result):
    return {
        'ok': result.ok,
        'errors': [{'code': c, 'label': _CONTRACT_RULE_LABELS.get(c, c)} for c in result.errors],
        'warnings': [{'code': c, 'label': _CONTRACT_RULE_LABELS.get(c, c)} for c in result.warnings],
    }


def _contracts_err(e):
    body = {'error': e.code, 'code': e.code}
    if getattr(e, 'errors', None):
        body['errors'] = e.errors
    http = status.HTTP_403_FORBIDDEN if e.code == 'deploy_forbidden' else status.HTTP_400_BAD_REQUEST
    return Response(body, status=http)


class _ContractsBase(_AdminBase):
    """Gate + org-fenced template lookup for the Contract admin endpoints.
    super or org_admin only; deploy is super-only; cross-org -> 404."""

    def _not_found(self):
        return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

    def _contract_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'super') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None

    def _template_for(self, request, pk):
        """(template, admin, None) if the caller may access it; else (None, None, err).
        Cross-org -> 404 (no existence leak). Super global; org_admin own-org only."""
        admin, err = self._contract_admin(request)
        if err:
            return None, None, err
        from ..models import ContractTemplate
        template = (ContractTemplate.objects.filter(pk=pk)
                    .select_related('organisation')
                    .prefetch_related('clauses', 'schedule_rows').first())
        if template is None:
            return None, None, self._not_found()
        if not self.has_role(admin, 'super') and template.organisation_id != admin.owning_organisation_id:
            return None, None, self._not_found()   # cross-org 404
        return template, admin, None

    def _target_org(self, request, admin):
        """The org a new template belongs to: super -> the request 'organisation' code
        (required); org_admin -> own owning org."""
        from apps.courses.models import PartnerOrganisation
        if self.has_role(admin, 'super'):
            code = (request.data.get('organisation') or '').strip()
            if not code:
                return None, Response({'error': 'organisation_required', 'code': 'organisation_required'},
                                      status=status.HTTP_400_BAD_REQUEST)
            org = PartnerOrganisation.objects.filter(code=code).first()
            if org is None:
                return None, Response({'error': 'unknown_organisation', 'code': 'unknown_organisation'},
                                      status=status.HTTP_400_BAD_REQUEST)
            return org, None
        org = admin.owning_organisation
        if org is None:
            return None, self._deny_role()
        return org, None


class AdminContractTemplateListView(_ContractsBase):
    """GET list (org-fenced; super may ?organisation=<code>). POST create a DRAFT
    ({version, organisation? (super), copy_from?})."""
    def get(self, request):
        admin, err = self._contract_admin(request)
        if err:
            return err
        from ..models import ContractTemplate
        qs = (ContractTemplate.objects.select_related('organisation')
              .prefetch_related('clauses', 'schedule_rows')
              .order_by('organisation_id', '-created_at'))
        if not self.has_role(admin, 'super'):
            qs = qs.filter(organisation_id=admin.owning_organisation_id)
        else:
            org_f = (request.query_params.get('organisation') or '').strip()
            if org_f:
                qs = qs.filter(organisation__code=org_f)
        return Response({'templates': [_contract_template_summary(t) for t in qs]})

    def post(self, request):
        admin, err = self._contract_admin(request)
        if err:
            return err
        org, oerr = self._target_org(request, admin)
        if oerr:
            return oerr
        from .. import contracts
        from ..models import ContractTemplate
        copy_from = None
        cf = request.data.get('copy_from')
        if cf:
            copy_from = ContractTemplate.objects.filter(pk=cf, organisation=org).first()
            if copy_from is None:
                return Response({'error': 'copy_from_not_found', 'code': 'copy_from_not_found'},
                                status=status.HTTP_400_BAD_REQUEST)
        try:
            template = contracts.create_template(
                org, (request.data.get('version') or '').strip(),
                created_by_email=getattr(admin, 'email', '') or '', copy_from=copy_from)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        return Response(_contract_template_detail(template), status=status.HTTP_201_CREATED)


class AdminContractTemplateDetailView(_ContractsBase):
    """GET the full template. PATCH updates whitelisted config fields (draft only)."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        return Response(_contract_template_detail(template))

    def patch(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from .. import contracts
        fields = {k: v for k, v in request.data.items() if k in contracts._CONFIG_FIELDS}
        try:
            contracts.update_config(template, **fields)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractClausesView(_ContractsBase):
    """PUT the full ordered clause list (draft only)."""
    def put(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        clauses = request.data.get('clauses')
        if not isinstance(clauses, list):
            return Response({'error': 'clauses must be a list', 'code': 'bad_body'},
                            status=status.HTTP_400_BAD_REQUEST)
        from .. import contracts
        try:
            contracts.replace_clauses(template, clauses)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractScheduleView(_ContractsBase):
    """PUT the full payment schedule (draft only)."""
    def put(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        rows = request.data.get('rows')
        if not isinstance(rows, list):
            return Response({'error': 'rows must be a list', 'code': 'bad_body'},
                            status=status.HTTP_400_BAD_REQUEST)
        from .. import contracts
        try:
            contracts.replace_schedule(template, rows)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractGenerateQuizView(_ContractsBase):
    """POST — generate a clause's quiz via Gemini (draft only; billable, on-demand).
    The Gemini call is the mockable seam contracts._gemini_generate (never live in tests)."""
    def post(self, request, pk, order):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        clause = template.clauses.filter(order=order).first()
        if clause is None:
            return self._not_found()
        from .. import contracts
        try:
            contracts.generate_quiz(clause, model=request.data.get('model') or None)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        return Response(_contract_clause_dict(clause))


class AdminContractVettingView(_ContractsBase):
    """POST — record the lawyer-vetting attestation ({vetted_by_name, vetted_on}).
    The attesting admin's own email is stamped as the attester."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from django.utils.dateparse import parse_date
        from .. import contracts
        try:
            contracts.record_vetting(
                template,
                vetted_by_name=(request.data.get('vetted_by_name') or '').strip(),
                vetted_on=parse_date((request.data.get('vetted_on') or '').strip()),
                attested_by_email=(getattr(admin, 'email', '') or '').strip())
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractValidateView(_ContractsBase):
    """GET — the deploy-validation result (errors + warnings), mirroring the service."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from .. import contracts
        return Response(_contract_validation_dict(contracts.validate_for_deployment(template)))


class AdminContractSubmitView(_ContractsBase):
    """POST — draft -> pending_deployment (refuses when validation fails)."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from .. import contracts
        try:
            contracts.submit_for_deployment(
                template, submitted_by_email=getattr(admin, 'email', '') or '')
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractRevertView(_ContractsBase):
    """POST — pending_deployment -> draft (to edit further)."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from .. import contracts
        try:
            contracts.revert_to_draft(template)
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractDeployView(_ContractsBase):
    """POST — pending_deployment -> active (SUPER only; org_admin -> 403). Atomically
    archives the org's previous active version."""
    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        if not self.has_role(admin, 'super'):
            return self._deny_role()   # deploy is super-only
        from .. import contracts
        try:
            contracts.deploy(template, is_super=True,
                             deployed_by_email=getattr(admin, 'email', '') or '')
        except contracts.ContractsError as e:
            return _contracts_err(e)
        template.refresh_from_db()
        return Response(_contract_template_detail(template))


class AdminContractPreviewView(_ContractsBase):
    """GET — a rendered preview (HTML, or ?output=pdf). Sample particulars only.

    NOTE: the PDF selector is ``?output=pdf``, NOT ``?format=pdf`` — ``format`` is DRF's
    RESERVED content-negotiation query param, and ``?format=pdf`` makes DRF raise Http404
    (no 'pdf' renderer) during content negotiation, BEFORE this view runs (TD-163)."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from django.http import HttpResponse
        from .. import contracts
        html = contracts.render_preview_html(template, request.query_params.get('locale', 'en'))
        if request.query_params.get('output') == 'pdf':
            from .. import bursary
            try:
                pdf = bursary.generate_pdf(html)
            except bursary.BursaryError as e:
                return Response({'error': e.code, 'code': e.code},
                                status=status.HTTP_400_BAD_REQUEST)
            resp = HttpResponse(pdf, content_type='application/pdf')
            resp['Content-Disposition'] = f'inline; filename="contract_{template.version}.pdf"'
            return resp
        return HttpResponse(html, content_type='text/html')


class AdminContractQuizPreviewView(_ContractsBase):
    """GET — the comprehension checkpoints served for a locale (author preview)."""
    def get(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        from .. import contracts
        loc = contracts.resolve_locale(request.query_params.get('locale', 'en'), template)
        return Response({'template_version': template.version, 'locale_used': loc,
                         'checkpoints': contracts.quiz_checkpoints(template, loc)})


class AdminContractImportDocxView(_ContractsBase):
    """POST a .docx — parse it (deterministically from the doc's own heading/list
    numbering; Gemini only as a fallback for unstyled docs) into a PROPOSED clause list
    plus a detected title/preamble, for the author to review (draft-only). Nothing is
    saved and the uploaded file is NOT retained — on confirm the FE PUTs the reviewed
    clauses and fills a blank title/preamble. Failures return a code the FE degrades on."""
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        template, admin, err = self._template_for(request, pk)
        if err:
            return err
        if template.status != 'draft':
            return Response({'error': 'not_draft', 'code': 'not_draft'},
                            status=status.HTTP_400_BAD_REQUEST)
        upload = request.FILES.get('file')
        if upload is None:
            return Response({'error': 'no_file', 'code': 'no_file'},
                            status=status.HTTP_400_BAD_REQUEST)
        from .. import contracts
        try:
            proposal = contracts.segment_docx(upload.read())   # bytes only; never stored
        except contracts.ContractsError as e:
            return _contracts_err(e)
        # PROPOSED — the FE reviews, then PUTs clauses (+ fills blank title/preamble/party fields).
        return Response({
            'clauses': proposal['clauses'],
            'title': proposal.get('title', ''),
            'preamble': proposal.get('preamble', ''),
            'counterparty': proposal.get('counterparty', {}),
        })
