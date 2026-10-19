"""Request #39 Sprint 3 — MIXED permission sets, end to end on the server.

Nobody holds a mixed set yet: `PartnerAdmin.permissions` is NULL for everyone (the preset), and the
editor that saves one is Sprint 4. So each test here sets the list DIRECTLY on the row, exactly what
a reviewed SQL update would do, and asks the LIVE gates. The golden table
(`apps/courses/tests/test_permission_presets.py`) proves the presets did not move; this file proves
a custom set moves access exactly as the catalogue says — and that the safety rules hold for it.

Lessons 2026-09-28 ("test the neighbouring states"): every combination below is one nobody holds
today, on purpose. The acceptance list is the roadmap's Sprint 3 section.
"""
from datetime import date
from types import SimpleNamespace
from unittest import mock

from apps.courses.models import PartnerAdmin
from apps.scholarship.models import ScholarshipApplication
from apps.scholarship.programme_overview import sections_for
from apps.scholarship.services import is_review_target, may_assign_to
from apps.scholarship.tests import test_payment_endpoints as pe
from apps.scholarship.tests.factories import make_application
from apps.scholarship.views_admin import _AdminBase

APPS = '/api/v1/admin/scholarship/applications/'
SPENDING = '/api/v1/admin/scholarship/spending/'
SPENDING_FLAGS = '/api/v1/admin/scholarship/spending/flag/?merchant=Shop'
RUNS = '/api/v1/admin/scholarship/payment-runs/'
FUNDING = '/api/v1/admin/scholarship/payments/funding-summary/'
ASSIGNABLE = '/api/v1/admin/scholarship/assignable-admins/'
REVIEWERS = '/api/v1/admin/reviewers/'


def _grant(admin, keys):
    """What a reviewed SQL update (or, from Sprint 4, the editor) would store; re-read like a request."""
    PartnerAdmin.objects.filter(pk=admin.pk).update(permissions=list(keys))
    admin.refresh_from_db()
    return admin


def _unassigned_app(case):
    """A second awarded student in organisation A, assigned to nobody (through the factory)."""
    return make_application('awarded', cohort=case.cohort_a)


class TestReviewerPlusSpending(pe._Base):
    """Rohini's combination: Spending page 200, Applications assigned-only, no Payments, no money on
    the Overview (the Overview is preset-bound, R2: she sees the reviewer's sections)."""

    def setUp(self):
        super().setUp()
        _grant(self.reviewer, ['review', 'spending'])

    def test_the_spending_page_and_its_flags_open(self):
        self._auth('pe-rv')
        self.assertEqual(self.client.get(SPENDING).status_code, 200)
        self.assertEqual(self.client.get(SPENDING_FLAGS).status_code, 200)

    def test_the_preset_reviewer_is_still_refused_spending(self):
        PartnerAdmin.objects.filter(pk=self.reviewer.pk).update(permissions=None)
        self._auth('pe-rv')
        self.assertEqual(self.client.get(SPENDING).status_code, 403)

    def test_applications_stay_assigned_only(self):
        self.assertEqual(_AdminBase()._b40_scope(self.reviewer), 'assigned')
        self._auth('pe-rv')
        resp = self.client.get(APPS)
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['applications'], [])     # nothing is assigned to her
        self.assertEqual(self.client.get(f'{APPS}{self.app_a.id}/').status_code, 403)

    def test_no_payments(self):
        self._auth('pe-rv')
        self.assertEqual(self.client.get(RUNS).status_code, 403)
        self.assertEqual(self.client.get(FUNDING).status_code, 403)

    def test_no_money_on_the_overview(self):
        self.assertEqual(sections_for(self.reviewer), ('mine',))


