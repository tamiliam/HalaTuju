"""A1.13 third review — one regression per finding.

  Med 1  the offer-lapse job and the parent-call record take the APPLICATION lock before the
         Sponsorship (the house order the withdrawal, the cancel and the award-email job keep).
  Med 2  after a withdrawal and a re-award, the voided agreement is no agreement: the student is
         shown the NEW contract (the preview), the agreement GET answers 404, and she can sign.
  Low 1  the signed PDF of a withdrawn award is never swept as an orphan blob.

SQLite ignores ``select_for_update``, so the ORDER is proved with a call-order spy (as in
`test_a113_review_fixes.py`). All on dummy data; the PDF / storage seams are mocked.
"""
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.db.models.query import QuerySet
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.scholarship import agreement_guard, parent_call
from apps.scholarship import award_withdrawal as wd
from apps.scholarship import sponsorship as svc
from apps.scholarship.models import (
    BursaryAgreement, ScholarshipCohort, Sponsorship, StudentActivity,
)
from apps.scholarship.tests.factories import (
    TEST_JWT_SECRET, authed_client, make_admin, make_application, make_student,
)
from apps.scholarship.tests.test_a113_review_fixes import (
    REASON, _accept, _order_spy, _sponsor,
)
from apps.scholarship.tests.test_bursary_agreement import (
    _add_parent_ic, _cumig, _fund, _fundable_app, _mock_seams, _twin,
)

HOUSE_ORDER = ['lock_application', 'sfu:ScholarshipApplication', 'sfu:Sponsorship']
SHARED = '017-555 4444'


# ── Med 1 (a): the offer-lapse job ─────────────────────────────────────────────────────────────

@override_settings(BURSARY_AGREEMENT_ENABLED=False)
class TestLapseLockOrder(TestCase):
    def setUp(self):
        self.app = make_application('recommended', award_amount=Decimal('3000'))
        self.sp = svc.fund_student(_sponsor(self.app.programme), self.app)
        Sponsorship.objects.filter(pk=self.sp.pk).update(
            accept_deadline=timezone.now() - timedelta(days=1))

    def test_the_application_is_locked_before_the_sponsorship(self):
        order, (p1, p2) = _order_spy()
        with p1, p2:
            self.assertEqual(svc.lapse_expired_offers()['lapsed'], 1)
        self.assertEqual(order[:3], HOUSE_ORDER)
        self.sp.refresh_from_db()
        self.app.refresh_from_db()
        self.assertEqual((self.sp.status, self.app.status), ('lapsed', 'recommended'))

    def test_an_offer_accepted_after_the_list_was_read_is_still_left_alone(self):
        real = svc._expired_offers

        def read_then_accept(now):
            rows = real(now)
            Sponsorship.objects.filter(pk=self.sp.pk).update(status='active')   # lands in between
            return rows
        with patch.object(svc, '_expired_offers', read_then_accept):
            self.assertEqual(svc.lapse_expired_offers()['lapsed'], 0)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.status, 'active')


# ── Med 1 (b): the parent-call record ──────────────────────────────────────────────────────────

@override_settings(BURSARY_AGREEMENT_ENABLED=True)
class TestParentCallLockOrder(TestCase):
    """A call that clears a flag holding signing re-arms the student's armed offers (TD-347). It
    used to lock the offer rows and then insert the call row (which share-locks the application):
    Sponsorship before application, the reverse of the withdrawal."""

    def setUp(self):
        self.profile = make_student(guardians=[{'name': 'Ravi', 'phone': SHARED}], contact_phone=SHARED)
        self.app = make_application('awarded', student=self.profile)
        self.offer = Sponsorship.objects.create(
            sponsor=_sponsor(self.app.programme), application=self.app, amount=Decimal('2000'),
            status='offered', accept_deadline=timezone.now() + timedelta(days=3))

    def test_the_applications_are_locked_before_the_offers(self):
        self.assertTrue(parent_call.needs_parent_call(self.profile))     # signing is held
        order, (p1, p2) = _order_spy()
        with p1, p2:
            parent_call.record_call(self.profile, application=self.app, outcome='shared_confirmed',
                                    consent=True, number=SHARED)
        locks = [o for o in order if o in ('sfu:ScholarshipApplication', 'sfu:Sponsorship')]
        self.assertEqual(locks[:2], ['sfu:ScholarshipApplication', 'sfu:Sponsorship'])
        self.assertLess(order.index('sfu:StudentProfile'), order.index('sfu:ScholarshipApplication'))
        self.assertFalse(parent_call.needs_parent_call(self.profile))

    def test_every_application_of_the_student_is_locked(self):
        other = make_application('recommended', student=self.profile, cohort=None)
        seen = []
        real = QuerySet.select_for_update

        def sfu(qs, *a, **k):
            locked = real(qs, *a, **k)
            if qs.model.__name__ == 'ScholarshipApplication':
                seen.append(sorted(locked.values_list('pk', flat=True)))
            return locked
        with patch.object(QuerySet, 'select_for_update', sfu):
            parent_call.record_call(self.profile, application=self.app, outcome='shared_confirmed',
                                    consent=True, number=SHARED)
        self.assertIn(sorted([self.app.pk, other.pk]), seen)

    @override_settings(BURSARY_AGREEMENT_ENABLED=False)
    def test_with_signing_off_the_call_takes_no_application_lock(self):   # unchanged path
        order, (p1, p2) = _order_spy()
        with p1, p2:
            parent_call.record_call(self.profile, application=self.app, outcome='shared_confirmed',
                                    consent=True, number=SHARED)
        self.assertNotIn('sfu:ScholarshipApplication', order)
        self.assertNotIn('sfu:Sponsorship', order)


