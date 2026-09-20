"""Sponsor terms — the authoring endpoints, moved verbatim from `views_admin.py` at H11.

⚠ `from .. import sponsor_terms as sponsor_terms_mod` below means
`apps.scholarship.sponsor_terms`, the SERVICE. This file is `views_admin.sponsor_terms`, the
views. The alias is the original one and is kept exactly so the moved bodies are unchanged.

Part of the `views_admin` package. Every name below is re-exported from
`views_admin/__init__.py`, so `urls.py` and every importer are unchanged.
"""
from rest_framework.response import Response

from .. import sponsor_terms as sponsor_terms_mod
from ..models import Sponsor
from .base import _AdminBase


# ── Sponsor terms (T2) ───────────────────────────────────────────────────────
# The versioned document a sponsor reads and accepts. Authoring only — nothing here is
# sponsor-facing; the wizard and the gate are T3.

def _terms_section_dict(sec):
    """Allowlist view of one section. Explicit fields — never model passthrough."""
    return {
        'order': sec.order,
        'heading_en': sec.heading_en, 'heading_ms': sec.heading_ms, 'heading_ta': sec.heading_ta,
        'body_en': sec.body_en, 'body_ms': sec.body_ms, 'body_ta': sec.body_ta,
        'is_quiz_candidate': sec.is_quiz_candidate,
        'quiz_en': sec.quiz_en, 'quiz_ms': sec.quiz_ms, 'quiz_ta': sec.quiz_ta,
        'quiz_generated_model': sec.quiz_generated_model,
    }


def _terms_summary_dict(terms):
    return {
        'id': terms.id,
        'version': terms.version,
        'status': terms.status,
        'title_en': terms.title_en,
        # The list table shows these two, so they belong on the summary. `languages_available`
        # walks the sections, which is why the list view prefetches them.
        'languages_available': terms.languages_available,
        'section_count': terms.sections.count(),
        'created_by_email': terms.created_by_email,
        'published_by_email': terms.published_by_email,
        'published_at': terms.published_at,
        'archived_at': terms.archived_at,
        'created_at': terms.created_at,
        'updated_at': terms.updated_at,
    }


def _terms_detail_dict(terms):
    d = _terms_summary_dict(terms)
    d.update({
        'title_ms': terms.title_ms, 'title_ta': terms.title_ta,
        'intro_en': terms.intro_en, 'intro_ms': terms.intro_ms, 'intro_ta': terms.intro_ta,
        'languages_available': terms.languages_available,
        'sections': [_terms_section_dict(x) for x in terms.sections.all()],
        'acceptance_count': terms.acceptances.count(),
    })
    return d


def _terms_validation_dict(result):
    return {
        'ok': result.ok,
        'errors': [{'code': c, 'label': sponsor_terms_mod.RULE_LABELS.get(c, c)}
                   for c in result.errors],
        'warnings': [{'code': c, 'label': sponsor_terms_mod.RULE_LABELS.get(c, c)}
                     for c in result.warnings],
    }


def _terms_err(exc):
    """A publish refusal is a 403 (you are not allowed); everything else is a 400 (fix it)."""
    payload = {'error': exc.code}
    if getattr(exc, 'detail', ''):
        payload['detail'] = exc.detail
    if getattr(exc, 'errors', None):
        payload['errors'] = [{'code': c, 'label': sponsor_terms_mod.RULE_LABELS.get(c, c)}
                             for c in exc.errors]
    status_code = 403 if exc.code == 'publish_forbidden' else 400
    return Response(payload, status=status_code)


class _SponsorTermsBase(_AdminBase):
    """Gate for the sponsor-terms panel — identical to the sponsor-emails gate, and for the same
    reason: authoring what every donor is bound by is an editorial power, not a reading one.
    Finance reads the sponsor list because money is its business; it does not write the terms.
    """
    def _terms_admin(self, request):
        admin = self.get_admin(request)
        if not admin:
            return None, self._deny()
        if not (self.has_role(admin, 'admin') or admin.role == 'org_admin'):
            return None, self._deny_role()
        return admin, None

    def _version_or_404(self, pk):
        from ..models import SponsorTermsVersion
        return (SponsorTermsVersion.objects
                .prefetch_related('sections')
                .filter(pk=pk)
                .first())


class AdminSponsorTermsListView(_SponsorTermsBase):
    """GET  .../admin/scholarship/sponsor-terms/  — every version, newest first.
    POST .../admin/scholarship/sponsor-terms/  {version, copy_from?} — a new draft.
    """
    def get(self, request):
        admin, err = self._terms_admin(request)
        if err:
            return err
        from ..models import SponsorTermsVersion
        rows = SponsorTermsVersion.objects.prefetch_related('sections').all()
        active = sponsor_terms_mod.active_version()
        return Response({
            'versions': [_terms_summary_dict(t) for t in rows],
            'active_version': active.version if active else '',
            'sponsor_count': Sponsor.objects.count(),
        })

    def post(self, request):
        admin, err = self._terms_admin(request)
        if err:
            return err
        copy_from = None
        if request.data.get('copy_from'):
            copy_from = self._version_or_404(request.data.get('copy_from'))
            if not copy_from:
                return Response({'error': 'not_found'}, status=404)
        try:
            terms = sponsor_terms_mod.create_version(
                version=request.data.get('version') or '',
                copy_from=copy_from,
                by_email=admin.email or '',
            )
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        return Response(_terms_detail_dict(terms), status=201)