class TestFinancePlusReview(pe._FinanceBase):
    """Open question 1 (owner, 2026-10-19): a Finance person GIVEN Review sees the files of the
    students ASSIGNED to them — never the others — and the funding summary they already read keeps
    exactly its key set."""

    def setUp(self):
        super().setUp()
        _grant(self.finance, ['payments_approve', 'review'])
        ScholarshipApplication.objects.filter(pk=self.app_a.pk).update(assigned_to=self.finance)

    def test_the_assigned_file_opens(self):
        self._auth('pe-fi')
        self.assertEqual(self.client.get(f'{APPS}{self.app_a.id}/').status_code, 200)

    def test_an_unassigned_file_is_refused(self):
        other = _unassigned_app(self)
        self._auth('pe-fi')
        self.assertEqual(self.client.get(f'{APPS}{other.id}/').status_code, 403)

    def test_the_list_is_their_assigned_students_only(self):
        _unassigned_app(self)
        self._auth('pe-fi')
        ids = {a['id'] for a in self.client.get(APPS).json()['applications']}
        self.assertEqual(ids, {self.app_a.id})

    def test_the_finance_preset_alone_still_sees_no_file(self):
        PartnerAdmin.objects.filter(pk=self.finance.pk).update(permissions=None)
        self._auth('pe-fi')
        self.assertEqual(self.client.get(f'{APPS}{self.app_a.id}/').status_code, 403)
        self.assertEqual(self.client.get(APPS).status_code, 403)

    def test_the_funding_summary_key_set_is_unchanged(self):
        self._auth('pe-fi')
        rows = self.client.get(FUNDING).json()['rows']
        self.assertTrue(rows)
        for row in rows:
            self.assertEqual(set(row), pe.TestFundingSummaryEndpoint.KEYS)

    def test_they_still_approve_runs(self):
        self._auth('pe-fi')
        self.assertEqual(self.client.get(RUNS).status_code, 200)
        self.assertTrue(self.finance.has_perm('payments_approve'))

    def test_the_overview_stays_the_finance_preset_s(self):
        # R2: preset-bound. No "my cases" tile; the Applications row is their door.
        self.assertEqual(sections_for(self.finance), ('money', 'money_series'))

    def test_an_org_admin_may_assign_them_and_they_sit_on_the_reviewers_tab(self):
        self.assertTrue(may_assign_to(self.approver, self.finance))
        self._auth('pe-ap')
        row = next(r for r in self.client.get(ASSIGNABLE).json()['admins']
                   if r['id'] == self.finance.id)
        # The reviewer profile is preset-bound (R2): no profile, so no languages — shown unknown.
        self.assertEqual((row['assignable'], row['languages']), (True, []))
        ids = {r['id'] for r in self.client.get(REVIEWERS).json()['reviewers']}
        self.assertIn(self.finance.id, ids)
        self.assertNotIn(self.approver.id, ids)            # org admins stay off (owner, 2026-10-19)

    def test_they_may_be_paused_like_any_review_target(self):
        self.assertTrue(is_review_target(self.finance))
        self._auth('pe-ap')
        resp = self.client.post(f'{REVIEWERS}{self.finance.id}/pause/', {'paused': True},
                                format='json')
        self.assertEqual(resp.status_code, 200, resp.content)


class TestAdminMinusSpending(pe._Base):
    def setUp(self):
        super().setUp()
        _grant(self.maker, ['see_all', 'payments_prepare'])

    def test_spending_is_refused_and_the_rest_stays(self):
        self._auth('pe-mk')
        self.assertEqual(self.client.get(SPENDING).status_code, 403)
        self.assertEqual(self.client.get(SPENDING_FLAGS).status_code, 403)
        self.assertEqual(self.client.get(RUNS).status_code, 200)
        self.assertEqual(self.client.get(APPS).status_code, 200)
        self.assertEqual(_AdminBase()._b40_scope(self.maker), 'all')


class TestQcWithoutSeeAll(pe._Base):
    """`qc` needs `see_all`. A stored list naming `qc` alone is read FAIL-CLOSED (the key is dropped,
    never `see_all` added); the Sprint 4 editor refuses to save it."""

    def setUp(self):
        super().setUp()
        _grant(self.qc, ['qc'])

    def test_the_list_is_read_without_qc(self):
        self.assertEqual(self.qc.permission_set, ())
        self.assertFalse(self.qc.has_perm('qc'))
        self.assertEqual(_AdminBase()._b40_scope(self.qc), 'none')

    def test_the_qc_gate_and_the_list_refuse_them(self):
        view = _AdminBase()
        case = SimpleNamespace(owning_organisation_id=self.org_a.id, assigned_to_id=None,
                               status='interviewed', verdict_decided_by='')
        with mock.patch.object(view, 'get_admin', return_value=self.qc), \
                mock.patch.object(view, '_get_application', return_value=case):
            _, _, err = view._require_qc(None, 1)
        self.assertEqual(err.status_code, 403)
        self._auth('pe-qc')
        self.assertEqual(self.client.get(APPS).status_code, 403)