# ── Med 2 + Low 1: a re-awarded student signs the NEW contract ─────────────────────────────────

@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestReAwardAfterWithdrawal(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c3', name='B40', year=2026)

    def setUp(self):
        for p in _mock_seams():
            p.start()
            self.addCleanup(p.stop)
        self.super = make_admin(super_admin=True)
        self.org = _cumig()
        self.app = _fundable_app(self.cohort, suffix='a113t', org=self.org, source=_twin(self.org))
        _add_parent_ic(self.app)
        self.sp_a = _fund(self.app)
        _accept(self.app)
        self.ag = BursaryAgreement.objects.get(application=self.app)
        self.old_pdf = self.ag.pdf_storage_path
        with self.captureOnCommitCallbacks(execute=True):
            wd.withdraw_award(self.app, by_admin=self.super, reason=REASON)
        self.sp_b = svc.fund_student(_sponsor(self.app.programme), self.app)     # re-awarded
        self.student = authed_client(self.app.profile)

    def test_the_student_sees_the_new_contract_then_signs_it(self):
        self.ag.refresh_from_db()
        self.assertTrue(agreement_guard.is_void(self.ag))
        resp = self.student.get('/api/v1/scholarship/award/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertNotIn('bursary_agreement', resp.data)                  # not "already signed"
        self.assertIn('bursary_preview', resp.data)                       # the new contract to sign
        self.assertIsNotNone(resp.data['offer'])
        self.assertEqual(self.student.get('/api/v1/scholarship/bursary-agreement/').status_code, 404)

        _accept(self.app)                                                 # she signs the new one
        self.ag.refresh_from_db()
        self.assertEqual(BursaryAgreement.objects.filter(application=self.app).count(), 1)
        self.assertEqual(self.ag.sponsorship_id, self.sp_b.pk)            # the SAME row, re-signed
        self.assertTrue(self.ag.binds)
        self.assertFalse(agreement_guard.is_void(self.ag))
        resp = self.student.get('/api/v1/scholarship/bursary-agreement/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.data['status'], 'binds')

    def test_live_agreement_hides_only_a_void_row(self):
        self.app.refresh_from_db()
        self.assertIsNone(agreement_guard.live_agreement(self.app))          # voided
        _accept(self.app)
        self.app.refresh_from_db()
        self.assertEqual(agreement_guard.live_agreement(self.app).pk, self.ag.pk)   # signed again
        self.assertIsNone(agreement_guard.live_agreement(make_application('recommended')))  # none

    def test_the_withdrawn_signed_pdf_is_never_an_orphan(self):
        from apps.scholarship.management.commands.cleanup_orphan_blobs import known_paths
        self.assertTrue(self.old_pdf)
        meta = StudentActivity.objects.get(application=self.app, event='award_withdrawn').meta
        self.assertEqual(meta['agreement_voided']['pdf_storage_path'], self.old_pdf)
        # The re-signing writes a NEW path on the row (a later second in production).
        BursaryAgreement.objects.filter(pk=self.ag.pk).update(pdf_storage_path='x/new-signing.pdf')
        known = known_paths()
        self.assertIn(self.old_pdf, known)
        self.assertIn('x/new-signing.pdf', known)

    def test_the_admin_file_shows_no_agreement_for_a_void_row(self):   # fourth review, Low
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        self.app.refresh_from_db()
        ser = AdminApplicationDetailSerializer(self.app)
        self.assertIsNone(ser.get_bursary_agreement(self.app))           # not "draft, old amount"
        _accept(self.app)
        self.app.refresh_from_db()
        self.assertEqual(ser.get_bursary_agreement(self.app)['status'], 'binds')

    def test_a_withdrawal_with_no_agreement_adds_no_path(self):
        from apps.scholarship.activity import withdrawn_agreement_pdfs
        StudentActivity.objects.filter(event='award_withdrawn').update(meta={'agreement_voided': None})
        self.assertEqual(withdrawn_agreement_pdfs(), set())


# ── Fourth review, Med: a void agreement pins no template ──────────────────────────────────────

def _deploy_next(programme, version):
    """Deploy a new version of the gift's template; ``contracts.deploy`` archives the old one."""
    from apps.scholarship import contracts
    from apps.scholarship.tests.contract_helpers import make_deployable
    t = make_deployable(version, programme=programme.code)
    contracts.submit_for_deployment(t)
    return contracts.deploy(t, is_super=True)


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET,
                   BURSARY_AGREEMENT_ENABLED=True)
class TestReAwardUsesTheCurrentTemplate(TestCase):
    """Withdraw, archive v1 / activate v2, re-award: the preview, the quiz, the signing and the
    payment schedule all follow v2 — never the void row's pinned v1."""

    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c4', name='B40', year=2026)

    def setUp(self):
        for p in _mock_seams():
            p.start()
            self.addCleanup(p.stop)
        self.super = make_admin(super_admin=True)
        self.org = _cumig()
        self.app = _fundable_app(self.cohort, suffix='a113v', org=self.org, source=_twin(self.org))
        _add_parent_ic(self.app)
        _fund(self.app)
        _accept(self.app)
        self.ag = BursaryAgreement.objects.get(application=self.app)
        self.v1 = self.ag.template
        with self.captureOnCommitCallbacks(execute=True):
            wd.withdraw_award(self.app, by_admin=self.super, reason=REASON)
        self.v2 = _deploy_next(self.app.programme, '2026-bursary-v2')
        self.v1.refresh_from_db()
        self.sp_b = svc.fund_student(_sponsor(self.app.programme), self.app)     # re-awarded
        self.app.refresh_from_db()
        self.student = authed_client(self.app.profile)

    def test_the_whole_path_follows_v2(self):
        from apps.scholarship import bursary, contract_scope, payments
        self.assertEqual(self.v1.status, 'archived')
        self.assertEqual(self.ag.template_id, self.v1.pk)                  # the void row still names v1
        self.assertEqual(contract_scope.template_for_application(self.app), self.v2)
        self.assertEqual(payments._schedule_row(self.app).template_id, self.v2.pk)

        # The preview renders v2, and says her v1 quiz does not count.
        with patch.object(bursary, 'render_agreement_html', wraps=bursary.render_agreement_html) as r:
            resp = self.student.get('/api/v1/scholarship/award/')
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(r.call_args.kwargs['template'], self.v2)
        self.assertFalse(resp.data['bursary_preview']['comprehension_passed'])

        # The quiz serves v2.
        quiz = self.student.get('/api/v1/scholarship/award/comprehension-quiz/')
        self.assertEqual(quiz.status_code, 200, quiz.content)
        self.assertEqual(quiz.data['template_version'], self.v2.version)

        # Signing refuses until she retakes the quiz on v2.
        with self.assertRaises(svc.SponsorshipError) as cm:
            _accept(self.app)
        self.assertEqual(cm.exception.code, 'comprehension_stale')
        passed = self.student.post('/api/v1/scholarship/award/comprehension/',
                                   {'template_version': self.v2.version}, format='json')
        self.assertEqual(passed.status_code, 200, passed.content)
        self.app.refresh_from_db()
        self.assertEqual(self.app.comprehension_template_id, self.v2.pk)

        _accept(self.app)
        self.ag.refresh_from_db()
        self.assertEqual((self.ag.template_id, self.ag.version), (self.v2.pk, self.v2.version))
        self.assertEqual(self.ag.sponsorship_id, self.sp_b.pk)
        self.app.refresh_from_db()
        self.assertEqual(contract_scope.template_for_application(self.app), self.v2)
        self.assertEqual(payments._schedule_row(self.app).template_id, self.v2.pk)

    def test_a_binding_agreement_still_keeps_its_pin(self):     # the unchanged rule
        from apps.scholarship import contract_scope
        self.student.post('/api/v1/scholarship/award/comprehension/',
                          {'template_version': self.v2.version}, format='json')
        self.app.refresh_from_db()
        _accept(self.app)
        _deploy_next(self.app.programme, '2026-bursary-v3')      # a later redeploy
        self.app.refresh_from_db()
        self.assertEqual(contract_scope.template_for_application(self.app), self.v2)
