"""Gopal's coaching on a document and on an income cluster."""
from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView

from halatuju.middleware.supabase_auth import SupabaseIsAuthenticated
from ..models import ApplicantDocument
from .common import _current_application, _log_coach_serve


class DocumentHelpView(APIView):
    """GET a warm "Cikgu Gopal" helper message for one of the caller's documents.

    Reacts to the document's already-decided soft verdict (mismatch / unreadable) with a
    short, encouraging note that explains the fix — it never writes the student's answers
    and never sees any admin/score data (the engine only receives doc-type + verdict +
    first name). Soft by construction: nothing to help with → source 'none'; AI down or
    throttled → source 'fallback' (the frontend shows pre-written copy keyed by `verdict`).
    """
    permission_classes = [SupabaseIsAuthenticated]

    def get(self, request, pk):
        doc = ApplicantDocument.objects.filter(
            pk=pk, application__profile_id=request.user_id,
        ).select_related('application', 'application__profile').first()
        if doc is None:
            return Response({'error': 'Not found'}, status=status.HTTP_404_NOT_FOUND)

        from .. import help_engine
        verdict = help_engine.verdict_for_document(doc)
        if not verdict:
            _log_coach_serve('doc', doc.application_id, 'none', '')
            return Response({'message': '', 'source': 'none'})

        # Specific academic diffs so the coach can NAME the subject(s) + grades (not just "a grade
        # differs") and deep-link to the grades page (owner 2026-07-08; typed subjects not on the
        # slip since request #62). The same slip check; empty for every other verdict.
        from ..slip_coach import coach_detail
        detail = coach_detail(doc, verdict)

        # Throttle the billable call (never block — decisions.md "throttle the AI").
        # Per-application hourly cap via the default cache; degrade to the FE fallback copy.
        from django.conf import settings as _settings
        from django.core.cache import cache
        from django.utils import timezone
        cap = getattr(_settings, 'DOC_HELP_RATE_LIMIT_PER_HOUR', 20)
        key = f'help_coach:{doc.application_id}:{timezone.now():%Y%m%d%H}'
        if cache.get(key, 0) >= cap:
            _log_coach_serve('doc', doc.application_id, 'fallback', verdict)
            return Response({'message': '', 'source': 'fallback', 'verdict': verdict, **detail})
        cache.set(key, cache.get(key, 0) + 1, 3600)

        from ..profile_engine import _resolve_language
        language = _resolve_language(doc.application, request.query_params.get('lang'))
        from .. import branding as _branding, help_cache
        from .. import usage as _usage
        # Bill the coach's Gemini call to the tenant. The engine's OWN signature stays sealed
        # (see test_engine_signature_is_structurally_firewalled) — attribution rides the ambient
        # usage_context, which the engine's inner `usage_context(source='doc_help')` inherits.
        # An organisation id is a billing key, never student data, and never enters the prompt.
        with _usage.usage_context(application=doc.application):
            result = help_cache.cached_help(   # A2.4 SP-06: a repeat open costs no model call
                doc.application_id, doc.doc_type, verdict,
                first_name=help_engine.first_name_of(doc), target_language=language,
                branding=_branding.for_application(doc.application),
            )
        result['verdict'] = verdict
        result.update(detail)
        _log_coach_serve('doc', doc.application_id, result.get('source', 'none'), verdict)
        return Response(result)


