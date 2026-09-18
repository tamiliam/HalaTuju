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

from apps import scholarship as _scholarship_pkg
from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import (
    ApplicantDocument, GraduationMessage, ScholarshipApplication, ScholarshipCohort,
    Sponsor, Sponsorship,
)
from apps.scholarship.views_admin import _AdminBase

TEST_JWT_SECRET = 'test-supabase-jwt-secret'

#: The app directory the static guard reads from. Taken from the PACKAGE, never from
#: `views_admin.__file__` — H11 turns `views_admin.py` into `views_admin/`, and
#: `os.path.dirname()` of a package's `__init__.py` is the package itself, which would
#: silently move the whole scan one level down.
_APP_DIR = os.path.dirname(_scholarship_pkg.__file__)


def scan_targets(base, entry):
    """Resolve ONE `SCANNED` entry to the source files it names.

    An entry is EITHER a filename (`views_admin.py`) OR a package directory
    (`views_admin/`), and the guard must read the same queries either way. H11 splits
    `views_admin.py` into a package of submodules; without this, the tuple would keep
    naming a file that no longer exists and the guard would either error or — worse, if
    someone "fixed" it by dropping the entry — pass for ever while watching nothing.

    A directory is walked RECURSIVELY, so a submodule nested inside the package
    (`views_admin/requests/invoices.py`) is scanned like any other. Returns absolute
    paths, sorted, and an empty list when the entry names nothing — the floor test below
    is what turns that emptiness into a failure.
    """
    path = os.path.join(base, entry)
    if os.path.isdir(path):
        return sorted(
            os.path.join(dirpath, name)
            for dirpath, _dirs, names in os.walk(path)
            for name in names if name.endswith('.py'))
    return [path] if os.path.isfile(path) else []


def read_scanned(base, entry):
    """(display name, source) for every file an entry names. The display name is relative
    to `base` with forward slashes, so a package submodule reads as
    `views_admin/invoices.py` on every platform."""
    for path in scan_targets(base, entry):
        with open(path, encoding='utf-8') as fh:
            yield os.path.relpath(path, base).replace(os.sep, '/'), fh.read()


