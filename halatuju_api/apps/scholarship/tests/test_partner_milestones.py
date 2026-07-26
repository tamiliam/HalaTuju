"""Partner-organisation comms — milestones + the assignment email (S3, 2026-07-26).

The load-bearing assertions here are about a milestone being told ONCE, never for a state that has
since been reverted, and never lost because the organisation had no address at the time.
"""
import jwt
from django.core import mail
from django.test import TestCase, override_settings
from django.utils import timezone
from rest_framework.test import APIClient

from apps.courses.models import PartnerAdmin, PartnerOrganisation, StudentProfile
from apps.scholarship import partner_comms, partner_notify
from apps.scholarship.models import (
    PartnerEmailLog, PartnerEmailTemplate, ScholarshipApplication, ScholarshipCohort,
)

TEST_JWT_SECRET = 'test-secret-partner-milestones'
LIVE = dict(PARTNER_COMMS_ENABLED=True,
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


def _token(uid):
    return jwt.encode({'sub': uid, 'aud': 'authenticated', 'role': 'authenticated'},
                      TEST_JWT_SECRET, algorithm='HS256')


def _org(code, name=None, email='partner@example.org'):
    org, _ = PartnerOrganisation.objects.update_or_create(
        code=code,
        defaults={'name': name or code.upper(), 'contact_email': email,
                  'contact_person': 'Sivamani', 'is_active': True},
    )
    return org


def _app(cohort, chip, status, n):
    prof = StudentProfile.objects.create(
        supabase_user_id=f'pm-{chip}-{status}-{n}', name=f'Student {n}', referral_source=chip)
    return ScholarshipApplication.objects.create(cohort=cohort, profile=prof, status=status)


def _seed():
    from django.core.management import call_command
    call_command('seed_partner_email_templates', verbosity=0)
    PartnerEmailTemplate.objects.update(enabled=True)


@override_settings(**LIVE)
class TestMilestones(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed()
        cls.cohort = ScholarshipCohort.objects.create(code='pm-2026', name='PM', year=2026)

    def setUp(self):
        mail.outbox = []

    def test_awaiting_review_is_told_once_then_never_again(self):
        _org('smc')
        app = _app(self.cohort, 'smc', 'profile_complete', 1)
        partner_notify.send_partner_milestones()
        self.assertEqual(len([m for m in mail.outbox if 'completed' in m.subject]), 1)
        app.refresh_from_db()
        self.assertIsNotNone(app.partner_awaiting_notified_at)

        mail.outbox = []
        partner_notify.send_partner_milestones()
        self.assertEqual(mail.outbox, [])

    def test_a_reverted_transition_produces_no_email_at_all(self):
        """The sweep re-checks the CURRENT status. This is why milestones are not sent inline at
        the transition — `revert_if_profile_incomplete` can undo it before the sweep runs."""
        _org('smc')
        app = _app(self.cohort, 'smc', 'profile_complete', 1)
        app.status = 'shortlisted'
        app.save(update_fields=['status'])
        partner_notify.send_partner_milestones()
        self.assertEqual(mail.outbox, [])
        app.refresh_from_db()
        self.assertIsNone(app.partner_awaiting_notified_at)

    def test_an_award_reverted_to_recommended_produces_no_email(self):
        _org('smc')
        app = _app(self.cohort, 'smc', 'awarded', 1)
        app.status = 'recommended'
        app.save(update_fields=['status'])
        partner_notify.send_partner_milestones()
        self.assertEqual([m for m in mail.outbox if 'awarded' in m.subject.lower()], [])

    def test_several_students_share_one_email(self):
        _org('smc')
        for i in range(3):
            _app(self.cohort, 'smc', 'profile_complete', i)
        partner_notify.send_partner_milestones()
        msgs = [m for m in mail.outbox if 'completed' in m.subject]
        self.assertEqual(len(msgs), 1)
        for i in range(3):
            self.assertIn(f'STUDENT {i}', msgs[0].body)

    def test_each_organisation_gets_only_its_own_students(self):
        _org('smc')
        _org('pptm', email='pptm@example.org')
        _app(self.cohort, 'smc', 'profile_complete', 1)
        _app(self.cohort, 'pptm', 'profile_complete', 2)
        partner_notify.send_partner_milestones()
        by_to = {m.to[0]: m.body for m in mail.outbox if 'completed' in m.subject}
        self.assertEqual(len(by_to), 2)
        self.assertIn('STUDENT 1', by_to['partner@example.org'])
        self.assertNotIn('STUDENT 2', by_to['partner@example.org'])

    def test_an_unreachable_organisation_keeps_its_students_UNSTAMPED(self):
        """So they are told once an address exists, rather than silently skipped forever."""
        org = _org('noaddr', email='')
        app = _app(self.cohort, 'noaddr', 'profile_complete', 1)
        partner_notify.send_partner_milestones()
        app.refresh_from_db()
        self.assertIsNone(app.partner_awaiting_notified_at)
        self.assertTrue(PartnerEmailLog.objects.filter(
            organisation=org, kind='awaiting_review', note='no_recipient').exists())

    def test_adding_an_address_later_tells_them_the_backlog(self):
        org = _org('noaddr', email='')
        app = _app(self.cohort, 'noaddr', 'profile_complete', 1)
        partner_notify.send_partner_milestones()
        self.assertEqual(mail.outbox, [])
        PartnerOrganisation.objects.filter(pk=org.pk).update(contact_email='now@example.org')
        partner_notify.send_partner_milestones()
        self.assertEqual(len([m for m in mail.outbox if 'completed' in m.subject]), 1)
        app.refresh_from_db()
        self.assertIsNotNone(app.partner_awaiting_notified_at)

    def test_a_repeated_identical_skip_is_logged_once(self):
        """An hourly sweep would otherwise write the same row 24 times a day per organisation."""
        org = _org('noaddr', email='')
        _app(self.cohort, 'noaddr', 'profile_complete', 1)
        for _ in range(3):
            partner_notify.send_partner_milestones()
        self.assertEqual(PartnerEmailLog.objects.filter(
            organisation=org, kind='awaiting_review', note='no_recipient').count(), 1)

    def test_a_house_org_student_is_never_the_subject_of_a_partner_email(self):
        _org(partner_comms.HOUSE_ORG_CODE, name='BrightPath', email='staff@example.org')
        app = _app(self.cohort, partner_comms.HOUSE_ORG_CODE, 'profile_complete', 1)
        partner_notify.send_partner_milestones()
        self.assertEqual(mail.outbox, [])
        app.refresh_from_db()
        self.assertIsNone(app.partner_awaiting_notified_at)

    def test_a_self_referred_student_is_never_the_subject_of_one_either(self):
        _org('smc')
        app = _app(self.cohort, 'halatuju', 'profile_complete', 1)   # no partner owns this chip
        partner_notify.send_partner_milestones()
        self.assertEqual(mail.outbox, [])
        app.refresh_from_db()
        self.assertIsNone(app.partner_awaiting_notified_at)

    def test_a_big_backlog_is_capped_and_the_rest_follow_next_sweep(self):
        _org('smc')
        for i in range(partner_notify.MAX_MILESTONE_STUDENTS + 3):
            _app(self.cohort, 'smc', 'profile_complete', i)
        partner_notify.send_partner_milestones()
        self.assertEqual(
            ScholarshipApplication.objects.filter(
                partner_awaiting_notified_at__isnull=False).count(),
            partner_notify.MAX_MILESTONE_STUDENTS)
        mail.outbox = []
        partner_notify.send_partner_milestones()
        self.assertEqual(len([m for m in mail.outbox if 'completed' in m.subject]), 1)
        self.assertEqual(
            ScholarshipApplication.objects.filter(
                partner_awaiting_notified_at__isnull=True).count(), 0)

    def test_awarded_covers_the_funded_states(self):
        _org('smc')
        for i, status in enumerate(('awarded', 'active', 'maintenance')):
            _app(self.cohort, 'smc', status, i)
        partner_notify.send_partner_milestones()
        msgs = [m for m in mail.outbox if 'awarded' in m.subject.lower()]
        self.assertEqual(len(msgs), 1)
        self.assertIn('as your own', msgs[0].body)   # the licence to share it as theirs

    def test_the_two_kinds_are_independently_switchable(self):
        _org('smc')
        _app(self.cohort, 'smc', 'profile_complete', 1)
        _app(self.cohort, 'smc', 'awarded', 2)
        PartnerEmailTemplate.objects.filter(kind='awaiting_review').update(enabled=False)
        partner_notify.send_partner_milestones()
        self.assertEqual([m for m in mail.outbox if 'completed' in m.subject], [])
        self.assertEqual(len([m for m in mail.outbox if 'awarded' in m.subject.lower()]), 1)

    @override_settings(PARTNER_COMMS_ENABLED=False)
    def test_platform_flag_off_stamps_nothing(self):
        _org('smc')
        app = _app(self.cohort, 'smc', 'profile_complete', 1)
        partner_notify.send_partner_milestones()
        self.assertEqual(mail.outbox, [])
        app.refresh_from_db()
        self.assertIsNone(app.partner_awaiting_notified_at)

    def test_dry_run_stamps_nothing_so_it_can_be_repeated(self):
        import io
        _org('smc')
        app = _app(self.cohort, 'smc', 'profile_complete', 1)
        out = io.StringIO()
        partner_notify.send_partner_milestones(dry_run=True, out=out)
        self.assertEqual(mail.outbox, [])
        app.refresh_from_db()
        self.assertIsNone(app.partner_awaiting_notified_at)
        self.assertIn('dry-run', out.getvalue())

    def test_a_failed_send_leaves_the_student_unstamped(self):
        from unittest import mock
        _org('smc')
        app = _app(self.cohort, 'smc', 'profile_complete', 1)
        with mock.patch('apps.scholarship.partner_notify.send_partner_email', return_value=False):
            partner_notify.send_partner_milestones()
        app.refresh_from_db()
        self.assertIsNone(app.partner_awaiting_notified_at,
                          'a failed send must be retried, not swallowed')


@override_settings(ROOT_URLCONF='halatuju.urls', SUPABASE_JWT_SECRET=TEST_JWT_SECRET, **LIVE)
class TestAssignmentEmail(TestCase):
    @classmethod
    def setUpTestData(cls):
        _seed()
        cls.cohort = ScholarshipCohort.objects.create(code='pm-as', name='PM', year=2026)
        cls.org = _org('smc')
        cls.other = _org('pptm', email='pptm@example.org')
        cls.org_admin = PartnerAdmin.objects.create(
            supabase_user_id='pm-oa', role='org_admin', is_active=True,
            owning_organisation=cls.org, name='OrgAdmin', email='oa@example.org')

    def setUp(self):
        self.client = APIClient()
        self.client.credentials(HTTP_AUTHORIZATION=f'Bearer {_token("pm-oa")}')
        mail.outbox = []
        self.app = _app(self.cohort, '', 'profile_complete', 1)   # sourceless student

    def _assign(self, value):
        return self.client.patch(
            f'/api/v1/admin/scholarship/applications/{self.app.id}/witness/',
            {'witness_org': value}, format='json')

    def test_assigning_emails_that_organisation(self):
        r = self._assign('smc')
        self.assertEqual(r.status_code, 200)
        msgs = [m for m in mail.outbox if 'joined' in m.subject]
        self.assertEqual(len(msgs), 1)
        self.assertEqual(msgs[0].to, ['partner@example.org'])
        self.assertIn('STUDENT 1', msgs[0].body)

    def test_reassigning_emails_the_NEW_organisation_only(self):
        self._assign('smc')
        mail.outbox = []
        self._assign('pptm')
        recipients = {m.to[0] for m in mail.outbox if 'joined' in m.subject}
        self.assertEqual(recipients, {'pptm@example.org'})

    def test_clearing_the_witness_emails_nobody(self):
        self._assign('smc')
        mail.outbox = []
        r = self._assign(None)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_an_email_failure_never_fails_the_assignment(self):
        from unittest import mock
        with mock.patch('apps.scholarship.partner_notify.send_partner_email',
                        side_effect=RuntimeError('smtp down')):
            r = self._assign('smc')
        self.assertEqual(r.status_code, 200, 'the assignment must still succeed')
        self.app.refresh_from_db()
        self.assertEqual(self.app.witness_org_id, self.org.id)

    @override_settings(PARTNER_COMMS_ENABLED=False)
    def test_flag_off_assigns_without_emailing(self):
        r = self._assign('smc')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mail.outbox, [])

    def test_an_unreachable_organisation_is_assigned_and_logged_not_emailed(self):
        PartnerOrganisation.objects.filter(pk=self.org.pk).update(contact_email='')
        r = self._assign('smc')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(mail.outbox, [])
        self.assertTrue(PartnerEmailLog.objects.filter(
            organisation=self.org, kind='assigned', note='no_recipient').exists())

    def test_the_log_row_names_the_application(self):
        self._assign('smc')
        row = PartnerEmailLog.objects.get(organisation=self.org, kind='assigned', ok=True)
        self.assertEqual(row.application_id, self.app.id)
        self.assertEqual(row.students, 1)
