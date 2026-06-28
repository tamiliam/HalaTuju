"""Standardised assistance amount (2026-06-29).

The award is fixed by pathway (STPM → RM3,000, else RM2,000), auto-applied when a reviewer
records an APPROVE verdict, cleared on DECLINE, and only a SUPER may override it (tested in
test_sponsorship). Here: the pure rule + the record-verdict auto-apply/clear behaviour +
the proposed_award_amount serializer field.
"""
from decimal import Decimal

from django.test import TestCase, override_settings

from rest_framework.test import APIClient

from apps.courses.models import StudentProfile, PartnerAdmin
from apps.scholarship import award
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.tests.test_sponsorship import _token, TEST_JWT_SECRET


def _cohort():
    return ScholarshipCohort.objects.create(code='pa', name='B40', year=2026)


def _app(cohort, *, pathway='matric', status='interviewed', suffix='1'):
    p = StudentProfile.objects.create(supabase_user_id=f'aw-{suffix}', grades={'bm': 'A'}, exam_type='spm')
    return ScholarshipApplication.objects.create(
        cohort=cohort, profile=p, status=status, chosen_pathway=pathway)


class TestProposedAmountRule(TestCase):
    def setUp(self):
        self.cohort = _cohort()

    def test_stpm_is_3000(self):
        app = _app(self.cohort, pathway='stpm', suffix='s')
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

    def test_serializer_exposes_proposed(self):
        from apps.scholarship.serializers_admin import AdminApplicationDetailSerializer
        app = _app(self.cohort, pathway='stpm', suffix='ser')
        data = AdminApplicationDetailSerializer(app).data
        self.assertEqual(data['proposed_award_amount'], '3000')
