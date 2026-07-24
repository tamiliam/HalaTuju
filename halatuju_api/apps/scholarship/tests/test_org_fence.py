"""Platform Sprint 3b — PROVE the organisation fence, forever.

Three durable guards protecting the owner's feature-work period after Phase 1:

1. Fence-proof suite — two real organisations, each with an application (+ document,
   sponsorship, graduation message). Drive the REAL admin endpoints and assert one
   org's staff can never see or act on the other's rows.
2. Coverage-completeness — enumerate every `_AdminBase` subclass at runtime; each MUST
   be classified in FENCED_OR_EXEMPT. A new endpoint nobody classified fails CI.
3. Static source guard — a raw watched-model query in views_admin.py outside the shared
   helpers, with no `# org-fence:` pragma, fails CI (mirrors the superseded-docs guard).
"""
import datetime
import os
import re
from unittest import mock

import jwt
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import views_admin
from apps.scholarship.models import (
    ApplicantDocument, GraduationMessage, ScholarshipApplication, ScholarshipCohort,
    Sponsor, Sponsorship,
)
from apps.scholarship.views_admin import _AdminBase

TEST_JWT_SECRET = 'test-supabase-jwt-secret'


# QC refuses to accept a case with no reporting date (owner 2026-07-23) - it sizes the
# bursary, so a missing one is no longer acceptable at the gate. A fresh-entrant date,
# matching the cohort year, so these suites' existing amount assertions are unchanged.
_QC_REPORTING_DATE = datetime.date(2026, 6, 8)


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestOrgFenceProof(TestCase):
    """Two tenants, full stack of rows, driven through the real endpoints."""
    @classmethod
    def setUpTestData(cls):
        def tenant(code, uid_ns):
            org = PartnerOrganisation.objects.create(code=f'proof-{code}', name=code)
            cohort = ScholarshipCohort.objects.create(
                code=f'pc-{code}', name=code, year=2026, owning_organisation=org)
            prof = StudentProfile.objects.create(
                supabase_user_id=f'{uid_ns}-stud', nric=f'0101{uid_ns}-14-0001', name=f'Stud {code}')
            app = ScholarshipApplication.objects.create(reporting_date=_QC_REPORTING_DATE, 
                cohort=cohort, profile=prof, status='interviewed',
                verdict_decided_at=timezone.now(),
                ai_verdict_snapshot=[], officer_verdict={})
            ApplicantDocument.objects.create(
                application=app, doc_type='ic', storage_path=f'{app.id}/ic/x')
            sponsor = Sponsor.objects.create(
                supabase_user_id=f'{uid_ns}-spon', name=f'Sponsor {code}', email=f'sp{uid_ns}@x.com')
            Sponsorship.objects.create(sponsor=sponsor, application=app, amount=1000, status='offered')
            GraduationMessage.objects.create(application=app, raw_text='thank you', status='pending')
            admin = PartnerAdmin.objects.create(
                supabase_user_id=f'{uid_ns}-admin', role='admin', is_active=True,
                owning_organisation=org, name=f'Admin {code}', email=f'adm{uid_ns}@x.com')
            return dict(org=org, app=app, admin=admin)

        cls.a = tenant('A', 'a')
        cls.b = tenant('B', 'b')
        cls.super = PartnerAdmin.objects.create(
            supabase_user_id='super-uid', is_super_admin=True, is_active=True,
            name='Super', email='super@x.com')
        # A qc + a reviewer bound to org A — needed to exercise the org gate on the
        # QC and graduation-review endpoints (their ROLE gate fires before the org
        # gate, so a plain 'admin' would 403 on role before reaching the org 404).
        cls.qc_a = PartnerAdmin.objects.create(
            supabase_user_id='a-qc', role='qc', is_active=True,
            owning_organisation=cls.a['org'], name='QC A', email='qca@x.com')
        cls.reviewer_a = PartnerAdmin.objects.create(
            supabase_user_id='a-rev', role='reviewer', is_active=True,
            owning_organisation=cls.a['org'], name='Reviewer A', email='reva@x.com')
        # org_admin per tenant — org-wide read + QC, own org only (Administration panel).
        cls.org_admin_a = PartnerAdmin.objects.create(
            supabase_user_id='a-oa', role='org_admin', is_active=True,
            owning_organisation=cls.a['org'], name='OrgAdmin A', email='oaa@x.com')
        cls.org_admin_b = PartnerAdmin.objects.create(
            supabase_user_id='b-oa', role='org_admin', is_active=True,
            owning_organisation=cls.b['org'], name='OrgAdmin B', email='oab@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    # --- list surfaces return only the caller's org --------------------------
    def test_application_list_isolated(self):
        self._auth('a-admin')
        ids = {a['id'] for a in self.client.get('/api/v1/admin/scholarship/applications/').json()['applications']}
        self.assertEqual(ids, {self.a['app'].id})

    def test_sponsorship_list_isolated(self):
        self._auth('a-admin')
        r = self.client.get('/api/v1/admin/sponsorships/').json()
        app_ids = {s['application_id'] for s in r['sponsorships']} if r['sponsorships'] and 'application_id' in r['sponsorships'][0] else None
        self.assertEqual(len(r['sponsorships']), 1)
        if app_ids is not None:
            self.assertEqual(app_ids, {self.a['app'].id})

    def test_graduation_list_isolated(self):
        self._auth('a-admin')
        r = self.client.get('/api/v1/admin/graduation-messages/?status=all').json()
        self.assertEqual(len(r['messages']), 1)

    def test_verdict_metrics_isolated(self):
        self._auth('a-admin')
        m = self.client.get('/api/v1/admin/scholarship/verdict-metrics/').json()
        self.assertEqual(m['applications'], 1)
        self._auth('super-uid')
        m = self.client.get('/api/v1/admin/scholarship/verdict-metrics/').json()
        self.assertEqual(m['applications'], 2)

    # --- super sees everything ----------------------------------------------
    def test_super_sees_both_lists(self):
        self._auth('super-uid')
        ids = {a['id'] for a in self.client.get('/api/v1/admin/scholarship/applications/').json()['applications']}
        self.assertEqual(ids, {self.a['app'].id, self.b['app'].id})
        self.assertEqual(len(self.client.get('/api/v1/admin/sponsorships/').json()['sponsorships']), 2)

    # --- cross-org detail / write / QC are blocked (404, no existence leak) ---
    def test_cross_org_detail_404(self):
        self._auth('a-admin')
        r = self.client.get(f"/api/v1/admin/scholarship/applications/{self.b['app'].id}/")
        self.assertEqual(r.status_code, 404)

    def test_cross_org_write_404(self):
        self._auth('a-admin')
        r = self.client.post(
            f"/api/v1/admin/scholarship/applications/{self.b['app'].id}/verify-accept/", {}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_cross_org_qc_404(self):
        self._auth('a-qc')  # a qc (role passes) from org A on org B's app → org gate → 404
        r = self.client.post(
            f"/api/v1/admin/scholarship/applications/{self.b['app'].id}/qc-decision/",
            {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_cross_org_graduation_review_404(self):
        msg_b = GraduationMessage.objects.get(application=self.b['app'])
        self._auth('a-rev')  # a reviewer (role passes) from org A on org B's message → 404
        r = self.client.post(
            f'/api/v1/admin/graduation-messages/{msg_b.id}/review/', {'action': 'approve'}, format='json')
        self.assertEqual(r.status_code, 404)

    # --- org_admin behaves exactly like the other org-scoped roles -----------
    def test_org_admin_list_isolated(self):
        self._auth('a-oa')
        ids = {a['id'] for a in self.client.get('/api/v1/admin/scholarship/applications/').json()['applications']}
        self.assertEqual(ids, {self.a['app'].id})

    def test_org_admin_cross_org_detail_404(self):
        self._auth('a-oa')
        r = self.client.get(f"/api/v1/admin/scholarship/applications/{self.b['app'].id}/")
        self.assertEqual(r.status_code, 404)

    def test_org_admin_cross_org_qc_404(self):
        self._auth('a-oa')
        r = self.client.post(
            f"/api/v1/admin/scholarship/applications/{self.b['app'].id}/qc-decision/",
            {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 404)

    def test_org_admin_same_org_qc_accepts(self):
        # org_admin has QC powers (owner decision) — a same-org QC accept works.
        with mock.patch('apps.scholarship.views_admin.build_verdict', return_value=[]):
            self._auth('a-oa')
            r = self.client.post(
                f"/api/v1/admin/scholarship/applications/{self.a['app'].id}/qc-decision/",
                {'decision': 'accept'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.a['app'].refresh_from_db()
        self.assertEqual(self.a['app'].status, 'recommended')


class TestFenceCoverageCompleteness(TestCase):
    """Every _AdminBase subclass must be explicitly classified. A new admin endpoint
    that nobody wired into the fence (or consciously exempted) fails HERE."""

    # name → how it is fenced (see docs/plans/2026-07-15-phase1-s3a-endpoint-audit.md).
    FENCED_OR_EXEMPT = {
        # base
        '_BursaryAdminBase': 'base — shared _agreement lookup',
        '_PaymentsBase': 'base — shared payments gate + org-fenced run lookup',
        # Payments module (P2) — org-fenced via _run_for (cross-org 404) + admin/org_admin role
        # gate; the list is filtered to the caller's organisation. PaymentRun/PaymentRunItem are
        # not watched applicant models, so no static-guard pragma is needed.
        'AdminPaymentRunListView': 'payments-org-fenced', 'AdminPaymentRunDetailView': 'payments-org-fenced',
        'AdminPaymentRunItemView': 'payments-org-fenced', 'AdminPaymentRunSignView': 'payments-org-fenced',
        'AdminPaymentRunCancelView': 'payments-org-fenced', 'AdminPaymentRunCsvView': 'payments-org-fenced',
        # Sprint 14 — filters applications on owning_organisation; a super with no org context
        # gets `no_org` rather than every tenant's students.
        'AdminPaymentFundingSummaryView': 'payments-org-fenced',
        # Contract module (S3) — org-fenced via _ContractsBase._template_for (cross-org 404)
        # + super/org_admin role gate; the list filters to the caller's org; deploy is
        # super-only. ContractTemplate is not a watched applicant model → no static pragma.
        '_ContractsBase': 'base — shared contract gate + org-fenced template lookup',
        'AdminContractTemplateListView': 'contract-org-fenced', 'AdminContractTemplateDetailView': 'contract-org-fenced',
        'AdminContractClausesView': 'contract-org-fenced', 'AdminContractScheduleView': 'contract-org-fenced',
        'AdminContractGenerateQuizView': 'contract-org-fenced', 'AdminContractVettingView': 'contract-org-fenced',
        'AdminContractValidateView': 'contract-org-fenced', 'AdminContractSubmitView': 'contract-org-fenced',
        'AdminContractRevertView': 'contract-org-fenced', 'AdminContractDeployView': 'contract-org-fenced+super-deploy',
        'AdminContractPreviewView': 'contract-org-fenced', 'AdminContractQuizPreviewView': 'contract-org-fenced',
        'AdminContractImportDocxView': 'contract-org-fenced',
        # Requests space (Sprint 15) — org-fenced via _OrgRequestsBase._org_request_for
        # (cross-org 404); list/count/detail scoped to the caller's org (super global). The
        # requestee actions (answer/defer/modify) are org_admin; approve/decline add super; the
        # owner actions (triage/quote/requote/schedule/done/ai-rerun) are super-only. OrgRequest
        # IS a watched model (added to WATCHED below) so its raw queries carry # org-fence pragmas.
        # Every route 404s while REQUESTS_ENABLED is off (dark ship).
        '_OrgRequestsBase': 'base — requests flag/role/org gate + org-fenced request lookup',
        'AdminOrgRequestListView': 'requests-org-fenced', 'AdminOrgRequestCountView': 'requests-org-fenced',
        'AdminOrgRequestDetailView': 'requests-org-fenced', 'AdminOrgRequestAnswerView': 'requests-org-fenced',
        'AdminOrgRequestApproveView': 'requests-org-fenced', 'AdminOrgRequestDeferView': 'requests-org-fenced',
        'AdminOrgRequestModifyView': 'requests-org-fenced', 'AdminOrgRequestDeclineView': 'requests-org-fenced',
        'AdminOrgRequestTriageView': 'requests-org-fenced+super-only',
        'AdminOrgRequestQuoteView': 'requests-org-fenced+super-only',
        'AdminOrgRequestRequoteView': 'requests-org-fenced+super-only',
        'AdminOrgRequestScheduleView': 'requests-org-fenced+super-only',
        'AdminOrgRequestDoneView': 'requests-org-fenced+super-only',
        'AdminOrgRequestAiRerunView': 'requests-org-fenced+super-only',
        # Sources module (go-live transition, T1) — super/org_admin role gate via _SourcesBase.
        # Source rows (PartnerOrganisation) are a SHARED single-tenant registry, deliberately NOT
        # org-fenced (multi-tenant fencing of shared source rows is out of scope — see the plan).
        # The witness endpoint reaches an application via _get_application (not a raw query).
        '_SourcesBase': 'base — super/org_admin gate for sources + witness assignment',
        'AdminSourcesView': 'shared-registry-single-tenant', 'AdminSourceDetailView': 'shared-registry-single-tenant',
        'AdminApplicationWitnessView': 'super/org_admin — witness assignment (single-tenant)',
        # gate-fenced (via _scoped_application / _require_app_write / _require_qc)
        'AdminApplicationDetailView': 'gate', 'AdminVerdictSummaryView': 'gate',
        'AdminVerifyAcceptView': 'gate', 'AdminRejectView': 'gate',
        # Fenced by _require_app_write, then narrowed again to super/org_admin (see the view).
        'AdminOrgRejectView': 'gate',
        # Fenced by _require_app_write; records the officer-entered reporting date.
        'AdminReportingDateView': 'gate',
        # Fenced by _require_app_write, then narrowed to super/org_admin (manual nudge send).
        'AdminNudgeStudentView': 'gate',
        'AdminCancelDeclineView': 'gate', 'AdminHoldAwardView': 'gate',
        'AdminApplicationRefereeView': 'gate', 'AdminRefereeDetailView': 'gate',
        'AdminRunVisionView': 'gate', 'AdminGenerateProfileView': 'gate',
        'AdminFinaliseProfileView': 'gate', 'AdminPublishAnonProfileView': 'gate',
        'AdminSuggestGapsView': 'gate', 'AdminProfileEditView': 'gate',
        'AdminPublishProfileView': 'gate', 'AdminInterviewView': 'gate',
        'AdminInterviewSubmitView': 'gate', 'AdminInterviewReopenView': 'gate',
        'AdminSetAwardAmountView': 'gate', 'AdminDisbursementScheduleView': 'gate',
        'AdminCloseApplicationView': 'gate', 'AdminMaintenanceSubstateView': 'gate',
        'AdminRequestInfoView': 'gate', 'AdminResolutionItemView': 'gate',
        'AdminRecordVerdictView': 'gate', 'AdminReopenDecisionView': 'gate',
        'AdminQcDecisionView': 'gate', 'AdminCancelReopenView': 'gate',
        'AdminSubmitDeclineView': 'gate',   # reviewer sends a decline verdict to QC (_require_app_write)
        'AdminAssignReviewerView': 'gate+super/org_admin', 'AdminInterviewSlotsView': 'gate',
        'AdminInterviewSlotDetailView': 'gate',
        # list/aggregate fenced via _org_scoped
        'AdminApplicationListView': 'list-fenced', 'AdminSponsorshipListView': 'list-fenced',
        'AdminVerdictMetricsView': 'list-fenced', 'AdminGraduationMessageListView': 'list-fenced',
        # list-fenced (PartnerAdmin staff pool, org-scoped for a non-super caller — 2026-07-15)
        'AdminAssignableAdminsView': 'list-fenced',
        # secondary fetch + _can_review_app / _org_allows re-gate
        'AdminDisbursementActionView': 'can-review', 'AdminResolutionItemActionView': 'can-review',
        'AdminGraduationMessageReviewView': 'org-allows',
        # super-only (global)
        'AdminBursaryCountersignView': 'super-only',
        # cross-org by design (platform-level Sponsor account; not applicant data — D-1).
        # Role-gated to super/org_admin (review) and super/org_admin/admin (list) since 2026-07-15.
        'AdminSponsorListView': 'cross-org-by-design', 'AdminSponsorReviewView': 'cross-org-by-design',
        'AdminSponsorPendingCountView': 'cross-org-by-design',
        # self-scoped (caller's own reviewer profile, no application)
        'ReviewerProfileView': 'self-scoped',
        # grandfathered referral-org authorisation (orthogonal to ownership; dark)
        'AdminBursaryWitnessView': 'grandfathered',
    }

    @staticmethod
    def _all_subclasses(cls):
        seen = set()
        stack = list(cls.__subclasses__())
        while stack:
            c = stack.pop()
            if c not in seen:
                seen.add(c)
                stack.extend(c.__subclasses__())
        return seen

    def test_every_admin_endpoint_is_classified(self):
        live = {c.__name__ for c in self._all_subclasses(_AdminBase)}
        unclassified = live - set(self.FENCED_OR_EXEMPT)
        self.assertEqual(
            unclassified, set(),
            'New _AdminBase endpoint(s) not classified in FENCED_OR_EXEMPT — wire the org '
            'fence (or add a documented exemption):\n' + '\n'.join(sorted(unclassified)))

    def test_no_stale_classifications(self):
        """Keep the map honest: every classified name must still be a live subclass."""
        live = {c.__name__ for c in self._all_subclasses(_AdminBase)}
        stale = set(self.FENCED_OR_EXEMPT) - live
        self.assertEqual(stale, set(), f'Stale entries in FENCED_OR_EXEMPT: {sorted(stale)}')


class TestOrgFenceStaticGuard(TestCase):
    """A raw watched-model query in views_admin.py MUST be fenced. Any
    `ScholarshipApplication.objects` / `Sponsorship.objects` / `GraduationMessage.objects`
    / `ApplicantDocument.objects` without a nearby `# org-fence:` pragma fails — so a
    future endpoint can't reintroduce a cross-tenant read/write by hand."""

    WATCHED = (
        'ScholarshipApplication.objects', 'Sponsorship.objects',
        'GraduationMessage.objects', 'ApplicantDocument.objects',
        'OrgRequest.objects',
    )

    def test_raw_admin_queries_are_fenced(self):
        path = os.path.join(os.path.dirname(views_admin.__file__), 'views_admin.py')
        with open(path, encoding='utf-8') as fh:
            src = fh.read()
        offenders = []
        for tok in self.WATCHED:
            for m in re.finditer(re.escape(tok), src):
                # Window spans a pragma placed on the line(s) just above or just below.
                window = src[max(0, m.start() - 200):m.start() + 200]
                if 'org-fence:' not in window:
                    line = src.count('\n', 0, m.start()) + 1
                    offenders.append(f'views_admin.py:{line} — {tok}')
        self.assertEqual(
            offenders, [],
            'Raw admin query without an `# org-fence:` pragma (cross-tenant read/write risk):\n'
            + '\n'.join(offenders))
