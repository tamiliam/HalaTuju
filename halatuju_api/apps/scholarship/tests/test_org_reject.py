"""Org-admin reject of a stuck SHORTLISTED applicant (bucket 'incomplete') — owner 2026-07-21.

Three things make this action different from every other decline, and each is pinned here:

  1. It is IMMEDIATE and IRREVERSIBLE — no cool-off, no embargo, no cancel window. The decline
     email goes in the same call.
  2. It is gated TIGHTER than `_require_app_write`: super/org_admin only. A `qc` and the assigned
     reviewer — both of whom may reject through the ordinary `/reject/` endpoint — are refused.
  3. The reason is REQUIRED and recorded verbatim, but stays INTERNAL: the student receives the
     generic warm decline, never the admin's words.

Plus the invariant that motivated the feature: the moment the reject lands, the student can no
longer add a document or advance their own status.
"""
import jwt
from django.core import mail
from django.test import TestCase, override_settings
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship.models import ScholarshipApplication, ScholarshipCohort
from apps.scholarship.services import POST_SHORTLIST_EDITABLE, org_admin_reject

TEST_JWT_SECRET = 'test-supabase-jwt-secret'
ORG_ADMIN, SUPER, QC, REVIEWER, OTHER_ORG_ADMIN = 'or-oa', 'or-su', 'or-qc', 'or-rev', 'or-other'


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