class IncomeClusterHelpView(APIView):
    """GET the SINGLE "Cikgu Gopal" message for one earner's whole income cluster.

    Income is a cluster (the earner's IC + their STR / payslip / EPF + their relationship
    doc), so unlike the single-document facts the coach speaks once per EARNER, anchored at
    the foot of the cluster — even before the IC is uploaded. ``member`` is the household
    member (father / mother / guardian / brother / sister). Same soft contract + hourly
    throttle as the per-document helper; nothing here is admin/score data."""
    permission_classes = [SupabaseIsAuthenticated]

    _MEMBERS = ('father', 'mother', 'guardian', 'brother', 'sister')

    def get(self, request, member):
        if member not in self._MEMBERS:
            return Response({'message': '', 'source': 'none'})
        app = _current_application(request.user_id)
        if app is None:
            return Response({'message': '', 'source': 'none'})

        from .. import help_engine
        from ..income_engine import income_cluster_advice
        verdict = income_cluster_advice(app, member)
        if not verdict:
            _log_coach_serve('income_cluster', app.id, 'none', '')
            return Response({'message': '', 'source': 'none'})

        from django.conf import settings as _settings
        from django.core.cache import cache
        from django.utils import timezone
        cap = getattr(_settings, 'DOC_HELP_RATE_LIMIT_PER_HOUR', 20)
        key = f'help_coach:{app.id}:{timezone.now():%Y%m%d%H}'
        if cache.get(key, 0) >= cap:
            _log_coach_serve('income_cluster', app.id, 'fallback', verdict)
            return Response({'message': '', 'source': 'fallback', 'verdict': verdict})
        cache.set(key, cache.get(key, 0) + 1, 3600)

        from ..profile_engine import _resolve_language
        language = _resolve_language(app, request.query_params.get('lang'))
        first_name = (getattr(getattr(app, 'profile', None), 'name', '') or '').strip().split(' ')[0]
        # Non-sensitive specifics so the coach names the RIGHT member + document (e.g. "your
        # mother's MyKad alongside her STR document"), not the generic father/payslip example.
        from ..income_engine import (_cluster_proof_identity, relationship_doc_for,
                                     _member_ic_doc, student_income_ic_check)
        _MEMBER_LABEL = {'father': 'father', 'mother': 'mother', 'guardian': 'legal guardian',
                         'brother': 'elder brother', 'sister': 'elder sister'}
        _DOC_LABEL = {'str': 'STR document', 'salary_slip': 'salary slip', 'epf': 'EPF statement',
                      'birth_certificate': 'birth certificate', 'guardianship_letter': 'guardianship letter'}
        proof_kind, _pn, _pi = _cluster_proof_identity(app, member)
        rel_doc = relationship_doc_for(member)
        # Is the earner's MyKad already corroborated by their income document? If so, a
        # relationship clash is the BC's fault, not the IC's — let the coach commit to that
        # (drop the now-pointless "re-check the MyKad" line).
        _ic_doc = _member_ic_doc(app, member)
        _icc = student_income_ic_check(_ic_doc) if _ic_doc else None
        ic_matches_income_doc = bool(_icc and 'match' in
                                     (_icc.get('proof_name_status'), _icc.get('proof_nric_status')))
        # income_proof_needed asks specifically for the salary slip (the proof not yet uploaded,
        # so _cluster_proof_identity has nothing to report). The relationship-mismatch message is
        # member-aware: a mother's clash is between her birth certificate and her MyKad, so name
        # the rel doc there too (not just for the "needed/unreadable" verdicts).
        income_doc = ('salary slip' if verdict == 'income_proof_needed'
                      else _DOC_LABEL.get(proof_kind, ''))
        # #4: on the STR route the salary slip / EPF is OPTIONAL (the STR is the income proof), so a
        # wrong-person proof there is an extra file to REMOVE, not a required one to re-upload.
        _route = (getattr(app, 'income_route', '') or '').strip()
        context = {
            'member': _MEMBER_LABEL.get(member, member),
            'income_doc': income_doc,
            'rel_doc': (_DOC_LABEL.get(rel_doc, '') if verdict in (
                'income_rel_doc_needed', 'income_rel_doc_unreadable',
                'income_relationship_mismatch') else ''),
            'ic_matches_income_doc': (ic_matches_income_doc
                                      and verdict == 'income_relationship_mismatch'),
            'income_proof_optional': (_route == 'str'
                                      and verdict == 'income_proof_person_mismatch'),
        }
        from .. import branding as _branding, help_cache
        from .. import usage as _usage
        # Same billing seam as the per-document coach — ambient only, signature untouched.
        with _usage.usage_context(application=app):
            result = help_cache.cached_help(   # A2.4 SP-06: a repeat open costs no model call
                app.id, 'income_cluster', verdict, first_name=first_name, target_language=language,
                context=context, branding=_branding.for_application(app),
            )
        result['verdict'] = verdict
        _log_coach_serve('income_cluster', app.id, result.get('source', 'none'), verdict)
        return Response(result)
