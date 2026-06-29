"""Standardised assistance amount (2026-06-29).

The award is fixed by pathway (STPM → RM3,000, else RM2,000), auto-applied when a reviewer
records an APPROVE verdict, cleared on DECLINE, and only a SUPER may override it (tested in
test_sponsorship). Here: the pure rule + the record-verdict auto-apply/clear behaviour +
the proposed_award_amount serializer field.
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from rest_framework.test import APIClient

from django.utils import timezone

from apps.courses.models import StudentProfile, PartnerAdmin
from apps.scholarship import award
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort, ApplicantDocument
from apps.scholarship.tests.test_sponsorship import _token, TEST_JWT_SECRET


def _cohort():
    return ScholarshipCohort.objects.create(code='pa', name='B40', year=2026)


def _app(cohort, *, pathway='matric', status='interviewed', suffix='1'):
    p = StudentProfile.objects.create(supabase_user_id=f'aw-{suffix}', grades={'bm': 'A'}, exam_type='spm')
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=p, status=status, chosen_pathway=pathway)


def _add_not_genuine_offer(app):
    """An offer letter the genuineness scorer judged suspect → pathway 'offer_not_official'."""
    return ApplicantDocument.objects.create(
        application=app, doc_type='offer_letter', storage_path=f'{app.id}/offer/x',
        vision_fields={'authenticity': {'status': 'suspect'}}, vision_run_at=timezone.now())


class TestProposedAmountRule(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_stpm_is_3000(self):
        app = _app(self.cohort, pathway='stpm', suffix='s')
        self.assertEqual(award.proposed_award_amount(app), Decimal('3000'))

    def test_stpm_continuing_is_1000(self):
        # Cohort year is 2026; a 2025 reporting date = started last year → one year left.
        import datetime
        app = _app(self.cohort, pathway='stpm', suffix='cont')
        app.reporting_date = datetime.date(2025, 6, 10)
        app.save(update_fields=['reporting_date'])
        self.assertEqual(award.proposed_award_amount(app), Decimal('1000'))

    def test_stpm_fresh_entrant_is_3000(self):
        import datetime
        app = _app(self.cohort, pathway='stpm', suffix='fresh')
        app.reporting_date = datetime.date(2026, 6, 8)   # this intake year → full amount
        app.save(update_fields=['reporting_date'])
        self.assertEqual(award.proposed_award_amount(app), Decimal('3000'))

    def test_others_are_2000(self):
        for i, pw in enumerate(['matric', 'poly', 'university', 'asasi', 'pismp', '', 'unknown']):
            app = _app(self.cohort, pathway=pw, suffix=f'o{i}')
            self.assertEqual(award.proposed_award_amount(app), Decimal('2000'), pw)

    def test_allowed_amounts(self):
        for ok in ('1000', '1500', '2000', '2500', '3000'):
            self.assertTrue(award.is_allowed_amount(Decimal(ok)), ok)
        for bad in ('900', '2300', '3500', 'abc'):
            self.assertFalse(award.is_allowed_amount(bad), bad)


class TestVerdictDisqualifier(TestCase):
    """The confident-disqualifier markers zero the proposed amount; the merely-uncertain
    codes (a missing offer / income-needs-interview) keep the standard pathway amount."""
    def setUp(self):
        self.cohort = _cohort()

    def test_disqualifier_detected(self):
        for code in award.CONFIDENT_DISQUALIFIERS:
            v = [{'fact': 'pathway', 'status': 'review', 'evidence': [],
                  'unresolved': [{'code': code, 'params': {}}]}]
            self.assertEqual(award.verdict_disqualifier(v), code, code)

    def test_uncertain_codes_are_not_disqualifiers(self):
        for code in ('offer_letter_missing', 'income_unverified_needs_interview',
                     'offer_unreadable', 'pathway_confirm'):
            v = [{'fact': 'pathway', 'status': 'gap', 'evidence': [],
                  'unresolved': [{'code': code, 'params': {}}]}]
            self.assertEqual(award.verdict_disqualifier(v), '', code)

    def test_empty_or_none_verdict(self):
        self.assertEqual(award.verdict_disqualifier(None), '')
        self.assertEqual(award.verdict_disqualifier([]), '')

    def test_proposed_amount_is_none_on_disqualifier(self):
        app = _app(self.cohort, pathway='stpm', suffix='dq1')
        v = [{'fact': 'pathway', 'status': 'review', 'evidence': [],
              'unresolved': [{'code': 'offer_not_official', 'params': {}}]}]
        self.assertIsNone(award.proposed_award_amount(app, verdict=v))

    def test_proposed_amount_keeps_value_on_uncertain(self):
        app = _app(self.cohort, pathway='stpm', suffix='dq2')
        v = [{'fact': 'pathway', 'status': 'gap', 'evidence': [],
              'unresolved': [{'code': 'offer_letter_missing', 'params': {}}]}]
        self.assertEqual(award.proposed_award_amount(app, verdict=v), Decimal('3000'))

    def test_proposed_amount_computes_verdict_when_omitted(self):
        # A real not-genuine offer flows through build_verdict → no amount.
        app = _app(self.cohort, pathway='matric', suffix='dq3')
        _add_not_genuine_offer(app)
        self.assertIsNone(award.proposed_award_amount(app))


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAutoApplyOnVerdict(TestCase):
    """record-verdict auto-applies the pathway amount on approve, clears on decline."""
    @classmethod
    def setUpTestData(cls):
        cls.cohort = _cohort()
        PartnerAdmin.objects.create(supabase_user_id='rev', role='reviewer', is_active=True,
                                    name='Rev', email='r@x.com')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("rev", "r@x.com")}')

    def _record(self, app, overall):
        return self.client.post(
            f'/api/v1/admin/scholarship/applications/{app.id}/record-verdict/',
            {'officer_verdict': {'identity': 'pass', 'academic': 'pass', 'pathway': 'pass',
                                 'income': 'pass', 'overall': overall},
             'reason': 'ok'}, format='json')

    def _app_assigned(self, pathway, suffix):
        app = _app(self.cohort, pathway=pathway, status='interviewed', suffix=suffix)
        app.assigned_to = PartnerAdmin.objects.get(supabase_user_id='rev')
        app.save(update_fields=['assigned_to'])
        return app

    def test_approve_sets_stpm_3000(self):
        app = self._app_assigned('stpm', 'a1')
        r = self._record(app, 'accept')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('3000'))

    def test_approve_sets_other_2000(self):
        app = self._app_assigned('poly', 'a2')
        self._record(app, 'accept')
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('2000'))

    def test_decline_clears_amount(self):
        app = self._app_assigned('matric', 'a3')
        ScholarshipApplication.objects.filter(id=app.id).update(award_amount=Decimal('2000'))
        self._record(app, 'decline')
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)

    def test_approve_preserves_super_override(self):
        # A pre-set (super-overridden) amount is NOT clobbered by a re-record on approve.
        app = self._app_assigned('poly', 'a4')
        ScholarshipApplication.objects.filter(id=app.id).update(award_amount=Decimal('2500'))
        self._record(app, 'accept')
        app.refresh_from_db()
        self.assertEqual(app.award_amount, Decimal('2500'))

    def test_approve_skips_amount_when_disqualified(self):
        # A confident disqualifier (not-genuine offer) → approve persists NO amount;
        # a super may override it afterwards via the set-award endpoint.
        app = self._app_assigned('matric', 'dq')
        _add_not_genuine_offer(app)
        r = self._record(app, 'accept')
        self.assertEqual(r.status_code, 200, r.content)
        app.refresh_from_db()
        self.assertIsNone(app.award_amount)

    def test_serializer_exposes_proposed(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        app = _app(self.cohort, pathway='stpm', suffix='ser')
        data = AdminApplicationDetailSerializer(app).data
        self.assertEqual(data['proposed_award_amount'], '3000')
        self.assertIsNone(data['award_disqualifier'])

    def test_serializer_disqualified_is_null_with_reason(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        app = _app(self.cohort, pathway='matric', suffix='serdq')
        _add_not_genuine_offer(app)
        data = AdminApplicationDetailSerializer(app).data
        self.assertIsNone(data['proposed_award_amount'])
        self.assertEqual(data['award_disqualifier'], 'offer_not_official')