class TestOrgAdminRejectService(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cohort = ScholarshipCohort.objects.create(code='c', name='B40 Programme', year=2026)
        cls.admin = PartnerAdmin.objects.create(
            supabase_user_id='svc-oa', role='org_admin', is_active=True,
            name='Org Admin', email='oa@x.com')

    def _app(self, status='shortlisted'):
        p = StudentProfile.objects.create(
            supabase_user_id=f'u{StudentProfile.objects.count()}', name='Priya')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email='stu@x.com')

    def test_records_status_bucket_stamps_and_reason(self):
        app = self._app()
        org_admin_reject(app, self.admin, '  Never uploaded the payslip after 4 reminders.  ')
        app.refresh_from_db()
        self.assertEqual(app.status, 'rejected')
        self.assertEqual(app.rejection_category, 'incomplete')
        self.assertEqual(app.rejected_by, 'oa@x.com')
        self.assertIsNotNone(app.rejected_at)
        # Stored verbatim, but stripped — a reason of pure whitespace is not a reason.
        self.assertEqual(app.rejection_comments, 'Never uploaded the payslip after 4 reminders.')
        # The status it came FROM is snapshotted like every other decline.
        self.assertEqual(app.pre_decline_status, 'shortlisted')

    def test_email_is_immediate_with_no_embargo(self):
        """The whole point of the owner's design: no cool-off, nothing left pending."""
        app = self._app()
        org_admin_reject(app, self.admin, 'Incomplete after the full reminder sequence.')
        app.refresh_from_db()
        self.assertIsNone(app.decline_due_at)
        self.assertEqual(app.pending_rejection_category, '')
        self.assertIsNotNone(app.decline_email_sent_at)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].to, ['stu@x.com'])

    def test_uses_the_generic_warm_copy_not_the_not_selected_copy(self):
        """The 'interview' bucket opens "thank you for COMPLETING your application" — false for a
        student who never completed. 'incomplete' must fall through to the generic FAIL_* copy."""
        app = self._app()
        org_admin_reject(app, self.admin, 'Did not complete.')
        body = mail.outbox[0].body.lower()
        self.assertIn("please don't be discouraged", body)
        self.assertNotIn('for completing your', body)
        self.assertNotIn('most closely met', body)

    def test_reason_never_reaches_the_student(self):
        secret = 'Suspected fabricated payslip - flagged internally'
        app = self._app()
        org_admin_reject(app, self.admin, secret)
        msg = mail.outbox[0]
        haystack = (msg.subject + msg.body + ''.join(c for c, _ in msg.alternatives)).lower()
        self.assertNotIn('fabricated', haystack)
        self.assertNotIn('flagged internally', haystack)

    def test_blank_reason_refused(self):
        for blank in ('', '   ', None):
            with self.subTest(reason=repr(blank)):
                app = self._app()
                with self.assertRaises(ValueError) as ctx:
                    org_admin_reject(app, self.admin, blank)
                self.assertEqual(str(ctx.exception), 'comments_required')
                app.refresh_from_db()
                self.assertEqual(app.status, 'shortlisted')   # nothing moved
        self.assertEqual(len(mail.outbox), 0)                 # and nobody was emailed

    def test_only_from_shortlisted(self):
        for stage in ('submitted', 'profile_complete', 'interviewing', 'interviewed',
                      'recommended', 'awarded', 'active', 'rejected', 'expired'):
            with self.subTest(stage=stage):
                with self.assertRaises(ValueError) as ctx:
                    org_admin_reject(self._app(stage), self.admin, 'A reason.')
                self.assertEqual(str(ctx.exception), 'bad_status')

    def test_student_is_locked_out_immediately(self):
        """The owner's stated purpose: stop the applicant adding a document or advancing their
        own status. Every student write path gates on POST_SHORTLIST_EDITABLE."""
        app = self._app()
        self.assertIn(app.status, POST_SHORTLIST_EDITABLE)     # editable before
        org_admin_reject(app, self.admin, 'A reason.')
        app.refresh_from_db()
        self.assertNotIn(app.status, POST_SHORTLIST_EDITABLE)  # frozen after


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET)
class TestOrgAdminRejectEndpoint(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.org = PartnerOrganisation.objects.create(name='Tamil Foundation', code='tf')
        cls.other = PartnerOrganisation.objects.create(name='Other Org', code='oo')
        cls.cohort = ScholarshipCohort.objects.create(
            code='c', name='B40 Programme', year=2026, owning_organisation=cls.org)
        mk = PartnerAdmin.objects.create
        mk(supabase_user_id=ORG_ADMIN, role='org_admin', is_active=True, name='OA',
           email='oa@x.com', owning_organisation=cls.org)
        mk(supabase_user_id=SUPER, role='super', is_super_admin=True, is_active=True,
           name='SU', email='su@x.com')
        cls.reviewer = mk(supabase_user_id=REVIEWER, role='reviewer', is_active=True, name='R',
                          email='r@x.com', owning_organisation=cls.org)
        mk(supabase_user_id=QC, role='qc', is_active=True, name='Q', email='q@x.com',
           owning_organisation=cls.org)
        mk(supabase_user_id=OTHER_ORG_ADMIN, role='org_admin', is_active=True, name='OO',
           email='oo@x.com', owning_organisation=cls.other)

    def setUp(self):
        self.client = APIClient()

    def _auth(self, uid):
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token(uid)}')

    def _app(self, status='shortlisted'):
        p = StudentProfile.objects.create(supabase_user_id=f'e{StudentProfile.objects.count()}')
        return ScholarshipApplication.objects.create(
            cohort=self.cohort, profile=p, status=status, notify_email='stu@x.com',
            assigned_to=self.reviewer)

    def _url(self, app):
        return f'/api/v1/admin/scholarship/applications/{app.id}/org-reject/'

    def _post(self, app, **body):
        return self.client.post(self._url(app), body or {'comments': 'A recorded reason.'},
                                format='json')

    def test_org_admin_may_reject(self):
        app = self._app()
        self._auth(ORG_ADMIN)
        self.assertEqual(self._post(app).status_code, 200)
        app.refresh_from_db()
        self.assertEqual((app.status, app.rejection_category), ('rejected', 'incomplete'))
        self.assertEqual(app.rejection_comments, 'A recorded reason.')

    def test_super_may_reject(self):
        """"The rejection is a super feature" — the platform super keeps it too."""
        app = self._app()
        self._auth(SUPER)
        self.assertEqual(self._post(app).status_code, 200)

    def test_qc_refused(self):
        """A qc passes _require_app_write (org-wide write) — this endpoint must still refuse."""
        app = self._app()
        self._auth(QC)
        self.assertEqual(self._post(app).status_code, 403)
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.id).status, 'shortlisted')

    def test_assigned_reviewer_refused(self):
        """The reviewer this case is ASSIGNED to may decline via /reject/, but not via this one."""
        app = self._app()
        self._auth(REVIEWER)
        self.assertEqual(self._post(app).status_code, 403)
        self.assertEqual(ScholarshipApplication.objects.get(pk=app.id).status, 'shortlisted')

    def test_other_org_admin_gets_404_not_403(self):
        """Cross-org must not leak that the application exists."""
        app = self._app()
        self._auth(OTHER_ORG_ADMIN)
        self.assertEqual(self._post(app).status_code, 404)

    def test_blank_comments_400(self):
        app = self._app()
        self._auth(ORG_ADMIN)
        r = self._post(app, comments='   ')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'comments_required')
        self.assertEqual(len(mail.outbox), 0)

    def test_missing_comments_key_400(self):
        app = self._app()
        self._auth(ORG_ADMIN)
        r = self.client.post(self._url(app), {}, format='json')
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'comments_required')

    def test_wrong_status_400(self):
        app = self._app('interviewed')
        self._auth(ORG_ADMIN)
        r = self._post(app)
        self.assertEqual(r.status_code, 400)
        self.assertEqual(r.json()['code'], 'bad_status')

    def test_second_reject_400_not_a_double_email(self):
        """Idempotence guard: the case is no longer 'shortlisted', so a re-post is refused."""
        app = self._app()
        self._auth(ORG_ADMIN)
        self.assertEqual(self._post(app).status_code, 200)
        self.assertEqual(self._post(app).status_code, 400)
        self.assertEqual(len(mail.outbox), 1)

    def test_reason_is_returned_to_the_cockpit(self):
        app = self._app()
        self._auth(ORG_ADMIN)
        r = self._post(app, comments='Stuck since March; no response.')
        self.assertEqual(r.json()['rejection_comments'], 'Stuck since March; no response.')