def find_offences(base, entries, watched, fences=(), pragmas=()):
    """Every watched query with neither a narrowing nor a pragma in its window.

    Yields (display name, line number, token, stripped source line). The window spans a
    pragma placed on the line(s) just above or just below, which is what makes a pragma a
    normal comment rather than a magic suffix.

    Module-level, and given its `base`, so the scanner itself is testable against a
    throwaway tree — see `test_a_package_submodule_is_scanned_like_a_file`.
    """
    for entry in entries:
        for name, src in read_scanned(base, entry):
            lines = src.split('\n')
            for tok in watched:
                for m in re.finditer(re.escape(tok), src):
                    window = src[max(0, m.start() - 200):m.start() + 200]
                    if any(p in window for p in pragmas):
                        continue
                    if any(f in window for f in fences):
                        continue
                    n = src.count('\n', 0, m.start()) + 1
                    yield name, n, tok, lines[n - 1].strip()


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
        # Sabah S2b — gift programmes and their intake years. FENCED on the PROGRAMME's own
        # `organisation_id`, derived from the caller's `owning_organisation` in
        # `_ProgrammeScopedBase._programmes_for`; a super sees every tenant, everyone else exactly
        # their own, and a NULL-org admin sees none (`.none()`, not everything). Cross-tenant is
        # **404, never 403** — the same reasoning that keeps the org fence on 404 elsewhere: a 403
        # would confirm the tenant exists. Intake years are reached only through
        # `programme__in=_programmes_for(...)`, so they inherit the same wall.
        # ⚠ `_programmes_for` deliberately includes INACTIVE programmes, unlike the configuration
        # screen's `_programme_for` — you cannot switch a gift on if you cannot see it. That widens
        # what is LISTED, never across the organisation boundary.
        '_ProgrammeScopedBase': 'sabah-s2b-programme-scoped-base',
        # Sponsor spending S4 — the officer's spending screen. FENCED on
        # `application__owning_organisation` inside `spend_report._txns`, the same fence the
        # Payments funding summary uses; `_SpendingBase._spending_admin` resolves the scope ONCE.
        # ⚠ S6 (2026-09-11) added a SECOND scope: a super gets `spend_report.ALL_ORGS`, which
        # reads every organisation. `_spending_admin` is the only door to it in the feature, and
        # it is a sentinel OBJECT, never `None` — so an accident that loses an organisation still
        # filters `owning_organisation=None` (empty), rather than widening to the platform. An
        # `org_admin` with no organisation is still refused `no_org`.
        # ⚠ The merchant VERDICT is global on purpose (a shop's category is a fact about the
        # shop, not about a tenant) — so the fence on the WRITE is on who may set it: the
        # merchant must be one this organisation's own students actually used.
        # ⚠ `finance` is absent by decision, not omission: `_b40_scope` promises a finance
        # admin never sees student data beyond the Payments allowlist, and this screen carries
        # names beside purchases.
        '_SpendingBase': 'spending-s4-org-fenced',
        'AdminSpendingView': 'spending-s4-org-fenced',
        'AdminSpendingCategoryView': 'spending-s4-org-fenced',
        # Programme Overview (2026-09-15). The FENCE is `programme_overview.application_scope` —
        # one queryset every figure is derived from, `owning_organisation` for a tenant and
        # `spend_report.ALL_ORGS` for a super; disbursements and spend rows are reached only
        # through `application_id__in=scope`, never from their own managers.
        # ⚠ ROLE SHAPING IS A SECOND GATE, and it is why this entry is not plain 'org-fenced'.
        # The KEY SET IS CHOSEN SERVER-SIDE from `SECTIONS_BY_ROLE`, so reviewer/qc/finance never
        # receive a key they may not read on Applications/Payments/Spending — a reviewer's payload
        # has no money key to hide, and a finance admin's has no funnel. A page that fetched
        # everything and rendered a subset would be a side door into pages the menu withholds.
        # `test_the_key_set_per_role_is_exact` pins it; `partner` (no sections at all) is 403.
        'AdminProgrammeOverviewView': 'programme-overview-org-fenced+role-shaped',
        'AdminProgrammeListView': 'sabah-s2b-programmes-fenced',
        'AdminProgrammeDetailView': 'sabah-s2b-programmes-fenced',
        # Reaches its gift through the SAME `_programme_or_404`, so another tenant's gift is 404
        # before a single token is spent.
        'AdminApplyCopyDraftView': 'sabah-s2b-programmes-fenced',
        'AdminIntakeYearListView': 'sabah-s2b-intake-years-fenced',
        'AdminIntakeYearDetailView': 'sabah-s2b-intake-years-fenced',
        # Same fence as its sibling — the cohort is reached through `_programmes_for(admin)`, so a
        # round belonging to another tenant is a 404, never a 403.
        'AdminIntakeYearFinishView': 'sabah-s2b-intake-years-fenced',
        # nav/IA N3a — the breadcrumb switchers. LIST-fenced on the same
        # owning_organisation the fence itself uses, so it cannot widen anything: super sees
        # every active org/programme, everyone else exactly their own, `partner` nothing (a
        # referral org is attribution, never a scope), NULL-org empty rather than a 500.
        # ⚠ The SELECTION it feeds is a display preference — it must never travel as a
        # header/cookie/middleware rewrite, which would relocate the fence into the client.
        'AdminScopeListView': 'nav-scopes-list-fenced',
        # Layer 0 Sprint 5 — the programme configuration screen. Fenced on the PROGRAMME's
        # organisation_id (derived from the same owning_organisation the fence uses; cross-org
        # 404, never 403); super/org_admin only. It writes CONFIGURATION, never access — the
        # catalogue is not a fence, and the view docstring says so.
        'AdminProgrammeConfigurationView': 'programme-config-org-fenced',
        # Layer 1 A2. The ORGANISATION is derived from `admin.owning_organisation` — the same field
        # the fence itself uses — so it cannot widen access; a super names one with `?org=`, and a
        # code outside the caller's organisation is 404, never 403. It carries NO student data: the
        # payload is one organisation's name, its colour, and six contrast numbers.
        'AdminOrganisationThemeView': 'organisation-theme-org-fenced',
        # A3's two lifecycle endpoints SUBCLASS the view above, so they inherit its gate, its org
        # fence and its payload rather than growing their own copies. Classified separately because
        # the coverage check enumerates subclasses, and a shared fence is still a fence per route.
        'AdminOrganisationThemePublishView': 'organisation-theme-org-fenced',
        'AdminOrganisationThemeRevertView': 'organisation-theme-org-fenced',
        # Org Config Sprint A. Same derivation as the theme view (organisation from
        # `admin.owning_organisation`; super names `?org=`; cross-org 404, never 403) — a
        # MIRROR, not a subclass, so a stray verb on this route can never touch a colour draft.
        # Payload = the registry's few tunable numbers for ONE organisation; no student data.
        'AdminOrganisationConfigurationView': 'organisation-config-org-fenced',
        # Programme Overview phase 2 (2026-09-18). The organisation's widget layout — the SAME
        # derivation as the configuration view (organisation from `admin.owning_organisation`;
        # super names `?org=`; cross-org 404, never 403), a MIRROR again. Payload = five keys and
        # five booleans; no student data. Writers: org_admin + super. What it changes is read by
        # `programme_overview.build` as a NARROWING of the role's sections, never a widening.
        'AdminOverviewLayoutView': 'overview-layout-org-fenced',
        # base
        '_BursaryAdminBase': 'base — shared _agreement lookup',
        '_PaymentsBase': 'base — shared payments gate + org-fenced run lookup',
        '_CreditsBase': 'base — shared credits gate + org-fenced credit lookup',
        # Wallet credits (P4b) — org-fenced on `programme__organisation_id` (cross-org 404).
        # NB the fence is on the PROGRAMME, not the sponsor: a Sponsor is a platform-level
        # account (deliberately unfenced, see AdminSponsorListView), but the money inside a
        # gift belongs to the organisation running that gift. POST also re-fences the target
        # programme, so an admin cannot credit a wallet inside another tenant's gift.
        'AdminWalletCreditListCreateView': 'credits-org-fenced',
        'AdminWalletCreditSignView': 'credits-org-fenced',
        'AdminWalletCreditCancelView': 'credits-org-fenced',
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
        # The owner asking the requester a question — super-only via _super_side, which still
        # resolves the request through the org-fenced _org_request_for lookup.
        'AdminOrgRequestAskView': 'requests-org-fenced',
        # TD-201, the discussion. super OR any org_admin of the OWNING org, via
        # _requestee(allow_super=True) -> the same org-fenced _org_request_for lookup, so a
        # cross-org pk is a 404 before any comment is written. The 'internal' visibility is
        # refused for a non-super at the view AND in the service.
        'AdminOrgRequestCommentView': 'requests-org-fenced',
        # TD-204, the engineer's analysis. Super-only, and the analysis row is reached through
        # `req.analyses` — never `OrgRequestAnalysis.objects` — so the org-fenced request lookup
        # is also the fence on the analysis. This table holds the cited file paths and the hours,
        # which the requesting organisation must never see; no org-facing serializer names it.
        'AdminOrgRequestAnalysisView': 'requests-org-fenced+super-only',
        'AdminOrgRequestAnalysisApproveView': 'requests-org-fenced+super-only',
        # Same fence, same reason: retiring a draft reaches it through `req.analyses` too, so a
        # cross-org analysis id 404s rather than resolving.
        'AdminOrgRequestWithdrawAnalysisView': 'requests-org-fenced+super-only',
        # Request #10 — the reviewers surface. A PartnerAdmin carries `owning_organisation`, so both
        # views narrow on it directly; the detail resolves THROUGH the narrowed list, so a cross-org
        # id 404s. Their workload figures are fenced on the application's owner too.
        '_ReviewersBase': 'base — reviewers role gate + owning_organisation narrowing',
        'AdminReviewerListView': 'list-fenced',
        'AdminReviewerDetailView': 'list-fenced',
        'AdminReviewerPauseView': 'list-fenced+org_admin-only',
        # Same shape, and doubly fenced: the reviewer resolves through the list-fenced
        # `_reviewers`, and the GIFT resolves through `_programmes_for`. Both a cross-org
        # reviewer and a cross-org gift are 404. What it sets is a NARROWING of who is offered
        # work, never a fence — see the view's docstring.
        'AdminReviewerProgrammeView': 'list-fenced+org_admin-only',
        # The seven code-owned reviewer emails. Serves the SAME seven strings to every tenant —
        # there is no organisation data in it to narrow — so it is exempt on content, not on
        # oversight. The role gate is inherited from `_ReviewersBase` all the same.
        'AdminReviewerSystemEmailsView': 'no-org-data (static system copy) + reviewers role gate',
        # Invitations. ⚠ Fenced on `Invitation.organisation` and NOT through `PartnerAdmin`: a
        # sponsor invitation has no staff row to fence through (it creates no account), so
        # fencing through the invitee would silently drop that whole kind.
        'AdminInvitationsView': 'invitation-org-fenced',
        'AdminOrgRequestApproveView': 'requests-org-fenced', 'AdminOrgRequestDeferView': 'requests-org-fenced',
        'AdminOrgRequestModifyView': 'requests-org-fenced', 'AdminOrgRequestDeclineView': 'requests-org-fenced',
        'AdminOrgRequestTriageView': 'requests-org-fenced+super-only',
        'AdminOrgRequestQuoteView': 'requests-org-fenced+super-only',
        'AdminOrgRequestRequoteView': 'requests-org-fenced+super-only',
        'AdminOrgRequestScheduleView': 'requests-org-fenced+super-only',
        'AdminOrgRequestDoneView': 'requests-org-fenced+super-only',
        'AdminOrgRequestAiRerunView': 'requests-org-fenced+super-only',
        # Sprint 15.1 — screenshot attachments (org_admin own org + super); reached only through the
        # org-fenced request lookup, so a cross-org attachment is 404.
        'AdminOrgRequestAttachmentSignUploadView': 'requests-org-fenced',
        'AdminOrgRequestAttachmentCreateView': 'requests-org-fenced',
        'AdminOrgRequestAttachmentDeleteView': 'requests-org-fenced',
        # Sources module (go-live transition, T1) — super/org_admin role gate via _SourcesBase.
        # Source rows (PartnerOrganisation) are a SHARED single-tenant registry, deliberately NOT
        # org-fenced (multi-tenant fencing of shared source rows is out of scope — see the plan).
        # The witness endpoint reaches an application via _get_application (not a raw query).
        '_SourcesBase': 'base — super/org_admin gate for sources + witness assignment',
        'AdminSourcesView': 'shared-registry-single-tenant', 'AdminSourceDetailView': 'shared-registry-single-tenant',
        # Partner comms (2026-07-26) — same _SourcesBase role gate. Deliberately NOT org-fenced,
        # for the same reason as the Sources registry above: a partner-email TEMPLATE is
        # programme-wide (one wording for every partner, owner ruling — there is no per-org row to
        # fence), and the "who qualifies" list mirrors the shared source registry. Revisit together
        # with the Sources rows when a second tenant runs its own referral partners.
        'AdminPartnerEmailsView': 'shared-registry-single-tenant',
        'AdminPartnerEmailDetailView': 'shared-registry-single-tenant',
        'AdminApplicationWitnessView': 'super/org_admin — witness assignment (single-tenant)',
        # Billing & usage (Sprint 13a) — dual-audience, flag-gated 404-first. org_admin is
        # org-fenced BY CONSTRUCTION (usage.monthly_usage(restrict_org_id=own org) can build no
        # other org and no platform/NULL row — proven by the leak test in test_billing_usage.py);
        # super sees all orgs + the platform (NULL) reconciliation row. The aggregate query lives
        # in usage.py, not a raw views_admin query, so no static-guard pragma applies.
        'AdminBillingUsageView': 'billing-org-fenced (org_admin own org; super all+platform)',
        # Platform-level commercial config: the rate and margins applied to EVERY tenant. Not
        # org-scoped data at all, so there is nothing to fence — the control is that only a
        # super may read or write it (403 for org_admin, not 404: the route's existence is not
        # the secret, its contents are).
        'AdminBillingRatesView': 'super-only (platform commercial config, no tenant data)',
        # What the PLATFORM paid (one ledger for the whole platform, not per tenant) plus each
        # tenant's charge. Super-only for the same reason as the rates above — what we pay and
        # the margin on it is a commercial disclosure — so a 403, not a 404. The per-tenant
        # charges it returns are not org-fenced BECAUSE only a super ever sees the payload;
        # the tenant list itself comes from `.tenants()`, never a bare `is_active` filter.
        'AdminPlatformCostsView': 'super-only (platform cost ledger + every tenant\'s charge)',
        # Org-scoped: filtered on organisation_id, cross-org is 404. Super writes (a charge
        # against a tenant), org_admin reads its own only.
        'AdminOrgBuildHoursView': 'org-fenced (org_admin own org read; super writes)',
        # Tenant invoices (2026-09-14). ONE fence for all four: `_InvoiceBase._visible_invoices`
        # narrows an org_admin to its OWN organisation AND to invoices already SENT (the owner's
        # hold-until-Send ruling is part of the fence, not a display filter). Receipts are reached
        # only through that invoice set. Issue/send/void/receipt and both settings writes are
        # super-only. Proven through the real endpoints in test_invoice_endpoints.py.
        '_InvoiceBase': 'invoice fence base (own org + sent only for org_admin)',
        'AdminInvoicesView': 'invoice-fenced (org_admin own sent invoices; super all + issue)',
        'AdminInvoiceActionView': 'super-only (send / void / record receipt)',
        'AdminInvoicePdfView': 'invoice-fenced (org_admin own sent invoice or its receipt)',
        'AdminInvoiceSettingsView': 'super-only (issuer + tenant billing details)',
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
        # Break-glass on an IC lock — SUPER ONLY, and a super is unfenced by definition, so
        # there is no org dimension to fence. No other role reaches it, including org_admin,
        # which is deliberately narrower than the gate that TAKES the lock.
        'AdminReleaseNricLockView': 'gate — super-only',
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
        # The ACCOUNT is cross-org by design (as above); the MONEY and STUDENTS inside it are
        # fenced per-request by _SponsorScope (programme->organisation for credits + wallets,
        # application->owning_organisation for sponsorships). Same split as the credit endpoints.
        'AdminSponsorDetailView': 'identity-cross-org+money-fenced',
        # S-ASSIGN. The SPONSOR is deliberately unfenced (a platform-level account: one
        # login, one identity, one vetting), and the PROGRAMME is fenced hard — resolved
        # through `_programmes_for`, so another tenant's gift is 404, never 403. That is the
        # same split `AdminSponsorDetailView` carries: identity is cross-org, the money and
        # the students hanging off it are not.
        'AdminSponsorMembershipView': 'identity-cross-org+money-fenced',
        'AdminSponsorPendingCountView': 'cross-org-by-design',
        # Sponsor comms (S3): the templates are PLATFORM-level, not tenant content. A Sponsor has
        # no organisation, and enablement is per EMAIL not per recipient — so there is exactly one
        # welcome email for every sponsor, and nothing here to fence. Gated to super/org_admin/
        # admin (deliberately NARROWER than the sponsor LIST, which finance may also read: seeing
        # who funds the programme is finance's business, deciding what donors are told is not).
        '_SponsorEmailsBase': 'cross-org-by-design',
        'AdminSponsorEmailsView': 'cross-org-by-design',
        'AdminSponsorEmailDetailView': 'cross-org-by-design',
    # Sponsor TERMS (T2) are platform-level for exactly the reason the sponsor-emails block above
    # gives: a Sponsor has no organisation, so the document a sponsor accepts is not tenant
    # content and there is nothing here to fence. A second tenant wanting its own terms is a
    # product decision that would add an organisation FK — and would then need classifying here.
    '_SponsorTermsBase': 'cross-org-by-design',
    'AdminSponsorTermsListView': 'cross-org-by-design',
    'AdminSponsorTermsDetailView': 'cross-org-by-design',
    'AdminSponsorTermsSectionsView': 'cross-org-by-design',
    'AdminSponsorTermsGenerateQuizView': 'cross-org-by-design',
    'AdminSponsorTermsValidateView': 'cross-org-by-design',
    'AdminSponsorTermsPublishView': 'cross-org-by-design+super-publish',
    'AdminSponsorTermsPreviewView': 'cross-org-by-design',
    'AdminSponsorTermsImportDocxView': 'cross-org-by-design',
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
    future endpoint can't reintroduce a cross-tenant read/write by hand.

    ⚠ **TWO VOCABULARIES, ONE GUARD (TD-240, code health H3).** An admin endpoint is fenced
    on `owning_organisation`; a SPONSOR endpoint is not, and never was — it is fenced on the
    SPONSOR (`pool.for_sponsor`, or reading off the sponsor row itself). That is why
    `views_sponsor.py` sat in `NOT_YET_SCANNED` for months: scanning it with the admin
    vocabulary alone would have reported every correct sponsor fence as an offence. It is now
    scanned with BOTH — the admin tokens below, and the sponsor tokens in `SPONSOR_WATCHED`."""

    WATCHED = (
        'ScholarshipApplication.objects', 'Sponsorship.objects',
        'GraduationMessage.objects', 'ApplicantDocument.objects',
        'OrgRequest.objects',
        # TD-201. A comment is reached ONLY through its org-fenced request (req.comments), never
        # by a top-level manager query — if one appears in views_admin it needs a pragma saying why.
        'OrgRequestComment.objects',
        # TD-204. Same rule, and it matters more here: an analysis carries the cited file paths and
        # the engineer's hours, neither of which the requesting organisation may ever see. Reached
        # through req.analyses so the request's own fence covers it.
        'OrgRequestAnalysis.objects',
        # Sponsor spending S4. A row says what a named student bought and for how much, so an
        # unfenced manager query is the leak. Every read goes through `spend_report._txns`;
        # the ONE deliberate cross-organisation write (an owner verdict applies to the shop
        # everywhere) carries its own pragma saying so.
        'BursarySpendTxn.objects',
        # Tenant invoices (2026-09-14). An invoice and its receipts are a tenant's bill and its
        # payments; an unfenced manager query is one tenant reading another's money.
        'Invoice.objects', 'InvoiceReceipt.objects',
    )

    #: ⚠ THE SCAN'S SCOPE IS ITS STRENGTH AND ITS BLIND SPOT AT ONCE. It began as
    #: views_admin.py alone; S4 put admin-facing queries in `spend_report.py`, which the guard
    #: would have been structurally unable to see. **A new module that queries a watched model
    #: for an admin surface belongs on this list on the day it is written.**
    #: ⚠ AN ENTRY IS A FILE **OR** A PACKAGE DIRECTORY (code health H3). `scan_targets()`
    #: walks a directory recursively, so when H11 turns `views_admin.py` into
    #: `views_admin/`, this tuple changes by one character and the guard keeps seeing every
    #: query — including ones in submodules that did not exist when it was written.
    SCANNED = ('views_admin.py', 'spend_report.py', 'spend_category.py',
               'spending_import.py', 'spend_summary.py', 'spend_sponsor.py', 'invoicing.py',
               # Programme Overview (2026-09-15) — a pure aggregation module that queries
               # ScholarshipApplication and BursarySpendTxn for an admin surface, so it joined
               # this tuple on the day it was written, per the note above.
               'programme_overview.py',
               # TD-240, closed at code health H3 (2026-09-18). Scanned with BOTH vocabularies:
               # the admin tokens above, and `SPONSOR_WATCHED` below.
               'views_sponsor.py')

    #: ⚠ A LEDGER, NOT AN EXEMPTION LIST — the same idea as `NO_DOOR`. A file here is a
    #: DECISION somebody wrote down, and the reason is the check. Adding a name without a
    #: reason is the thing this is meant to make impossible.
    #:
    #: EMPTY since TD-240 closed (code health H3, 2026-09-18) — `views_sponsor.py` was its
    #: only entry and is now in SCANNED. Kept, not deleted: the next file that cannot be
    #: scanned today needs somewhere to say so out loud.
    NOT_YET_SCANNED = {}

    # ── The SPONSOR vocabulary (TD-240) ──────────────────────────────────────────────
    #: A sponsor endpoint is NOT fenced on `owning_organisation` — a Sponsor is a
    #: platform-level account with no organisation at all. It is fenced on the SPONSOR, and
    #: there are exactly two safe shapes:
    #:   * read off the sponsor row (`sponsor.sponsorships`, `sponsor.donations`) — safe by
    #:     construction, because the sponsor was resolved from the caller's own JWT; or
    #:   * narrow a pool queryset through `pool.for_sponsor(...)`, which keeps a sponsor to
    #:     the gift programmes they have been ACCEPTED into.
    #: The two builders below return every pool-eligible student on the PLATFORM. Using one
    #: in a sponsor-facing file without `for_sponsor` in the same window is the sponsor
    #: equivalent of a missing org fence — so it must carry a `# sponsor-fence:` pragma
    #: saying why there is nothing to narrow.
    #: ⚠ The trailing `(` is load-bearing: these names are also written in prose in the very
    #: comments that explain the fence, and a guard that fired on its own documentation would
    #: be deleted within a month. Only a CALL is a query.
    SPONSOR_WATCHED = ('display_pool_queryset(', 'eligible_pool_queryset(')
    SPONSOR_SCANNED = ('views_sponsor.py',)
    #: What counts as a narrowing in the sponsor vocabulary, seen in the same window.
    SPONSOR_FENCES = ('for_sponsor(',)

    #: Either pragma satisfies either scan: the pragma's TEXT is what says which fence it
    #: is claiming, and a reader needs the reason far more than the spelling.
    PRAGMAS = ('org-fence:', 'sponsor-fence:')

    #: ⚠⚠ **A FINDINGS LEDGER, AND IT MAY ONLY SHRINK.** A line here is a watched query that
    #: is NOT fenced and that this sprint deliberately did not touch — never a query somebody
    #: decided was fine (that is what a pragma is for). Keyed on the stripped source line, so
    #: it survives the line moving but not the line changing. `test_the_unfenced_ledger_only_shrinks`
    #: fails the moment an entry is fixed or fenced, with "remove me".
    #:
    #: EMPTY since TD-258 was fixed (2026-09-18). Its single entry was
    #: `SponsorFundView.post` reading an application by bare id; that view now resolves
    #: through `pool.for_sponsor(pool.display_pool_queryset(...), sponsor)` like its
    #: sibling, so the line is no longer an offence and the ledger no longer records one.
    #: Kept, not deleted: the MECHANISM is the point — the next unfenced query somebody
    #: consciously leaves alone needs somewhere to say so out loud, and
    #: `test_the_unfenced_ledger_only_shrinks` is what stops that note outliving the problem.
    KNOWN_UNFENCED = {}

    def _scan(self, entry):
        """(display name, source) for every file an entry names."""
        return read_scanned(_APP_DIR, entry)

    def test_every_scanned_entry_is_real_and_actually_carries_a_watched_query(self):
        """THE FLOOR. A scan that silently matches nothing makes every assertion above vacuous,
        and the guard then passes for ever while protecting nothing. This is the same shape as
        the repair-door guard's own floor, and it exists because S4 widened SCANNED: dropping a
        file from that tuple must FAIL here rather than quietly stop looking.

        ⚠ Since H3 an entry may be a PACKAGE, and the same floor applies to it: the package must
        exist, must hold at least one `*.py`, and the watched queries must still be findable
        somewhere inside it — so a split that loses the queries fails HERE, not silently."""
        watched = self.WATCHED + self.SPONSOR_WATCHED
        for entry in self.SCANNED:
            sources = list(self._scan(entry))
            self.assertTrue(sources, f'SCANNED names a missing file or empty package: {entry}')
            self.assertTrue(
                any(tok in src for _name, src in sources for tok in watched),
                f'{entry} carries no watched query - it is either the wrong file or the '
                f'queries moved, and either way this guard is now watching nothing.')

    def test_the_modules_that_query_watched_models_are_all_scanned(self):
        """The other half: a NEW admin-facing module that queries a watched model must join
        SCANNED. Without this, S4's own mistake repeats - move the query one file sideways and
        the guard is structurally blind to it."""
        candidates = ('views_admin.py', 'views_sponsor.py', 'views_branding.py',
                      'spend_report.py', 'spend_category.py', 'spending_import.py',
                      'spend_summary.py', 'spend_sponsor.py', 'invoicing.py', 'invoice_pdf.py',
                      'programme_overview.py')
        unscanned = []
        for filename in candidates:
            path = os.path.join(_APP_DIR, filename)
            if (not os.path.isfile(path) or filename in self.SCANNED
                    or filename in self.NOT_YET_SCANNED):
                continue
            with open(path, encoding='utf-8') as fh:
                src = fh.read()
            if any(tok in src for tok in self.WATCHED):
                unscanned.append(filename)
        self.assertEqual(unscanned, [],
                         f'These query a watched model and are not in SCANNED: {unscanned}')

    def _offences(self):
        """Both passes: the admin vocabulary over SCANNED, the sponsor one over
        SPONSOR_SCANNED. `views_sponsor.py` is in both, on purpose — a sponsor file may still
        reach for an admin-watched manager, which is exactly the finding the audit made."""
        yield from find_offences(_APP_DIR, self.SCANNED, self.WATCHED,
                                 pragmas=self.PRAGMAS)
        yield from find_offences(_APP_DIR, self.SPONSOR_SCANNED, self.SPONSOR_WATCHED,
                                 fences=self.SPONSOR_FENCES, pragmas=self.PRAGMAS)

    def test_raw_admin_queries_are_fenced(self):
        offenders = []
        for name, line, tok, text in self._offences():
            if text in self.KNOWN_UNFENCED.get(name, {}):
                continue        # a logged finding — see KNOWN_UNFENCED and the shrink test
            offenders.append(f'{name}:{line} — {tok}')
        self.assertEqual(
            offenders, [],
            'Raw query without an `# org-fence:` / `# sponsor-fence:` pragma '
            '(cross-tenant or cross-sponsor read/write risk):\n' + '\n'.join(offenders))

    def test_the_unfenced_ledger_only_shrinks(self):
        """A logged finding must still BE one. When the query is fixed, fenced or deleted, this
        fails with "remove me" — so the ledger can never quietly outlive the problem it records,
        and can never be padded with lines that are no longer offences."""
        live = {(name, text) for name, _line, _tok, text in self._offences()}
        stale = []
        for name, entries in self.KNOWN_UNFENCED.items():
            for text in entries:
                if (name, text) not in live:
                    stale.append(f'{name}: {text}')
        self.assertEqual(
            stale, [],
            'KNOWN_UNFENCED entries that are no longer unfenced offences — remove them '
            '(and say so in the technical-debt register):\n' + '\n'.join(stale))

    def test_the_sponsor_vocabulary_is_actually_looking_at_something(self):
        """The sponsor half's own floor. `SPONSOR_WATCHED` names helper functions rather than
        managers, so a rename in `pool.py` would leave the tokens matching nothing and the
        sponsor scan silently green. Both names must still be real, exported helpers."""
        from apps.scholarship import pool
        for token in self.SPONSOR_WATCHED:
            self.assertTrue(
                callable(getattr(pool, token.rstrip('('), None)),
                f'SPONSOR_WATCHED names `{token}`, which is no longer a helper in pool.py — '
                f'the sponsor half of this guard is now watching nothing.')
        for fence in self.SPONSOR_FENCES:
            self.assertTrue(
                callable(getattr(pool, fence.rstrip('('), None)),
                f'SPONSOR_FENCES names `{fence}`, which is no longer a helper in pool.py.')


# ── The scanner itself, proven against a throwaway tree (code health H3) ──────────────
#
# H11 turns `views_admin.py` into `views_admin/`. The danger is not that the guard errors —
# that would be loud — but that it goes quiet: a scan that names a file which no longer
# exists, or that stops at the package's `__init__.py`, is green and protects nothing. These
# two tests exercise `scan_targets` / `find_offences` on a tiny fake app so the package
# behaviour is proven WITHOUT depending on the real tree ever being split.

_PRAGMA_FREE = (
    'class AdminThingView(_AdminBase):\n'
    '    def get(self, request):\n'
    '        return ScholarshipApplication.objects.all()\n'
)
_PRAGMA_ED = (
    'class AdminThingView(_AdminBase):\n'
    '    def get(self, request):\n'
    '        # org-fence: scoped through _org_scoped, see the base gate.\n'
    '        return ScholarshipApplication.objects.all()\n'
)


def _fake_package(root, **files):
    pkg = root / 'views_admin'
    (pkg / 'nested').mkdir(parents=True)
    (pkg / '__init__.py').write_text('from .requests import *  # noqa\n', encoding='utf-8')
    for name, body in files.items():
        (pkg / name.replace('/', os.sep)).write_text(body, encoding='utf-8')
    return pkg


def test_a_package_submodule_is_scanned_like_a_file(tmp_path):
    """THE H11 PROOF, and it is the only one that matters: a watched query with NO pragma,
    sitting in a submodule the guard has never heard of, must still be caught."""
    _fake_package(tmp_path, **{'requests.py': _PRAGMA_ED,
                               'nested/invoices.py': _PRAGMA_FREE})

    found = list(find_offences(str(tmp_path), ('views_admin',),
                               ('ScholarshipApplication.objects',),
                               pragmas=('org-fence:',)))

    # The pragma-ed submodule is silent; the pragma-free one two levels down is not.
    assert [(name, tok) for name, _line, tok, _text in found] == [
        ('views_admin/nested/invoices.py', 'ScholarshipApplication.objects')]
    # …and it is reported at the real line, in the real submodule, not at the package root.
    assert found[0][1] == 3


def test_scan_targets_reads_a_file_and_a_package_the_same_way(tmp_path):
    """Today's behaviour must not move: a filename entry still resolves to exactly that one
    file, and a missing entry still resolves to nothing (which the floor test turns red)."""
    (tmp_path / 'views_admin.py').write_text(_PRAGMA_ED, encoding='utf-8')
    assert [os.path.basename(p) for p in scan_targets(str(tmp_path), 'views_admin.py')] \
        == ['views_admin.py']
    assert scan_targets(str(tmp_path), 'not_here.py') == []

    _fake_package(tmp_path, **{'requests.py': _PRAGMA_ED, 'nested/invoices.py': _PRAGMA_ED})
    names = [os.path.relpath(p, str(tmp_path)).replace(os.sep, '/')
             for p in scan_targets(str(tmp_path), 'views_admin')]
    assert names == ['views_admin/__init__.py', 'views_admin/nested/invoices.py',
                     'views_admin/requests.py']