class AdminSponsorTermsDetailView(_SponsorTermsBase):
    """GET / PATCH one version. PATCH edits the title and intro only; sections have their own
    endpoint because they are replaced wholesale rather than patched field by field."""
    def get(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        return Response(_terms_detail_dict(terms))

    def patch(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        fields = {k: v for k, v in request.data.items()
                  if k in sponsor_terms_mod._CONFIG_FIELDS}
        if not fields:
            return Response({'error': 'nothing_to_update'}, status=400)
        try:
            sponsor_terms_mod.update_intro(terms, fields, by_email=admin.email or '')
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsSectionsView(_SponsorTermsBase):
    """PUT .../sponsor-terms/<pk>/sections/ {sections: [...]} — replace them all.

    Orders are assigned server-side by position, so a client cannot produce a gap or a duplicate.
    """
    def put(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        try:
            sponsor_terms_mod.replace_sections(terms, request.data.get('sections'))
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        terms.refresh_from_db()
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsGenerateQuizView(_SponsorTermsBase):
    """POST .../sponsor-terms/<pk>/sections/<order>/generate-quiz/ — a Gemini draft. Billable."""
    def post(self, request, pk, order):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        section = terms.sections.filter(order=order).first()
        if not section:
            return Response({'error': 'not_found'}, status=404)
        try:
            sponsor_terms_mod.generate_quiz(section)
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        terms.refresh_from_db()
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsValidateView(_SponsorTermsBase):
    """GET .../sponsor-terms/<pk>/validate/ — the publish checklist, labels included."""
    def get(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        return Response(_terms_validation_dict(sponsor_terms_mod.validate_for_publish(terms)))


class AdminSponsorTermsPublishView(_SponsorTermsBase):
    """POST .../sponsor-terms/<pk>/publish/ — super or org_admin.

    Opened from super-only on 2026-07-28 at the owner's direction, so the programme lead can
    publish without going through the platform owner. A plain `admin` is still refused: authoring
    is staff work, but making a document binding on a donor is not.
    """
    def post(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        try:
            # super OR org_admin. A plain `admin` may AUTHOR but not make it binding: they are
            # staff doing the work, not the people answerable for what a donor is bound by.
            may_publish = bool(admin.is_super_admin) or admin.role == 'org_admin'
            sponsor_terms_mod.publish(terms, by_email=admin.email or '', allowed=may_publish)
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        terms.refresh_from_db()
        return Response(_terms_detail_dict(terms))


class AdminSponsorTermsImportDocxView(_SponsorTermsBase):
    """POST a .docx — parse it into a PROPOSED flat section list for the author to review.

    Nothing is saved and the upload is NOT retained. On confirm the frontend PUTs the reviewed
    sections, exactly as the contract importer works. Draft-only.
    """
    from rest_framework.parsers import MultiPartParser
    parser_classes = [MultiPartParser]

    def post(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        if terms.status != 'draft':
            return Response({'error': 'not_draft'}, status=400)
        upload = request.FILES.get('file')
        if upload is None:
            return Response({'error': 'no_file'}, status=400)
        try:
            proposal = sponsor_terms_mod.import_docx(upload.read())   # bytes only; never stored
        except sponsor_terms_mod.SponsorTermsError as exc:
            return _terms_err(exc)
        except Exception:
            # contracts.* raises ContractsError for an unreadable/empty document. Map anything
            # that escapes to one code rather than leaking a stack trace into the panel.
            return Response({'error': 'docx_unreadable'}, status=400)
        return Response(proposal)


class AdminSponsorTermsPreviewView(_SponsorTermsBase):
    """GET .../sponsor-terms/<pk>/preview/?locale=en — exactly what a sponsor will read.

    Serves `sponsor_terms.document()`, the SAME function the sponsor-facing page will call in T3,
    so the preview cannot drift from the real thing.
    """
    def get(self, request, pk):
        admin, err = self._terms_admin(request)
        if err:
            return err
        terms = self._version_or_404(pk)
        if not terms:
            return Response({'error': 'not_found'}, status=404)
        locale = request.query_params.get('locale') or 'en'
        return Response({
            'document': sponsor_terms_mod.document(terms, locale),
            'checkpoints': sponsor_terms_mod.quiz_checkpoints(terms, locale),
        })