class TestFinanceWithoutApprove(pe._FinanceBase):
    """Finance with approve REMOVED loses the approval; the org admin's per-run fallback takes it."""

    def setUp(self):
        super().setUp()
        _grant(self.finance, [])

    def test_the_approval_moves_to_the_fallback(self):
        run_id = self._create_run('pe-mk').json()['id']
        self.assertEqual(self._sign('pe-mk', 'Maker One', run_id).status_code, 200)
        self.assertEqual(self._sign('pe-fi', 'Fin One', run_id).status_code, 403)
        body = self._detail('pe-ap', run_id)
        self.assertEqual((body['your_step'], body['approver_fallback']), ('approve', True))

    def _detail(self, uid, run_id):
        self._auth(uid)
        return self.client.get(f'{RUNS}{run_id}/').json()


class TestSafetyRulesHoldForCustomSets(pe._FinanceBase):
    """The rules key on the PERSON, so a mixed set cannot get round them."""

    def _qc(self, admin, **case):
        view = _AdminBase()
        fields = dict(owning_organisation_id=self.org_a.id, assigned_to_id=None,
                      status='interviewed', verdict_decided_by='')
        fields.update(case)
        with mock.patch.object(view, 'get_admin', return_value=admin), \
                mock.patch.object(view, '_get_application',
                                  return_value=SimpleNamespace(**fields)):
            _, _, err = view._require_qc(None, 1)
        return None if err is None else err.data.get('code', err.status_code)

    def test_no_self_qc_for_an_admin_given_qc(self):
        _grant(self.maker, ['see_all', 'qc', 'payments_prepare'])
        self.assertIsNone(self._qc(self.maker))                              # they may QC others'
        self.assertEqual(self._qc(self.maker, assigned_to_id=self.maker.id), 'self_qc_forbidden')
        self.assertEqual(self._qc(self.maker, verdict_decided_by='MAKER@x.com'),
                         'self_verdict_qc_forbidden')

    def test_the_maker_never_approves_their_own_run(self):
        _grant(self.maker, ['see_all', 'spending', 'payments_prepare', 'payments_approve'])
        PartnerAdmin.objects.filter(pk=self.maker.pk).update(first_seen_at=date(2026, 7, 1))
        run_id = self._create_run('pe-mk').json()['id']
        self.assertEqual(self._sign('pe-mk', 'Maker One', run_id).status_code, 200)
        resp = self._sign('pe-mk', 'Maker One', run_id)
        self.assertEqual((resp.status_code, resp.json()['code']), (400, 'same_signer'))

    def test_assignment_only_to_review_holders(self):
        _grant(self.qc, ['see_all', 'qc'])                    # the qc preset, written out
        _grant(self.maker, ['see_all', 'qc'])                  # an admin given QC, not Review
        _grant(self.reviewer, ['spending'])                    # a reviewer with Review taken away
        for target in (self.qc, self.maker, self.reviewer, self.finance):
            self.assertFalse(may_assign_to(self.approver, target), target.role)
        _grant(self.finance, ['payments_approve', 'review'])
        self.assertTrue(may_assign_to(self.approver, self.finance))
        # The endpoint answers the same: a non-holder is `bad_assignee`, as an unknown id is.
        from apps.scholarship.views_admin.verdict import AdminAssignReviewerView
        case = SimpleNamespace(owning_organisation_id=self.org_a.id, status='profile_complete')
        self._auth('pe-ap')
        with mock.patch.object(AdminAssignReviewerView, '_scoped_application',
                               return_value=(case, None)), \
                mock.patch('apps.scholarship.views_admin.verdict.assign_reviewer'), \
                mock.patch('apps.scholarship.views_admin.verdict.AdminApplicationDetailSerializer',
                           return_value=SimpleNamespace(data={})):
            refused = self.client.post(f'{APPS}1/assign/', {'reviewer_id': self.maker.id},
                                       format='json')
            taken = self.client.post(f'{APPS}1/assign/', {'reviewer_id': self.finance.id},
                                     format='json')
        self.assertEqual((refused.status_code, refused.json()['code']), (400, 'bad_assignee'))
        self.assertEqual(taken.status_code, 200)

    def test_a_reviewer_without_review_cannot_hold_or_work_a_case(self):
        _grant(self.reviewer, ['spending'])
        self.assertFalse(is_review_target(self.reviewer))
        self.assertEqual(_AdminBase()._b40_scope(self.reviewer), 'none')
        ScholarshipApplication.objects.filter(pk=self.app_a.pk).update(assigned_to=self.reviewer)
        self.app_a.refresh_from_db()
        self.assertFalse(_AdminBase()._can_review_app(self.reviewer, self.app_a))
