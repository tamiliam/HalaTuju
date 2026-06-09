"""Four rejection buckets: engine category (merit/need/ineligible), bucket-specific
decline emails, and the post-shortlist admin reject action (interview/contractual)."""
import jwt
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, StudentProfile
from apps.scholarship import emails
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import admin_reject, score_application
from apps.scholarship.shortlisting import evaluate

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
REVIEWER, VIEWER = 'rej-reviewer', 'rej-viewer'

GOOD_GRADES = {'a': 'A', 'b': 'A', 'c': 'A', 'd': 'A', 'e': 'B+'}   # 4 A- + 5 strong → passes floor


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _cohort():
    return ScholarshipCohort.objects.create(
        code='c', name='B40 Programme', year=2026,
        min_spm_a_count=4, min_spm_bplus_count=5, min_stpm_pngk=2.9, per_capita_ceiling=1584)


class TestEngineCategory(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = _cohort()

    def _app(self, *, grades=GOOD_GRADES, str_=True, income=None, size=None,
             consent=True, intends=True, upu=''):
        p = StudentProfile.objects.create(
            supabase_user_id=f'u{StudentProfile.objects.count()}', receives_str=str_,
            grades=grades, household_income=income, household_size=size)
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, consent_to_contact=consent,
            intends_tertiary_2026=intends, upu_status=upu)

    def test_merit_when_grades_below_floor(self):
        r = evaluate(self._app(grades={}), self.cohort)
        self.assertEqual((r.verdict, r.category), ('rejected', 'merit'))

    def test_need_when_income_too_high(self):
        r = evaluate(self._app(str_=False, income=14679, size=7), self.cohort)
        self.assertEqual((r.verdict, r.category), ('rejected', 'need'))

    def test_ineligible_no_consent(self):
        self.assertEqual(evaluate(self._app(consent=False), self.cohort).category, 'ineligible')

    def test_ineligible_not_intending(self):
        self.assertEqual(evaluate(self._app(intends=False), self.cohort).category, 'ineligible')

    def test_ineligible_ipts(self):
        self.assertEqual(evaluate(self._app(upu='ipts'), self.cohort).category, 'ineligible')

    def test_shortlisted_has_blank_category(self):
        r = evaluate(self._app(), self.cohort)   # STR + good grades
        self.assertEqual((r.verdict, r.category), ('shortlisted', ''))

    def test_score_application_persists_category(self):
        app = self._app(grades={})
        score_application(app)
        app.refresh_from_db()
        self.assertEqual(app.rejection_category, 'merit')


class TestDeclineEmailDispatch(TestCase):
    def test_merit_email_suggests_academic(self):
        emails.send_decline_email('x@y.com', 'Priya', 'B40', category='merit', lang='en')
        self.assertIn('academic', mail.outbox[-1].body.lower())

    def test_need_email_suggests_financial_need(self):
        emails.send_decline_email('x@y.com', 'Priya', 'B40', category='need', lang='en')
        self.assertIn('financial need', mail.outbox[-1].body.lower())

    def test_interview_email_thanks_for_documents(self):
        emails.send_decline_email('x@y.com', 'Priya', 'B40', category='interview', lang='en')
        self.assertIn('documents', mail.outbox[-1].body.lower())

    def test_ineligible_and_contractual_use_generic(self):
        emails.send_decline_email('x@y.com', 'Priya', 'B40', category='ineligible', lang='en')
        emails.send_decline_email('x@y.com', 'Priya', 'B40', category='contractual', lang='en')
        # generic body mentions the seminars line, not the academic/need-specific phrasing
        for box in mail.outbox[-2:]:
            self.assertIn('seminar', box.body.lower())
            self.assertNotIn('financial need', box.body.lower())

    def test_all_languages_present(self):
        for lang in ('en', 'ms', 'ta'):
            emails.send_decline_email('x@y.com', 'A', 'B40', category='interview', lang=lang)
        self.assertEqual(len(mail.outbox), 3)


class TestAdminRejectService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = _cohort()
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='svc-admin', role='reviewer', is_active=True, name='A', email='admin@x.com')

    def _app(self, status):
        p = StudentProfile.objects.create(supabase_user_id=f'u{StudentProfile.objects.count()}')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email='stu@x.com')

    def test_interview_reject_from_shortlisted(self):
        app = self._app('shortlisted')
        admin_reject(app, self.admin, 'interview')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertEqual(app.rejection_category, 'interview')
        self.assertEqual(app.rejected_by, 'admin@x.com')
        self.assertIsNotNone(app.rejected_at)
        self.assertIn('documents', mail.outbox[-1].body.lower())

    def test_interview_reject_blocked_when_accepted(self):
        with self.assertRaises(ValueError):
            admin_reject(self._app('accepted'), self.admin, 'interview')

    def test_contractual_reject_from_accepted(self):
        app = self._app('accepted')
        admin_reject(app, self.admin, 'contractual')
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'contractual'))

    def test_contractual_reject_blocked_when_not_accepted(self):
        with self.assertRaises(ValueError):
            admin_reject(self._app('shortlisted'), self.admin, 'contractual')

    def test_bad_category_raises(self):
        with self.assertRaises(ValueError):
            admin_reject(self._app('shortlisted'), self.admin, 'merit')   # engine bucket, not settable here


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestAdminRejectEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = _cohort()
        PartnerAdmin.objects.create(supabase_user_id=REVIEWER, role='reviewer', is_active=True, name='R', email='r@x.com')
        PartnerAdmin.objects.create(supabase_user_id=VIEWER, role='admin', is_active=True, name='V', email='v@x.com')

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _app(self, status):
        p = StudentProfile.objects.create(supabase_user_id=f'e{StudentProfile.objects.count()}')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email='stu@x.com')

    def _url(self, app):
        return f'/api/v1/admin/scholarship/applications/{app.id}/reject/'

    def test_reviewer_interview_reject(self):
        app = self._app('interviewed')
        self._auth(REVIEWER)
        r = self.client.post(self._url(app), {'category': 'interview'}, format='json')
        self.assertEqual(r.status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'interview'))

    def test_viewer_forbidden(self):
        app = self._app('shortlisted')
        self._auth(VIEWER)
        self.assertEqual(self.client.post(self._url(app), {'category': 'interview'}, format='json').status_code, 403)

    def test_interview_on_accepted_400(self):
        app = self._app('accepted')
        self._auth(REVIEWER)
        r = self.client.post(self._url(app), {'category': 'interview'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_status')

    def test_contractual_on_accepted_ok(self):
        app = self._app('accepted')
        self._auth(REVIEWER)
        r = self.client.post(self._url(app), {'category': 'contractual'}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.id).rejection_category, 'contractual')

    def test_bad_category_400(self):
        app = self._app('shortlisted')
        self._auth(REVIEWER)
        r = self.client.post(self._url(app), {'category': 'need'}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_category')
